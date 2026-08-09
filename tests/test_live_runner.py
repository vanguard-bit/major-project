from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from pydantic import ValidationError

from ait.live_runner import (
    EXIT_MISSING_CREDS,
    EXIT_OK,
    EXIT_SAFETY,
    LivePlan,
    MissingCredentialsError,
    RequestFailureError,
    SafetyRejectionError,
    execute_live_plan,
    load_live_plan,
    main,
    validate_request,
)


def _minimal_plan(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "1.0.0",
        "id": "test-plan",
        "provider": "github",
        "environment": "sandbox",
        "base_url": "https://api.github.com",
        "allowed_hosts": ["api.github.com"],
        "token_env": "AIT_TEST_TOKEN",
        "expected_endpoints": ["/user"],
        "sensitive_markers": [],
        "requests": [{"method": "GET", "path": "/user"}],
    }
    base.update(overrides)
    return base


def _write_plan(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# --- Task 1: Safety guard ---------------------------------------------------


def test_load_live_plan_round_trip(tmp_path: Path) -> None:
    path = _write_plan(tmp_path, _minimal_plan())
    plan = load_live_plan(path)
    assert plan.id == "test-plan"
    assert plan.provider == "github"
    assert plan.requests[0].method == "GET"


def test_reject_non_allowlisted_host(tmp_path: Path) -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "https://evil.example/user"}])
    )
    with pytest.raises(SafetyRejectionError, match="host"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_scheme_change() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "http://api.github.com/user"}])
    )
    with pytest.raises(SafetyRejectionError, match="scheme"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_userinfo_in_url() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(
            requests=[{"method": "GET", "path": "https://user:pass@api.github.com/user"}]
        )
    )
    with pytest.raises(SafetyRejectionError, match="userinfo|user-info|credentials"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_fragment() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user#frag"}])
    )
    with pytest.raises(SafetyRejectionError, match="fragment"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_protocol_relative_path() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "//evil.example/user"}])
    )
    with pytest.raises(SafetyRejectionError, match="protocol-relative|host"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_path_traversal() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user/../admin"}])
    )
    with pytest.raises(SafetyRejectionError, match=r"\.\.|traversal"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_more_than_20_requests() -> None:
    requests = [{"method": "GET", "path": f"/user/{i}"} for i in range(21)]
    with pytest.raises((SafetyRejectionError, ValidationError), match="20"):
        LivePlan.model_validate(_minimal_plan(requests=requests))


def test_live_plan_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LivePlan.model_validate(_minimal_plan(unexpected_field=True))
    with pytest.raises(ValidationError):
        LivePlan.model_validate(
            _minimal_plan(requests=[{"method": "GET", "path": "/user", "extra": 1}])
        )


def test_live_plan_requires_at_least_one_request() -> None:
    with pytest.raises(ValidationError):
        LivePlan.model_validate(_minimal_plan(requests=[]))


def test_reject_mutation_without_allow_flag() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(
            environment="sandbox",
            requests=[{"method": "POST", "path": "/user", "json_body": {}}],
        )
    )
    with pytest.raises(SafetyRejectionError, match="mutation"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_mutation_in_production_even_with_flag() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(
            environment="production-readonly",
            requests=[{"method": "POST", "path": "/user", "json_body": {}}],
        )
    )
    with pytest.raises(SafetyRejectionError, match="sandbox|mutation"):
        validate_request(plan, plan.requests[0], allow_mutation=True)


def test_allow_mutation_in_sandbox_with_flag() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(
            environment="sandbox",
            requests=[{"method": "POST", "path": "/user", "json_body": {"ok": True}}],
        )
    )
    validate_request(plan, plan.requests[0], allow_mutation=True)


def test_query_retained_but_identity_is_normalized_path() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(
            expected_endpoints=["/user/repos"],
            requests=[
                {
                    "method": "GET",
                    "path": "/user/repos?per_page=1&page=2",
                }
            ],
        )
    )
    validate_request(plan, plan.requests[0], allow_mutation=False)
    from ait.live_runner import normalize_endpoint_path

    assert normalize_endpoint_path("/user/repos?per_page=1&page=2") == "/user/repos"


@pytest.mark.anyio
async def test_redirects_are_recorded_and_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "secret-token-value")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://api.github.com/elsewhere"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with pytest.raises(SafetyRejectionError, match="redirect"):
        await execute_live_plan(plan, allow_mutation=False, transport=transport)


