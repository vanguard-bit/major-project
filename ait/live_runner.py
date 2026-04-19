from __future__ import annotations

import json
import os
import time
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from ait.analysis import analyze_run
from ait.models import (
    CapturedExchange,
    Finding,
    FindingCategory,
    RunRecord,
    Severity,
    TargetConfig,
    TestRunConfig,
)


class LiveRequestSpec(BaseModel):
    name: str
    phase: str = "baseline"
    method: str = "GET"
    path: str
    expected_http: list[int] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | list[Any] | None = None
    form_body: dict[str, Any] | None = None
    expected_behavior: str = "allowed"


class LiveScenario(BaseModel):
    target: TargetConfig
    requests: list[LiveRequestSpec]
    auth_env_var: str
    auth_scheme: str = "Bearer"
    allowed_status_prefixes: list[int] = Field(default_factory=lambda: [2])
    timeout_seconds: int = 20
    follow_redirects: bool = True


def _flatten_field_names(payload: Any) -> set[str]:
    fields: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            fields.add(str(key))
            fields.update(_flatten_field_names(value))
    elif isinstance(payload, list):
        for item in payload:
            fields.update(_flatten_field_names(item))
    return fields


def _contains_marker(payload: Any, markers: list[str]) -> bool:
    if not markers:
        return False
    haystack = json.dumps(payload, sort_keys=True) if isinstance(payload, (dict, list)) else str(payload)
    return any(marker in haystack for marker in markers)


def _normalize_path(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _path_for_analysis(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        parsed = httpx.URL(path)
        return parsed.path or "/"
    return path if path.startswith("/") else f"/{path}"


async def run_live_assessment(scenario: LiveScenario, config: TestRunConfig | None = None) -> RunRecord:
    config = config or TestRunConfig()
    token = os.getenv(scenario.auth_env_var)
    if not token:
        raise ValueError(f"Missing auth token in environment variable {scenario.auth_env_var}")

    run_id = uuid4().hex[:12]
    exchanges: list[CapturedExchange] = []
    base_headers = {"Authorization": f"{scenario.auth_scheme} {token}"}

    exchange_specs: list[tuple[CapturedExchange, LiveRequestSpec]] = []

    async with httpx.AsyncClient(
        timeout=scenario.timeout_seconds,
        follow_redirects=scenario.follow_redirects,
    ) as client:
        for request_spec in scenario.requests:
            url = _normalize_path(str(scenario.target.base_url), request_spec.path)
            headers = {**base_headers, **request_spec.headers}
            started = time.perf_counter()
            response = await client.request(
                request_spec.method,
                url,
                params=request_spec.params or None,
                headers=headers,
                json=request_spec.json_body,
                data=request_spec.form_body,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            try:
                response_body: Any = response.json()
            except ValueError:
                response_body = response.text

            fields = sorted(_flatten_field_names(response_body))
            contains_sensitive_marker = _contains_marker(response_body, scenario.target.sensitive_markers)
            exchange = CapturedExchange(
                run_id=run_id,
                phase=request_spec.phase,
                method=request_spec.method.upper(),
                path=_path_for_analysis(request_spec.path),
                status_code=response.status_code,
                request_headers={key: value for key, value in headers.items() if key.lower() != "authorization"},
                request_body=request_spec.json_body or request_spec.form_body,
                response_body={
                    "status_code": response.status_code,
                    "latency_ms": elapsed_ms,
                    "body": response_body,
                },
                extracted_fields=fields,
                contains_sensitive_marker=contains_sensitive_marker,
            )
            exchanges.append(exchange)
            exchange_specs.append((exchange, request_spec))

    report = analyze_run(run_id, scenario.target, exchanges)
    policy_findings: list[Finding] = []
    for exchange, request_spec in exchange_specs:
        if request_spec.expected_http and exchange.status_code not in request_spec.expected_http:
            expected_codes = ", ".join(str(code) for code in request_spec.expected_http)
            if request_spec.expected_behavior == "denied":
                title = "Expected denial was not enforced"
                category = FindingCategory.POLICY_VIOLATION
                severity = Severity.HIGH
                remediation = "Tighten integration scopes or server-side authorization checks for this operation."
                expected_behavior = f"Request should be denied with one of: {expected_codes}."
            else:
                title = "Expected allowed request did not succeed"
                category = FindingCategory.POLICY_VIOLATION
                severity = Severity.MEDIUM
                remediation = "Verify token scopes, workspace sharing, and API request construction."
                expected_behavior = f"Request should succeed with one of: {expected_codes}."
            policy_findings.append(
                Finding(
                    severity=severity,
                    category=category,
                    endpoint=exchange.path,
                    title=title,
                    evidence=(
                        f"{request_spec.method.upper()} {exchange.path} returned {exchange.status_code}, "
                        f"expected {expected_codes}."
                    ),
                    expected_behavior=expected_behavior,
                    observed_behavior=f"Observed HTTP {exchange.status_code} during {request_spec.phase} phase.",
                    remediation_note=remediation,
                )
            )

    if policy_findings:
        report = report.model_copy(
            update={
                "findings": report.findings + policy_findings,
                "risk_score": min(100, report.risk_score + 30 * len(policy_findings)),
            }
        )
    return RunRecord(
        run_id=run_id,
        status="completed",
        target=scenario.target,
        config=config,
        findings=report.findings,
        exchanges=exchanges,
        report=report,
    )
