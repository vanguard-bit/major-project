from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urljoin, urlsplit

import anyio
import httpx
import typer
import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ait.analysis import analyze_run, extract_field_paths
from ait.artifacts import (
    ArtifactEnvelope,
    canonical_json_bytes,
    collect_provenance,
    redact_secrets,
)
from ait.models import CapturedExchange, RunReport, TargetConfig

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_MISSING_CREDS = 2
EXIT_SAFETY = 3

MAX_REQUESTS_PER_RUN = 20
MAX_RESPONSE_BYTES = 1_048_576  # 1 MiB
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 30
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
SAFE_METHODS = frozenset({"GET", "HEAD"})
REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})

SAFE_PLAN_ID = re.compile(r"^[a-zA-Z0-9._-]+$")

HEADER_ALLOWLIST = frozenset(
    {
        "content-type",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "retry-after",
        "x-github-request-id",
        "x-notion-request-id",
    }
)

app = typer.Typer(add_completion=False, help="Safe live SaaS probe runner")


class SafetyRejectionError(Exception):
    """Raised when a safety policy rejects a request or response."""


class MissingCredentialsError(Exception):
    """Raised when the plan's token environment variable is unset."""


class RequestFailureError(Exception):
    """Raised when a live request fails after retries or returns an error status."""


class LiveRequestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    phase: Literal["baseline", "mutated"] = "baseline"
    json_body: dict[str, Any] | None = None


class LivePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"]
    id: str
    provider: Literal["github", "notion"]
    environment: Literal["sandbox", "production-readonly"]
    base_url: HttpUrl
    allowed_hosts: set[str]
    token_env: str
    expected_endpoints: list[str]
    sensitive_markers: list[str]
    requests: list[LiveRequestSpec] = Field(
        min_length=1,
        max_length=MAX_REQUESTS_PER_RUN,
    )

    @field_validator("id")
    @classmethod
    def _safe_plan_id(cls, value: str) -> str:
        if ".." in value or "/" in value or "\\" in value:
            raise ValueError("plan id must not contain path separators or '..'")
        if not SAFE_PLAN_ID.fullmatch(value):
            raise ValueError(
                "plan id must be a safe slug matching [a-zA-Z0-9._-]+"
            )
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def _nonempty_hosts(cls, value: set[str]) -> set[str]:
        if not value:
            raise ValueError("allowed_hosts must be non-empty")
        return value


class LiveObservation(BaseModel):
    request_index: int
    method: str
    normalized_path: str
    request_target: str
    status_code: int
    response_bytes: int
    response_sha256: str
    response_fields: list[str]
    selected_headers: dict[str, str]
    elapsed_ms: float


def normalize_endpoint_path(path: str) -> str:
    without_fragment = path.split("#", 1)[0]
    without_query = without_fragment.split("?", 1)[0]
    if "://" in without_query:
        without_query = httpx.URL(without_query).path or "/"
    elif without_query.startswith("//"):
        without_query = "/" + without_query.lstrip("/").split("/", 1)[-1]
    if not without_query.startswith("/"):
        without_query = "/" + without_query
    return re.sub(r"/{2,}", "/", without_query) or "/"


def _query_as_str(query: Any) -> str:
    if isinstance(query, (bytes, bytearray)):
        return bytes(query).decode("ascii", errors="strict")
    return str(query)


def _request_target(path: str) -> str:
    """Path + query for evidence; fragment stripped. Not used for endpoint identity."""
    without_fragment = path.split("#", 1)[0]
    if "://" in without_fragment:
        url = httpx.URL(without_fragment)
        target = url.path or "/"
        if url.query:
            target = f"{target}?{_query_as_str(url.query)}"
        return target
    if not without_fragment.startswith("/"):
        without_fragment = "/" + without_fragment
    return without_fragment