@pytest.mark.anyio
async def test_token_never_appears_in_logs_or_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "ghp_SUPER_SECRET_TOKEN_DO_NOT_LEAK"
    monkeypatch.setenv("AIT_TEST_TOKEN", token)
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"login": "alice", "token": "should-not-store-value"},
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {token}",
                "set-cookie": "session=bad",
                "x-ratelimit-remaining": "4999",
                "x-github-request-id": "abc-123",
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with caplog.at_level(logging.DEBUG):
        observations, report = await execute_live_plan(
            plan,
            allow_mutation=False,
            transport=transport,
            output_root=tmp_path,
            command=["ait.live_runner", "run"],
        )

    blob = json.dumps(
        {
            "obs": [o.model_dump(mode="json") for o in observations],
            "report": report.model_dump(mode="json"),
            "logs": caplog.text,
            "repr_obs": repr(observations),
        }
    )
    assert token not in blob
    assert "ghp_SUPER" not in blob
    assert "set-cookie" not in blob.lower() or "set-cookie" not in str(
        observations[0].selected_headers
    ).lower()
    assert "authorization" not in {k.lower() for k in observations[0].selected_headers}
    assert observations[0].selected_headers.get("x-ratelimit-remaining") == "4999"
    assert observations[0].selected_headers.get("x-github-request-id") == "abc-123"

    raw_files = list((tmp_path / "raw" / "live").rglob("*.json"))
    assert raw_files
    raw_text = raw_files[0].read_text(encoding="utf-8")
    assert token not in raw_text
    assert "should-not-store-value" not in raw_text


# --- Task 2: Guarded HTTP execution -----------------------------------------


@pytest.mark.anyio
async def test_success_extracts_fields_without_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer tok"
        assert request.url.path == "/user"
        return httpx.Response(
            200,
            json={"login": "alice", "billing": {"tax_id": "x"}},
            headers={"content-type": "application/json"},
            request=request,
        )

    observations, report = await execute_live_plan(
        plan, transport=httpx.MockTransport(handler)
    )
    assert len(observations) == 1
    fields = set(observations[0].response_fields)
    assert "login" in fields
    assert "billing" in fields or "billing.tax_id" in fields
    assert observations[0].status_code == 200
    assert report.status == "completed"
    assert "alice" not in observations[0].model_dump_json()


@pytest.mark.anyio
async def test_missing_credentials_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIT_TEST_TOKEN", raising=False)
    plan = LivePlan.model_validate(_minimal_plan())
    with pytest.raises(MissingCredentialsError):
        await execute_live_plan(plan, transport=httpx.MockTransport(lambda r: httpx.Response(200)))


@pytest.mark.anyio
async def test_retry_429_at_most_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(
                429,
                headers={"retry-after": "0"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr("ait.live_runner._sleep", _noop_sleep)
    observations, _ = await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    assert calls["n"] == 3
    assert observations[0].status_code == 200


@pytest.mark.anyio
async def test_retry_exhausted_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, headers={"retry-after": "0"}, request=request)

    monkeypatch.setattr("ait.live_runner._sleep", _noop_sleep)
    with pytest.raises(RequestFailureError):
        await execute_live_plan(plan, transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_retry_after_above_30_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())
    slept: list[float] = []

    async def capture_sleep(seconds: float) -> None:
        slept.append(seconds)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "31"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr("ait.live_runner._sleep", capture_sleep)
    observations, _ = await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    assert observations[0].status_code == 200
    assert slept == [30.0]


@pytest.mark.anyio
async def test_oversized_response_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())
    huge = b"x" * (1_048_576 + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=huge, request=request)

    with pytest.raises(SafetyRejectionError, match="MiB|size|byte"):
        await execute_live_plan(plan, transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_401_is_request_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad credentials"}, request=request)

    with pytest.raises(RequestFailureError) as excinfo:
        await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    assert "tok" not in str(excinfo.value)


@pytest.mark.anyio
async def test_timeout_is_request_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(httpx.TimeoutException):
        await execute_live_plan(plan, transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_sha256_and_byte_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())
    body = b'{"login":"alice"}'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "application/json"},
            request=request,
        )

    observations, _ = await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    assert observations[0].response_bytes == len(body)
    assert observations[0].response_sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.anyio
