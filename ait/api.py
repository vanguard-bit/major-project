from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from ait.models import RunRecord, TargetConfig, TestRunConfig
from ait.reporting import render_html_report
from ait.runner import run_assessment
from ait.store import store


DEMO_TARGET = TargetConfig.model_validate_json(
    """
{
  "name": "demo-integration",
  "environment": "demo",
  "base_url": "http://127.0.0.1:8001/",
  "integration_sync_url": "http://127.0.0.1:8002/sync",
  "audit_base_url": "http://127.0.0.1:8001/",
  "auth_type": "oauth_client_credentials",
  "token_config": {
    "token_url": "http://127.0.0.1:8001/oauth/token",
    "client_id": "demo-client",
    "client_secret": "demo-secret",
    "scope": "crm.read billing.read"
  },
  "openapi_paths": [
    "/api/v1/customers",
    "/api/v1/customers/{customer_id}",
    "/api/v1/customers/{customer_id}/notes"
  ],
  "seed_endpoints": [
    "/api/v1/customers",
    "/api/v1/customers/{customer_id}",
    "/api/v1/customers/{customer_id}/notes"
  ],
  "expected_endpoints": [
    "/api/v1/customers",
    "/api/v1/customers/cust-001",
    "/api/v1/customers/cust-001/notes"
  ],
  "expected_scopes": [
    "crm.read"
  ],
  "sensitive_markers": [
    "billing_email",
    "tax_id"
  ],
  "description": "Demo target with a hidden billing endpoint for validating detections."
}
"""
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.save_target(DEMO_TARGET)
    yield


app = FastAPI(title="Adversarial Integration Tester", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/targets")
async def list_targets() -> list[TargetConfig]:
    return list(store.list_targets())


@app.post("/targets")
async def create_target(target: TargetConfig) -> TargetConfig:
    return store.save_target(target)


@app.post("/runs")
async def create_run(payload: dict) -> RunRecord:
    try:
        target = store.get_target(payload["target_name"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown target") from exc
    config = TestRunConfig.model_validate(payload.get("config", {}))
    run = await run_assessment(target, config)
    return store.save_run(run)


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunRecord:
    try:
        return store.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown run") from exc


@app.get("/runs/{run_id}/findings")
async def get_findings(run_id: str):
    run = await get_run(run_id)
    return run.findings


@app.get("/runs/{run_id}/report")
async def get_report(run_id: str, format: str = "json"):
    try:
        run = store.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown run") from exc
    if run.report is None:
        raise HTTPException(status_code=409, detail="Run report not available")
    if format == "html":
        return Response(render_html_report(run.report), media_type="text/html")
    return run.report