def load_live_plan(path: Path) -> LivePlan:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"live plan must be a mapping: {path}")
    requests = data.get("requests")
    if isinstance(requests, list) and len(requests) > MAX_REQUESTS_PER_RUN:
        raise SafetyRejectionError(
            f"plan exceeds maximum of {MAX_REQUESTS_PER_RUN} requests per run"
        )
    return LivePlan.model_validate(data)


def _approved_origin(base_url: HttpUrl | httpx.URL | str) -> tuple[str, str, int]:
    url = httpx.URL(str(base_url))
    scheme = (url.scheme or "").lower()
    host = url.host
    if host is None:
        raise SafetyRejectionError("base_url is missing a host")
    try:
        host_idna = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise SafetyRejectionError(f"invalid host for IDNA: {host!r}") from exc
    port = url.port
    if port is None:
        port = 443 if scheme == "https" else 80 if scheme == "http" else url.port
    if port is None:
        raise SafetyRejectionError("unable to determine effective port for base_url")
    return scheme, host_idna, int(port)


def _url_origin(url: httpx.URL) -> tuple[str, str, int]:
    scheme = (url.scheme or "").lower()
    host = url.host
    if host is None:
        raise SafetyRejectionError("URL is missing a host")
    try:
        host_idna = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise SafetyRejectionError(f"invalid host for IDNA: {host!r}") from exc
    port = url.port
    if port is None:
        port = 443 if scheme == "https" else 80 if scheme == "http" else None
    if port is None:
        raise SafetyRejectionError("unable to determine effective port")
    return scheme, host_idna, int(port)


def _path_has_control_chars(path_text: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in path_text)


def _reject_path_form(path_text: str) -> None:
    if "\\" in path_text or "%5c" in path_text.lower():
        raise SafetyRejectionError("backslashes are not allowed in paths")
    if _path_has_control_chars(path_text):
        raise SafetyRejectionError("control characters are not allowed in paths")
    lowered = path_text.lower()
    if "%2e%2e" in lowered or "%2e." in lowered or ".%2e" in lowered:
        raise SafetyRejectionError("encoded path traversal ('..') is not allowed")
    segments = [seg for seg in path_text.split("/") if seg not in ("",)]
    if any(seg in {"..", "."} for seg in segments):
        raise SafetyRejectionError("path traversal ('..') is not allowed")
    if ".." in path_text.split("/"):
        raise SafetyRejectionError("path traversal ('..') is not allowed")


def _reject_unsafe_path_text(path_text: str) -> None:
    if not path_text.startswith("/"):
        raise SafetyRejectionError("path must be absolute (start with '/')")
    current = path_text
    seen: set[str] = set()
    while current not in seen:
        seen.add(current)
        _reject_path_form(current)
        decoded = unquote(current)
        if decoded == current:
            break
        current = decoded
    else:
        raise SafetyRejectionError("path decoding did not reach a fixed point")
    _reject_path_form(current)


def resolve_request_url(plan: LivePlan, request: LiveRequestSpec) -> httpx.URL:
    raw = request.path
    if raw.startswith("//"):
        raise SafetyRejectionError("protocol-relative paths are not allowed")
    if "#" in raw:
        raise SafetyRejectionError("URL fragments are not allowed")

    approved = _approved_origin(plan.base_url)

    if "://" in raw:
        path_part = urlsplit(raw).path or "/"
        _reject_unsafe_path_text(path_part)
        url = httpx.URL(raw)
    else:
        path_only = raw.split("?", 1)[0]
        _reject_unsafe_path_text(path_only)
        base = str(plan.base_url)
        if not base.endswith("/"):
            base = base + "/"
        # Preserve leading slash semantics: join against base origin + path
        url = httpx.URL(urljoin(base, raw.lstrip("/")))

    if url.scheme != "https":
        raise SafetyRejectionError(f"scheme '{url.scheme}' is not allowed; only https")
    if url.username or url.password:
        raise SafetyRejectionError("userinfo/credentials in URLs are not allowed")
    if url.fragment:
        raise SafetyRejectionError("URL fragments are not allowed")

    origin = _url_origin(url)
    host = origin[1]
    if origin != approved:
        if origin[2] != approved[2]:
            raise SafetyRejectionError(
                f"port {origin[2]} does not match approved origin port {approved[2]}"
            )
        if origin[0] != approved[0]:
            raise SafetyRejectionError(
                f"scheme '{origin[0]}' does not match approved origin scheme '{approved[0]}'"
            )
        raise SafetyRejectionError(
            f"host '{host}' is not in the approved origin (expected '{approved[1]}')"
        )
    allowed_idna = set()
    for item in plan.allowed_hosts:
        try:
            allowed_idna.add(item.encode("idna").decode("ascii").lower())
        except UnicodeError:
            allowed_idna.add(item.lower())
    if host not in allowed_idna:
        raise SafetyRejectionError(f"host '{host}' is not in the allowlist")
    return url