async def test_captured_exchange_response_body_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(
        _minimal_plan(
            expected_endpoints=["/user"],
            requests=[
                {"method": "GET", "path": "/user"},
                {"method": "GET", "path": "/user/repos?per_page=1"},
            ],
        )
    )
    paths_seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths_seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True}, request=request)

    observations, report = await execute_live_plan(
        plan, transport=httpx.MockTransport(handler)
    )
    assert paths_seen == ["/user", "/user/repos"]
    assert "/user/repos" in report.hidden_endpoints
    assert all(o.normalized_path in ("/user", "/user/repos") for o in observations)


# --- CLI / exit codes -------------------------------------------------------


def test_cli_dry_run_no_credentials_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AIT_TEST_TOKEN", raising=False)
    path = _write_plan(tmp_path, _minimal_plan())
    code = main(["run", "--plan", str(path), "--dry-run"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "GET" in out
    assert "https://api.github.com/user" in out


def test_cli_missing_credentials_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AIT_TEST_TOKEN", raising=False)
    path = _write_plan(tmp_path, _minimal_plan())
    code = main(["run", "--plan", str(path), "--output-root", str(tmp_path)])
    assert code == EXIT_MISSING_CREDS
    assert list(tmp_path.rglob("*.json")) == []


def test_cli_safety_rejection_exit_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    path = _write_plan(
        tmp_path,
        _minimal_plan(
            environment="production-readonly",
            requests=[{"method": "POST", "path": "/user"}],
        ),
    )
    code = main(
        [
            "run",
            "--plan",
            str(path),
            "--output-root",
            str(tmp_path),
            "--allow-mutation",
        ]
    )
    assert code == EXIT_SAFETY


async def _noop_sleep(_seconds: float) -> None:
    return None


# --- Phase 3 review regressions ---------------------------------------------


def test_reject_plan_id_path_traversal() -> None:
    with pytest.raises((SafetyRejectionError, ValidationError), match=r"id|slug|traversal|\.\."):
        LivePlan.model_validate(_minimal_plan(id="../evil"))


def test_reject_plan_id_with_separator() -> None:
    with pytest.raises((SafetyRejectionError, ValidationError), match=r"id|slug|separator|/"):
        LivePlan.model_validate(_minimal_plan(id="a/b"))


def test_reject_alternate_port() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(
            requests=[{"method": "GET", "path": "https://api.github.com:8443/user"}]
        )
    )
    with pytest.raises(SafetyRejectionError, match="port|origin"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_encoded_dot_dot_traversal() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user/%2e%2e/admin"}])
    )
    with pytest.raises(SafetyRejectionError, match=r"\.\.|traversal|encoded"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_backslash_in_path() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user\\admin"}])
    )
    with pytest.raises(SafetyRejectionError, match=r"backslash|\\\\|traversal"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_relative_path_without_leading_slash() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "user"}])
    )
    with pytest.raises(SafetyRejectionError, match=r"path|relative|slash"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_header_allowlist_rejects_generic_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ait.live_runner import select_headers

    headers = httpx.Headers(
        {
            "content-type": "application/json",
            "x-request-id": "generic-should-drop",
            "request-id": "also-drop",
            "x-custom-request-id": "wildcard-drop",
            "x-github-request-id": "keep-me",
            "authorization": "Bearer secret",
        }
    )
    selected = select_headers(headers)
    assert selected == {
        "content-type": "application/json",
        "x-github-request-id": "keep-me",
    }


@pytest.mark.anyio
async def test_secret_values_scrubbed_from_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token = "ghp_LIVE_SECRET_VALUE_XYZ"
    monkeypatch.setenv("AIT_TEST_TOKEN", token)
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"login": "alice", "note": f"echo {token}"},
            headers={
                "content-type": "application/json",
                "x-github-request-id": f"rid-{token}",
            },
            request=request,
        )

    await execute_live_plan(
        plan,
        transport=httpx.MockTransport(handler),
        output_root=tmp_path,
        command=["ait.live_runner", "run"],
    )
    for path in tmp_path.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert token not in text
        assert "ghp_LIVE_SECRET" not in text


