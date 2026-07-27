from __future__ import annotations

from uuid import uuid4

import httpx

from ait.analysis import analyze_run
from ait.models import CapturedExchange, RunRecord, TargetConfig, TestRunConfig


async def _resolve_token(target: TargetConfig) -> str:
    if target.auth_type.value == "static_token":
        return target.token_config.token or ""
    if not target.token_config.token_url:
        raise ValueError("OAuth token URL is required for oauth_client_credentials targets.")
    payload = {
        "grant_type": "client_credentials",
        "client_id": target.token_config.client_id,
        "client_secret": target.token_config.client_secret,
        "scope": target.token_config.scope or "",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(str(target.token_config.token_url), json=payload)
        response.raise_for_status()
        body = response.json()
    return body["access_token"]


async def _post_seed(target: TargetConfig, run_id: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{target.audit_base_url}admin/seed",
            json={"run_id": run_id, "sensitive_markers": target.sensitive_markers},
        )
        response.raise_for_status()


async def _invoke_integration(
    target: TargetConfig,
    run_id: str,
    phase: str,
    token: str,
) -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            str(target.integration_sync_url),
            json={"run_id": run_id, "phase": phase, "token": token},
        )
        response.raise_for_status()


async def _fetch_audit_log(target: TargetConfig, run_id: str) -> list[CapturedExchange]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{target.audit_base_url}admin/audit/{run_id}")
        response.raise_for_status()
        payload = response.json()
    return [CapturedExchange.model_validate(item) for item in payload["entries"]]


async def run_assessment(target: TargetConfig, config: TestRunConfig) -> RunRecord:
    run_id = uuid4().hex[:12]
    token = await _resolve_token(target)
    await _post_seed(target, run_id)
    await _invoke_integration(target, run_id, "baseline", token)
    await _invoke_integration(target, run_id, "mutated", token)
    exchanges = await _fetch_audit_log(target, run_id)
    report = analyze_run(run_id, target, exchanges)
    return RunRecord(
        run_id=run_id,
        status="completed",
        target=target,
        config=config,
        findings=report.findings,
        exchanges=exchanges,
        report=report,
    )