def validate_request(plan: LivePlan, request: LiveRequestSpec, allow_mutation: bool) -> None:
    if request.method not in SAFE_METHODS:
        if not allow_mutation:
            raise SafetyRejectionError(
                f"mutating method {request.method} requires --allow-mutation"
            )
        if plan.environment != "sandbox":
            raise SafetyRejectionError(
                "mutating methods are only allowed when environment is sandbox"
            )
    resolve_request_url(plan, request)


def select_headers(headers: httpx.Headers) -> dict[str, str]:
    selected: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in HEADER_ALLOWLIST:
            selected[lowered] = value
    return selected


def scrub_secrets(value: Any, secrets: list[str]) -> Any:
    """Recursively replace known credential substrings before persistence/logging."""
    secrets = [s for s in secrets if s]
    if not secrets:
        return value
    if isinstance(value, dict):
        return {k: scrub_secrets(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_secrets(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_secrets(item, secrets) for item in value)
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret and secret in result:
                result = result.replace(secret, "[REDACTED]")
        return result
    return value


def sanitize_location(location: str, secrets: list[str]) -> str:
    """Sanitize redirect Location for errors/evidence without leaking tokens."""
    scrubbed = scrub_secrets(location, secrets)
    if not isinstance(scrubbed, str):
        return "[REDACTED]"
    # Drop query/fragment from displayed location to avoid response-derived secrets.
    try:
        parsed = httpx.URL(scrubbed)
        path = parsed.path or "/"
        return f"{parsed.scheme}://{parsed.host}{path}"
    except Exception:
        return scrubbed.split("?", 1)[0].split("#", 1)[0]


def _provider_headers(plan: LivePlan, token: str) -> dict[str, str]:
    if plan.provider == "github":
        from ait.providers.github import build_headers

        return build_headers(token)
    if plan.provider == "notion":
        from ait.providers.notion import build_headers

        return build_headers(token)
    raise SafetyRejectionError(f"unsupported provider {plan.provider}")


def _read_token(plan: LivePlan) -> str:
    token = os.environ.get(plan.token_env)
    if not token:
        raise MissingCredentialsError(
            f"missing credentials: environment variable {plan.token_env} is not set"
        )
    return token


async def _sleep(seconds: float) -> None:
    await anyio.sleep(seconds)


def _retry_after_seconds(
    headers: httpx.Headers, secrets: list[str] | None = None
) -> float:
    raw = headers.get("retry-after")
    if raw is None:
        return 0.0
    raw = raw.strip()
    try:
        value = float(raw)
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError) as exc:
            scrubbed = scrub_secrets(raw, secrets or [])
            raise SafetyRejectionError(
                f"invalid Retry-After header: {scrubbed!r}"
            ) from exc
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        value = (when - datetime.now(tz=UTC)).total_seconds()
    return min(MAX_RETRY_AFTER_SECONDS, max(0.0, value))


async def _read_body_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            await response.aclose()
            raise SafetyRejectionError(
                f"response exceeds maximum of {MAX_RESPONSE_BYTES} bytes (1 MiB)"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_fields(body: bytes, content_type: str | None) -> list[str]:
    if not body:
        return []
    if content_type and "json" not in content_type.lower():
        return []
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    return sorted(extract_field_paths(parsed))


def _sensitive_hit(fields: list[str], markers: list[str]) -> bool:
    for marker in markers:
        for field in fields:
            if field == marker or field.endswith(f".{marker}"):
                return True
    return False


def _target_from_plan(plan: LivePlan) -> TargetConfig:
    base = plan.base_url
    return TargetConfig(
        name=plan.id,
        environment=plan.environment,
        base_url=base,
        integration_sync_url=base,
        audit_base_url=base,
        expected_endpoints=list(plan.expected_endpoints),
        sensitive_markers=list(plan.sensitive_markers),
    )


def _new_run_id(plan_id: str) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{plan_id}-{stamp}-{uuid.uuid4().hex[:8]}"


def _resolve_under_root(output_root: Path, *parts: str) -> Path:
    root = output_root.resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SafetyRejectionError(
            f"resolved path {candidate} escapes output_root {root}"
        ) from exc
    return candidate


def _write_artifact_exclusive(path: Path, envelope: ArtifactEnvelope) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Prefer exclusive create so same-second / colliding run IDs cannot overwrite.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    content = canonical_json_bytes(envelope) + b"\n"
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise SafetyRejectionError(f"artifact already exists (refusing overwrite): {path}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _validate_redirect_location(
    request_url: httpx.URL,
    location: str,
    plan: LivePlan,
    secrets: list[str],
) -> str:
    if not location:
        raise SafetyRejectionError("redirect not followed: empty Location")
    try:
        absolute = httpx.URL(urljoin(str(request_url), location))
    except Exception as exc:
        raise SafetyRejectionError(
            f"redirect not followed: invalid Location={sanitize_location(location, secrets)}"
        ) from exc
    try:
        origin = _url_origin(absolute)
        approved = _approved_origin(plan.base_url)
        if origin != approved:
            raise SafetyRejectionError("redirect origin mismatch")
        host = origin[1]
        allowed_idna = set()
        for item in plan.allowed_hosts:
            try:
                allowed_idna.add(item.encode("idna").decode("ascii").lower())
            except UnicodeError:
                allowed_idna.add(item.lower())
        if host not in allowed_idna:
            raise SafetyRejectionError("redirect host not allowlisted")
        _reject_unsafe_path_text(absolute.path or "/")
    except SafetyRejectionError as exc:
        raise SafetyRejectionError(
            f"redirect not followed: status location rejected "
            f"location={sanitize_location(location, secrets)}"
        ) from exc
    return sanitize_location(str(absolute), secrets)


async def _execute_request(
    client: httpx.AsyncClient,
    plan: LivePlan,
    request: LiveRequestSpec,
    headers: dict[str, str],
    index: int,
    run_id: str,
    secrets: list[str],
) -> tuple[LiveObservation, CapturedExchange]:
    url = resolve_request_url(plan, request)
    started = datetime.now(tz=UTC)
    attempt = 0
    response: httpx.Response | None = None
    body = b""

    while True:
        attempt += 1
        http_request = client.build_request(
            request.method, url, headers=headers, json=request.json_body
        )
        response = await client.send(http_request, stream=True)

        if response.status_code in REDIRECT_STATUS:
            location = response.headers.get("location", "")
            status = response.status_code
            await response.aclose()
            sanitized = _validate_redirect_location(url, location, plan, secrets)
            raise SafetyRejectionError(
                f"redirect not followed: status={status} location={sanitized}"
            )

        if response.status_code in RETRYABLE_STATUS:
            if attempt > MAX_RETRIES:
                body = await _read_body_limited(response)
                await response.aclose()
                break
            delay = _retry_after_seconds(response.headers, secrets=secrets)
            await response.aclose()
            await _sleep(delay)
            continue

        body = await _read_body_limited(response)
        await response.aclose()
        break

    assert response is not None
    elapsed_ms = (datetime.now(tz=UTC) - started).total_seconds() * 1000.0
    content_type = response.headers.get("content-type")
    fields = _parse_fields(body, content_type)
    normalized = normalize_endpoint_path(request.path)
    target = scrub_secrets(_request_target(request.path), secrets)
    selected = scrub_secrets(select_headers(response.headers), secrets)
    digest = hashlib.sha256(body).hexdigest()

    if response.status_code in RETRYABLE_STATUS:
        raise RequestFailureError(
            f"request failed after retries with status {response.status_code}"
        )
    if response.status_code >= 400:
        raise RequestFailureError(f"request failed with status {response.status_code}")

    observation = LiveObservation(
        request_index=index,
        method=request.method,
        normalized_path=normalized,
        request_target=str(target),
        status_code=response.status_code,
        response_bytes=len(body),
        response_sha256=digest,
        response_fields=fields,
        selected_headers=selected if isinstance(selected, dict) else {},
        elapsed_ms=elapsed_ms,
    )
    exchange = CapturedExchange(
        run_id=run_id,
        phase=request.phase,
        method=request.method,
        path=normalized,
        status_code=response.status_code,
        request_headers={},
        request_body=None,
        response_body=None,
        extracted_fields=fields,
        contains_sensitive_marker=_sensitive_hit(fields, plan.sensitive_markers),
    )
    return observation, exchange


def _status_payload(
    *,
    plan: LivePlan,
    run_id: str,
    status: str,
    reason: str,
    observations: list[LiveObservation] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "plan_id": plan.id,
        "provider": plan.provider,
        "status": status,
        "reason": reason,
        "completed": False,
        "observations": [o.model_dump(mode="json") for o in (observations or [])],
        "evidence": evidence or {},
    }


def _write_status_artifact(
    *,
    plan: LivePlan,
    run_id: str,
    output_root: Path,
    command: list[str],
    status: str,
    reason: str,
    secrets: list[str],
    observations: list[LiveObservation] | None = None,
    evidence: dict[str, Any] | None = None,
    allow_mutation: bool,
) -> None:
    provenance = collect_provenance(command)
    configuration = scrub_secrets(
        redact_secrets(
            {
                "plan_id": plan.id,
                "provider": plan.provider,
                "environment": plan.environment,
                "base_url": str(plan.base_url),
                "allowed_hosts": sorted(plan.allowed_hosts),
                "token_env": plan.token_env,
                "expected_endpoints": plan.expected_endpoints,
                "sensitive_markers": plan.sensitive_markers,
                "allow_mutation": allow_mutation,
                "request_count": len(plan.requests),
                "run_status": status,
            }
        ),
        secrets,
    )
    payload = scrub_secrets(
        redact_secrets(
            _status_payload(
                plan=plan,
                run_id=run_id,
                status=status,
                reason=reason,
                observations=observations,
                evidence=evidence,
            )
        ),
        secrets,
    )
    path = _resolve_under_root(
        output_root, "raw", "live", plan.id, f"{run_id}.status.json"
    )
    _write_artifact_exclusive(
        path,
        ArtifactEnvelope(
            provenance=provenance,
            experiment="live",
            configuration=configuration if isinstance(configuration, dict) else {},
            payload=payload if isinstance(payload, dict) else {"status": status},
        ),
    )


async def execute_live_plan(
    plan: LivePlan,
    *,
    allow_mutation: bool = False,
    store_bodies: bool = False,
    transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    output_root: Path | None = None,
    command: list[str] | None = None,
) -> tuple[list[LiveObservation], RunReport]:
    # --store-bodies remains disabled: only permitted for approved synthetic sandbox data,
    # which is not yet gated by a separate synthetic-mode flag in this runner.
    if store_bodies:
        raise SafetyRejectionError(
            "--store-bodies is disabled; only permitted for approved synthetic sandbox data"
        )

    if len(plan.requests) > MAX_REQUESTS_PER_RUN:
        raise SafetyRejectionError(
            f"plan exceeds maximum of {MAX_REQUESTS_PER_RUN} requests per run"
        )

    cmd = command or ["python", "-m", "ait.live_runner"]
    run_id = _new_run_id(plan.id)
    secrets: list[str] = []
    token: str | None = None
    try:
        token = _read_token(plan)
        secrets = [token]
    except MissingCredentialsError:
        # Preflight path/policy checks can still run and record blocked status;
        # credential errors remain separate and write nothing.
        token = None

    def _blocked(reason: str, *, observations: list[LiveObservation] | None = None) -> None:
        if output_root is None:
            return
        _write_status_artifact(
            plan=plan,
            run_id=run_id,
            output_root=Path(output_root),
            command=cmd,
            status="blocked",
            reason=scrub_secrets(reason, secrets),
            secrets=secrets,
            observations=observations or [],
            evidence={"rejected_redirect_or_safety": True},
            allow_mutation=allow_mutation,
        )

    try:
        for request in plan.requests:
            validate_request(plan, request, allow_mutation)
    except SafetyRejectionError as exc:
        _blocked(str(exc))
        raise SafetyRejectionError(scrub_secrets(str(exc), secrets)) from None

    if token is None:
        raise MissingCredentialsError(
            f"missing credentials: environment variable {plan.token_env} is not set"
        )

    headers = _provider_headers(plan, token)

    observations: list[LiveObservation] = []
    exchanges: list[CapturedExchange] = []

    try:
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS),
        ) as client:
            for index, request in enumerate(plan.requests):
                try:
                    observation, exchange = await _execute_request(
                        client, plan, request, headers, index, run_id, secrets
                    )
                except SafetyRejectionError as exc:
                    scrubbed = scrub_secrets(str(exc), secrets)
                    _blocked(scrubbed, observations=observations)
                    raise SafetyRejectionError(scrubbed) from None
                observations.append(observation)
                exchanges.append(exchange)

        report = analyze_run(run_id, _target_from_plan(plan), exchanges)

        if output_root is not None:
            _write_live_artifacts(
                plan=plan,
                run_id=run_id,
                observations=observations,
                report=report,
                exchanges=exchanges,
                output_root=Path(output_root),
                command=cmd,
                allow_mutation=allow_mutation,
                secrets=secrets,
            )

        return observations, report
    except RequestFailureError as exc:
        if output_root is not None:
            _write_status_artifact(
                plan=plan,
                run_id=run_id,
                output_root=Path(output_root),
                command=cmd,
                status="failed",
                reason=scrub_secrets(str(exc), secrets),
                secrets=secrets,
                observations=observations,
                allow_mutation=allow_mutation,
            )
        raise
    except httpx.HTTPError as exc:
        if output_root is not None:
            _write_status_artifact(
                plan=plan,
                run_id=run_id,
                output_root=Path(output_root),
                command=cmd,
                status="failed",
                reason=scrub_secrets(str(exc), secrets),
                secrets=secrets,
                observations=observations,
                allow_mutation=allow_mutation,
            )
        raise