@pytest.mark.anyio
async def test_redirect_location_sanitized_and_not_printed_raw(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    token = "tok_IN_LOCATION"
    monkeypatch.setenv("AIT_TEST_TOKEN", token)
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": f"https://api.github.com/callback?access_token={token}"},
            request=request,
        )

    with pytest.raises(SafetyRejectionError) as excinfo:
        await execute_live_plan(
            plan,
            transport=httpx.MockTransport(handler),
            output_root=tmp_path,
            command=["ait.live_runner", "run"],
        )
    assert token not in str(excinfo.value)
    # Status/evidence may be written, but must not contain the raw token.
    for path in tmp_path.rglob("*.json"):
        assert token not in path.read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_query_retained_in_request_target_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(
        _minimal_plan(
            expected_endpoints=["/user/repos"],
            requests=[{"method": "GET", "path": "/user/repos?per_page=1&page=2"}],
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    observations, _ = await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    assert observations[0].normalized_path == "/user/repos"
    target = getattr(observations[0], "request_target", None) or getattr(
        observations[0], "query", None
    )
    assert target is not None
    assert "per_page=1" in str(target)
    assert "page=2" in str(target)


@pytest.mark.anyio
async def test_retry_after_http_date_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())
    slept: list[float] = []

    async def capture_sleep(seconds: float) -> None:
        slept.append(seconds)

    future = datetime.now(tz=UTC) + timedelta(seconds=5)
    http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": http_date}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr("ait.live_runner._sleep", capture_sleep)
    await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    assert len(slept) == 1
    assert 0.0 <= slept[0] <= 30.0


@pytest.mark.anyio
async def test_run_id_uses_microseconds_or_uuid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    _, report_a = await execute_live_plan(
        plan, transport=httpx.MockTransport(handler), output_root=tmp_path
    )
    _, report_b = await execute_live_plan(
        plan, transport=httpx.MockTransport(handler), output_root=tmp_path
    )
    assert report_a.run_id != report_b.run_id
    # Second-precision suffix alone would collide; require finer grain or UUID.
    for run_id in (report_a.run_id, report_b.run_id):
        assert (
            "." in run_id.split("-")[-1]
            or len(run_id) > len(f"{plan.id}-20260101T000000Z")
            or "-" in run_id[len(plan.id) + 1 :]
        )


@pytest.mark.anyio
async def test_failed_run_writes_non_completed_status_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(_minimal_plan())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad"}, request=request)

    with pytest.raises(RequestFailureError):
        await execute_live_plan(
            plan,
            transport=httpx.MockTransport(handler),
            output_root=tmp_path,
            command=["ait.live_runner", "run"],
        )
    status_files = list(tmp_path.rglob("*.json"))
    assert status_files
    blob = "\n".join(p.read_text(encoding="utf-8") for p in status_files)
    assert '"status": "completed"' not in blob or '"run_status"' in blob
    assert any(
        marker in blob
        for marker in ('"failed"', '"blocked"', '"incomplete"', '"error"', '"aborted"')
    )


def test_cli_missing_credentials_exit_2_no_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AIT_TEST_TOKEN", raising=False)
    path = _write_plan(tmp_path, _minimal_plan())
    out = tmp_path / "out"
    out.mkdir()
    code = main(["run", "--plan", str(path), "--output-root", str(out)])
    assert code == EXIT_MISSING_CREDS
    assert list(out.rglob("*.json")) == []


# --- Remaining Phase 3 review gaps -----------------------------------------


def test_reject_double_encoded_dot_dot_traversal() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user/%252e%252e/admin"}])
    )
    with pytest.raises(SafetyRejectionError, match=r"\.\.|traversal|encoded"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


def test_reject_percent_decoded_control_chars() -> None:
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user/%00admin"}])
    )
    with pytest.raises(SafetyRejectionError, match=r"control|null|unsafe"):
        validate_request(plan, plan.requests[0], allow_mutation=False)


