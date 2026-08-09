"""Demo-gated live evidence listing and paste-token probe endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ait.live_runner import (
    MissingCredentialsError,
    RequestFailureError,
    SafetyRejectionError,
    execute_live_plan,
    load_live_plan,
)
from ait.models import Finding

REPO_ROOT = Path(__file__).resolve().parent.parent

PLAN_FILES: dict[tuple[str, str], Path] = {
    ("github", "smoke"): Path("configs/live/github_smoke.yaml"),
    ("github", "readonly"): Path("configs/live/github_readonly.yaml"),
    ("github", "smoke-extended"): Path("configs/live/github_smoke_extended.yaml"),
    ("google", "smoke"): Path("configs/live/google_smoke.yaml"),
    ("google", "readonly"): Path("configs/live/google_readonly.yaml"),
    ("google", "smoke-extended"): Path("configs/live/google_smoke_extended.yaml"),
    ("notion", "readonly"): Path("configs/live/notion_readonly.yaml"),
}

router = APIRouter(prefix="/live", tags=["live-demo"])


class LiveProbeRequest(BaseModel):
    provider: Literal["github", "google", "notion"]
    plan: Literal["smoke", "readonly", "smoke-extended"]
    token: str = Field(min_length=1)


class LiveProbeResponse(BaseModel):
    run_id: str
    provider: str
    plan_id: str
    status: str
    risk_score: float
    hidden_endpoints: list[str]
    reached_endpoints: list[str]
    findings: list[Finding]


class LiveEvidenceRow(BaseModel):
    platform: str
    scenario: str
    risk_score: float
    result: str
    run_id: str
    plan_id: str
    hidden_endpoints: list[str]
    reached_endpoints: list[str]
    findings: list[dict[str, Any]]


def demo_live_enabled(request: Request) -> bool:
    if os.environ.get("AIT_DEMO_LIVE_PROBES") != "1":
        return False
    host = (request.headers.get("host") or "").split(":")[0].lower()
    return host in {"localhost", "127.0.0.1"}


def _require_demo(request: Request) -> None:
    if not demo_live_enabled(request):
        raise HTTPException(status_code=404, detail="Not Found")


def _result_summary(hidden: list[str], risk: float) -> str:
    if not hidden and risk == 0:
        return "clean"
    if hidden:
        return "hidden " + ", ".join(hidden)
    return f"risk {risk}"


def load_evidence_rows(derived_root: Path) -> list[LiveEvidenceRow]:
    rows: list[LiveEvidenceRow] = []
    if not derived_root.is_dir():
        return rows
    for path in sorted(derived_root.glob("live_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        conf = doc.get("configuration") or {}
        payload = doc.get("payload") or {}
        status = payload.get("status") or conf.get("run_status")
        if status not in {None, "completed"}:
            continue
        provider = str(conf.get("provider") or "unknown")
        plan_id = str(conf.get("plan_id") or payload.get("target_name") or path.stem)
        scenario = plan_id.split("-", 1)[1] if "-" in plan_id else plan_id
        hidden = list(payload.get("hidden_endpoints") or [])
        risk = float(payload.get("risk_score") or 0.0)
        run_id = str(payload.get("run_id") or path.stem)
        findings = payload.get("findings") or []
        if not isinstance(findings, list):
            findings = []
        rows.append(
            LiveEvidenceRow(
                platform=provider.title() if provider.islower() else str(provider),
                scenario=scenario,
                risk_score=risk,
                result=_result_summary(hidden, risk),
                run_id=run_id,
                plan_id=plan_id,
                hidden_endpoints=hidden,
                reached_endpoints=list(payload.get("reached_endpoints") or []),
                findings=findings,
            )
        )
    return rows


@router.get("/evidence", response_model=list[LiveEvidenceRow])
async def get_live_evidence(request: Request) -> list[LiveEvidenceRow]:
    _require_demo(request)
    derived = REPO_ROOT / "results" / "derived"
    return load_evidence_rows(derived)


@router.post("/probes", response_model=LiveProbeResponse)
async def post_live_probe(request: Request, body: LiveProbeRequest) -> LiveProbeResponse:
    _require_demo(request)
    key = (body.provider, body.plan)
    rel = PLAN_FILES.get(key)
    if rel is None:
        raise HTTPException(status_code=422, detail="Unknown provider/plan combination")
    plan_path = REPO_ROOT / rel
    if not plan_path.is_file():
        raise HTTPException(status_code=404, detail="Plan file not found")

    try:
        plan = load_live_plan(plan_path)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid plan") from exc

    try:
        _observations, report = await execute_live_plan(
            plan,
            token=body.token,
            output_root=REPO_ROOT / "results",
            command=[
                "python",
                "-m",
                "ait.api",
                "POST",
                "/live/probes",
                f"{body.provider}/{body.plan}",
            ],
        )
    except MissingCredentialsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except SafetyRejectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except (RequestFailureError, OSError, ValueError) as exc:
        message = str(exc)
        if body.token and body.token in message:
            message = message.replace(body.token, "[REDACTED]")
        raise HTTPException(status_code=502, detail=message) from None

    return LiveProbeResponse(
        run_id=report.run_id,
        provider=body.provider,
        plan_id=plan.id,
        status=report.status,
        risk_score=report.risk_score,
        hidden_endpoints=list(report.hidden_endpoints),
        reached_endpoints=list(report.reached_endpoints),
        findings=list(report.findings),
    )