def _write_live_artifacts(
    *,
    plan: LivePlan,
    run_id: str,
    observations: list[LiveObservation],
    report: RunReport,
    exchanges: list[CapturedExchange],
    output_root: Path,
    command: list[str],
    allow_mutation: bool,
    secrets: list[str],
) -> None:
    provenance = collect_provenance(command)
    configuration = scrub_secrets(
        redact_secrets(
            {
                "plan_id": plan.id,
                "provider": plan.provider,
                "environment": plan.environment,
                "base_url": str(plan.base_url),
                "allowed_hosts": sorted(plan.allowed_hosts),
                "token_env": plan.token_env,
                "expected_endpoints": plan.expected_endpoints,
                "sensitive_markers": plan.sensitive_markers,
                "allow_mutation": allow_mutation,
                "request_count": len(plan.requests),
                "run_status": "completed",
            }
        ),
        secrets,
    )
    raw_payload = scrub_secrets(
        redact_secrets(
            {
                "run_id": run_id,
                "status": "completed",
                "observations": [o.model_dump(mode="json") for o in observations],
                "exchanges": [e.model_dump(mode="json") for e in exchanges],
                "report": report.model_dump(mode="json"),
            }
        ),
        secrets,
    )
    raw_path = _resolve_under_root(output_root, "raw", "live", plan.id, f"{run_id}.json")
    _write_artifact_exclusive(
        raw_path,
        ArtifactEnvelope(
            provenance=provenance,
            experiment="live",
            configuration=configuration if isinstance(configuration, dict) else {},
            payload=raw_payload if isinstance(raw_payload, dict) else {},
        ),
    )
    derived_path = _resolve_under_root(
        output_root, "derived", f"live_{plan.id}_{run_id}.json"
    )
    derived_payload = scrub_secrets(
        redact_secrets(report.model_dump(mode="json")), secrets
    )
    # Derived may overwrite via write_artifact historically; prefer exclusive too.
    _write_artifact_exclusive(
        derived_path,
        ArtifactEnvelope(
            provenance=collect_provenance(command),
            experiment="live",
            configuration=configuration if isinstance(configuration, dict) else {},
            payload=derived_payload if isinstance(derived_payload, dict) else {},
        ),
    )