@pytest.mark.anyio
async def test_absolute_url_query_not_bytes_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    plan = LivePlan.model_validate(
        _minimal_plan(
            expected_endpoints=["/user/repos"],
            requests=[
                {
                    "method": "GET",
                    "path": "https://api.github.com/user/repos?per_page=1&page=2",
                }
            ],
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    observations, _ = await execute_live_plan(plan, transport=httpx.MockTransport(handler))
    target = observations[0].request_target
    assert "b'" not in target
    assert "per_page=1" in target
    assert "page=2" in target


@pytest.mark.anyio
async def test_invalid_retry_after_equal_to_token_is_scrubbed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from ait.live_runner import _retry_after_seconds

    token = "ghp_RETRY_AFTER_SECRET_TOKEN"
    monkeypatch.setenv("AIT_TEST_TOKEN", token)

    with pytest.raises(SafetyRejectionError) as unit_exc:
        _retry_after_seconds(httpx.Headers({"retry-after": token}), secrets=[token])
    assert token not in str(unit_exc.value)
    assert "[REDACTED]" in str(unit_exc.value)

    plan = LivePlan.model_validate(_minimal_plan())
    monkeypatch.setattr("ait.live_runner._sleep", _noop_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": token}, request=request)

    with pytest.raises(SafetyRejectionError) as excinfo:
        await execute_live_plan(
            plan,
            transport=httpx.MockTransport(handler),
            output_root=tmp_path,
            command=["ait.live_runner", "run"],
        )
    assert token not in str(excinfo.value)
    for path in tmp_path.rglob("*.json"):
        assert token not in path.read_text(encoding="utf-8")


def test_cli_prints_scrubbed_retry_after_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    token = "ghp_RETRY_AFTER_SECRET_TOKEN"
    monkeypatch.setenv("AIT_TEST_TOKEN", token)
    plan_path = _write_plan(tmp_path, _minimal_plan())

    async def _raise_scrubbed(*_args: Any, **_kwargs: Any) -> tuple[list[Any], Any]:
        raise SafetyRejectionError("invalid Retry-After header: '[REDACTED]'")

    monkeypatch.setattr("ait.live_runner.execute_live_plan", _raise_scrubbed)
    code = main(["run", "--plan", str(plan_path), "--output-root", str(tmp_path / "cli-out")])
    captured = capsys.readouterr()
    assert code == EXIT_SAFETY
    assert token not in captured.err
    assert token not in captured.out
    assert "[REDACTED]" in captured.err or "Retry-After" in captured.err


@pytest.mark.anyio
async def test_preflight_path_rejection_writes_blocked_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token = "unique-live-secret-value"
    monkeypatch.setenv("AIT_TEST_TOKEN", token)
    plan = LivePlan.model_validate(
        _minimal_plan(requests=[{"method": "GET", "path": "/user/../admin"}])
    )
    with pytest.raises(SafetyRejectionError):
        await execute_live_plan(
            plan,
            transport=httpx.MockTransport(lambda r: httpx.Response(200)),
            output_root=tmp_path,
            command=["ait.live_runner", "run"],
        )
    status_files = list(tmp_path.rglob("*.json"))
    assert status_files
    blob = "\n".join(p.read_text(encoding="utf-8") for p in status_files)
    assert '"blocked"' in blob
    assert token not in blob


def test_cli_preflight_safety_writes_blocked_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIT_TEST_TOKEN", "tok")
    out = tmp_path / "out"
    out.mkdir()
    path = _write_plan(
        tmp_path,
        _minimal_plan(
            environment="production-readonly",
            requests=[{"method": "POST", "path": "/user"}],
        ),
    )
    code = main(
        [
            "run",
            "--plan",
            str(path),
            "--output-root",
            str(out),
            "--allow-mutation",
        ]
    )
    assert code == EXIT_SAFETY
    blob = "\n".join(p.read_text(encoding="utf-8") for p in out.rglob("*.json"))
    assert blob
    assert '"blocked"' in blob


@pytest.mark.anyio
async def test_execute_live_plan_accepts_token_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory token override must not require plan.token_env."""
    monkeypatch.delenv("AIT_TEST_TOKEN", raising=False)
    plan = LivePlan.model_validate(_minimal_plan())
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(
            200,
            json={"login": "alice"},
            headers={"content-type": "application/json"},
            request=request,
        )

    observations, report = await execute_live_plan(
        plan,
        transport=httpx.MockTransport(handler),
        token="override-secret",
    )
    assert seen["authorization"] == "Bearer override-secret"
    assert len(observations) == 1
    assert report.status == "completed"
    assert "AIT_TEST_TOKEN" not in __import__("os").environ


@pytest.mark.anyio
async def test_execute_live_plan_rejects_blank_token_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AIT_TEST_TOKEN", raising=False)
    plan = LivePlan.model_validate(_minimal_plan())
    with pytest.raises(MissingCredentialsError, match="empty token"):
        await execute_live_plan(
            plan,
            transport=httpx.MockTransport(lambda r: httpx.Response(200)),
            token="   ",
        )
