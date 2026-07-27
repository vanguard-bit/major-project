from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

import anyio
import httpx
import typer
import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator

from ait.analysis import analyze_run, extract_field_paths
from ait.artifacts import ArtifactEnvelope, collect_provenance, redact_secrets, write_artifact
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

HEADER_ALLOWLIST = frozenset(
    {
        "content-type",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "retry-after",
        "x-github-request-id",
        "x-notion-request-id",
        "x-request-id",
        "request-id",
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
    method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    phase: Literal["baseline", "mutated"] = "baseline"
    json_body: dict[str, Any] | None = None


class LivePlan(BaseModel):
    schema_version: Literal["1.0.0"]
    id: str
    provider: Literal["github", "notion"]
    environment: Literal["sandbox", "production-readonly"]
    base_url: HttpUrl
    allowed_hosts: set[str]
    token_env: str
    expected_endpoints: list[str]
    sensitive_markers: list[str]
    requests: list[LiveRequestSpec] = Field(max_length=MAX_REQUESTS_PER_RUN)

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


def resolve_request_url(plan: LivePlan, request: LiveRequestSpec) -> httpx.URL:
    raw = request.path
    if raw.startswith("//"):
        raise SafetyRejectionError("protocol-relative paths are not allowed")
    if "#" in raw:
        raise SafetyRejectionError("URL fragments are not allowed")
    path_only = raw.split("?", 1)[0]
    if ".." in path_only.split("/"):
        raise SafetyRejectionError("path traversal ('..') is not allowed")

    if "://" in raw:
        url = httpx.URL(raw)
    else:
        base = str(plan.base_url)
        if not base.endswith("/"):
            base = base + "/"
        url = httpx.URL(urljoin(base, raw.lstrip("/")))

    if url.scheme != "https":
        raise SafetyRejectionError(f"scheme '{url.scheme}' is not allowed; only https")
    if url.username or url.password:
        raise SafetyRejectionError("userinfo/credentials in URLs are not allowed")
    if url.fragment:
        raise SafetyRejectionError("URL fragments are not allowed")
    host = url.host
    if host is None or host not in plan.allowed_hosts:
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
        if lowered in HEADER_ALLOWLIST or lowered.endswith("-request-id"):
            selected[lowered] = value
    return selected


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


def _retry_after_seconds(headers: httpx.Headers) -> float:
    raw = headers.get("retry-after")
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise SafetyRejectionError(f"invalid Retry-After header: {raw!r}") from exc
    if value > MAX_RETRY_AFTER_SECONDS:
        raise SafetyRejectionError(
            f"Retry-After {value} exceeds maximum of {MAX_RETRY_AFTER_SECONDS}s"
        )
    return max(0.0, value)


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


async def _execute_request(
    client: httpx.AsyncClient,
    plan: LivePlan,
    request: LiveRequestSpec,
    headers: dict[str, str],
    index: int,
    run_id: str,
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
            await response.aclose()
            raise SafetyRejectionError(
                f"redirect not followed: status={response.status_code} location={location}"
            )

        if response.status_code in RETRYABLE_STATUS:
            if attempt > MAX_RETRIES:
                body = await _read_body_limited(response)
                await response.aclose()
                break
            delay = _retry_after_seconds(response.headers)
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
    selected = select_headers(response.headers)
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
        status_code=response.status_code,
        response_bytes=len(body),
        response_sha256=digest,
        response_fields=fields,
        selected_headers=selected,
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


async def execute_live_plan(
    plan: LivePlan,
    *,
    allow_mutation: bool = False,
    store_bodies: bool = False,
    transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    output_root: Path | None = None,
    command: list[str] | None = None,
) -> tuple[list[LiveObservation], RunReport]:
    if store_bodies:
        raise SafetyRejectionError(
            "--store-bodies is only permitted for approved synthetic sandbox data"
        )

    if len(plan.requests) > MAX_REQUESTS_PER_RUN:
        raise SafetyRejectionError(
            f"plan exceeds maximum of {MAX_REQUESTS_PER_RUN} requests per run"
        )

    for request in plan.requests:
        validate_request(plan, request, allow_mutation)

    token = _read_token(plan)
    headers = _provider_headers(plan, token)
    run_suffix = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{plan.id}-{run_suffix}"

    observations: list[LiveObservation] = []
    exchanges: list[CapturedExchange] = []

    async with httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,
        timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS),
    ) as client:
        for index, request in enumerate(plan.requests):
            observation, exchange = await _execute_request(
                client, plan, request, headers, index, run_id
            )
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
            command=command or ["python", "-m", "ait.live_runner"],
            allow_mutation=allow_mutation,
        )

    return observations, report


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
) -> None:
    provenance = collect_provenance(command)
    configuration = redact_secrets(
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
        }
    )
    raw_payload = redact_secrets(
        {
            "run_id": run_id,
            "observations": [o.model_dump(mode="json") for o in observations],
            "exchanges": [e.model_dump(mode="json") for e in exchanges],
            "report": report.model_dump(mode="json"),
        }
    )
    raw_path = output_root / "raw" / "live" / plan.id / f"{run_id}.json"
    write_artifact(
        raw_path,
        ArtifactEnvelope(
            provenance=provenance,
            experiment="live",
            configuration=configuration,
            payload=raw_payload,
        ),
    )
    derived_path = output_root / "derived" / f"live_{plan.id}_{run_id}.json"
    write_artifact(
        derived_path,
        ArtifactEnvelope(
            provenance=collect_provenance(command),
            experiment="live",
            configuration=configuration,
            payload=redact_secrets(report.model_dump(mode="json")),
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
    parser.add_argument("--store-bodies", action="store_true")
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