def dry_run_plan(plan: LivePlan, allow_mutation: bool = False) -> list[str]:
    lines: list[str] = []
    for request in plan.requests:
        validate_request(plan, request, allow_mutation)
        url = resolve_request_url(plan, request)
        lines.append(f"{request.method} {url}")
    return lines


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _dispatch(args)
    except MissingCredentialsError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_MISSING_CREDS
    except SafetyRejectionError as exc:
        # Message should already be scrubbed at raise sites when secrets are known.
        print(str(exc), file=sys.stderr)
        return EXIT_SAFETY
    except (RequestFailureError, httpx.HTTPError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILURE


def _dispatch(args: list[str]) -> int:
    if not args or args[0] in {"-h", "--help"}:
        print(
            "Usage: python -m ait.live_runner run --plan PATH "
            "[--output-root DIR] [--dry-run] [--allow-mutation]"
        )
        return EXIT_FAILURE
    if args[0] != "run":
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        return EXIT_FAILURE

    import argparse

    parser = argparse.ArgumentParser(prog="ait.live_runner")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("results"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-mutation", action="store_true")
    parser.add_argument(
        "--store-bodies",
        action="store_true",
        help="Disabled: refused unless synthetic sandbox mode is implemented",
    )
    parsed = parser.parse_args(args[1:])

    plan = load_live_plan(parsed.plan)
    if parsed.dry_run:
        for line in dry_run_plan(plan, allow_mutation=parsed.allow_mutation):
            print(line)
        return EXIT_OK

    async def _run() -> tuple[list[LiveObservation], RunReport]:
        return await execute_live_plan(
            plan,
            allow_mutation=parsed.allow_mutation,
            store_bodies=parsed.store_bodies,
            output_root=parsed.output_root,
            command=["python", "-m", "ait.live_runner", *args],
        )

    observations, report = anyio.run(_run)
    print(f"run_id={report.run_id} status={report.status} observations={len(observations)}")
    return EXIT_OK


@app.command("run")
def run_command(
    plan: Path = typer.Option(..., "--plan", exists=True, readable=True),
    output_root: Path = typer.Option(Path("results"), "--output-root"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    allow_mutation: bool = typer.Option(False, "--allow-mutation"),
    store_bodies: bool = typer.Option(False, "--store-bodies"),
) -> None:
    argv = ["run", "--plan", str(plan), "--output-root", str(output_root)]
    if dry_run:
        argv.append("--dry-run")
    if allow_mutation:
        argv.append("--allow-mutation")
    if store_bodies:
        argv.append("--store-bodies")
    raise typer.Exit(main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
