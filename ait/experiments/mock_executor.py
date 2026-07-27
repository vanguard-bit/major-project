from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from ait.analysis import analyze_run, extract_field_paths, field_matches_sensitive_marker
from ait.experiments.schema import ExchangeSpec, ScenarioDefinition, ScenarioOutcome
from ait.models import CapturedExchange


def _request_path(request: httpx.Request) -> str:
    parsed = urlparse(str(request.url))
    path = parsed.path or "/"
    if parsed.query:
        from ait.experiments.scenario_loader import normalize_path

        return normalize_path(f"{path}?{parsed.query}")
    return path


def scripted_transport_handler(
    pending: list[ExchangeSpec],
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if not pending:
            raise ValueError(f"unexpected extra request: {request.method} {_request_path(request)}")
        expected = pending.pop(0)
        actual_path = _request_path(request)
        if request.method.upper() != expected.method or actual_path != expected.path:
            raise ValueError(
                "exchange mismatch: "
                f"expected {expected.method} {expected.path}, "
                f"got {request.method.upper()} {actual_path}"
            )
        body = expected.response_body
        if isinstance(body, (dict, list)):
            return httpx.Response(expected.status_code, json=body)
        if body is None:
            return httpx.Response(expected.status_code, content=b"")
        return httpx.Response(expected.status_code, text=str(body))

    return handler


def _parse_response_body(response: httpx.Response) -> dict[str, Any] | list[Any] | str | None:
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    text = response.text
    try:
        return response.json()
    except ValueError:
        return text


def _parse_request_body(request: httpx.Request) -> dict[str, Any] | list[Any] | str | None:
    content = request.content
    if not content:
        return None
    content_type = request.headers.get("content-type", "")
    text = content.decode("utf-8", errors="replace")
    if "application/json" in content_type:
        return json.loads(text)
    try:
        return json.loads(text)
    except ValueError:
        return text


def _request_headers(request: httpx.Request) -> dict[str, str]:
    return {key: value for key, value in request.headers.items()}


async def execute_scenario(scenario: ScenarioDefinition) -> ScenarioOutcome:
    run_id = scenario.id
    pending = list(scenario.exchanges)
    transport = httpx.MockTransport(scripted_transport_handler(pending))
    target = scenario.target.to_target_config()
    markers = set(target.sensitive_markers)
    captured: list[CapturedExchange] = []

    async with httpx.AsyncClient(
        transport=transport,
        base_url=str(scenario.target.base_url),
    ) as client:
        for spec in scenario.exchanges:
            kwargs: dict[str, Any] = {}
            if spec.request_body is not None:
                if isinstance(spec.request_body, (dict, list)):
                    kwargs["json"] = spec.request_body
                else:
                    kwargs["content"] = str(spec.request_body)
            response = await client.request(spec.method, spec.path, **kwargs)
            request = response.request
            response_body = _parse_response_body(response)
            extracted = sorted(extract_field_paths(response_body))
            contains_sensitive = any(
                field_matches_sensitive_marker(field, markers) for field in extracted
            )
            captured.append(
                CapturedExchange(
                    run_id=run_id,
                    phase=spec.phase,
                    method=request.method.upper(),
                    path=_request_path(request),
                    status_code=response.status_code,
                    request_headers=_request_headers(request),
                    request_body=_parse_request_body(request),
                    response_body=response_body,
                    extracted_fields=extracted,
                    contains_sensitive_marker=contains_sensitive,
                )
            )

    report = analyze_run(run_id, target, captured)
    expected_categories = {label.category for label in scenario.expected_labels}
    observed_categories = {finding.category for finding in report.findings}
    return ScenarioOutcome(
        scenario_id=scenario.id,
        expected_categories=expected_categories,
        observed_categories=observed_categories,
        report=report,
        exchanges=captured,
        expected_labels=list(scenario.expected_labels),
        target=scenario.target,
    )


__all__ = ["execute_scenario", "scripted_transport_handler"]
