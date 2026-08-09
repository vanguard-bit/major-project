"""Demo-gated live evidence listing and paste-token probe endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ait.live_runner import (
    LiveObservation,
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
    ("notion", "smoke"): Path("configs/live/notion_smoke.yaml"),
    ("notion", "readonly"): Path("configs/live/notion_readonly.yaml"),
    ("notion", "smoke-extended"): Path("configs/live/notion_smoke_extended.yaml"),
}

router = APIRouter(prefix="/live", tags=["live-demo"])


class LiveProbeRequest(BaseModel):
    provider: Literal["github", "google", "notion"]
    plan: Literal["smoke", "readonly", "smoke-extended"]
    token: str = Field(min_length=1)


class HiddenEndpointResponse(BaseModel):
    """Observed response summary for a hidden endpoint (full body is not stored)."""

    path: str
    status_code: int
    response_bytes: int = 0
    response_fields: list[str] = Field(default_factory=list)
    content_type: str | None = None


class LiveProbeResponse(BaseModel):
    run_id: str
    provider: str
    plan_id: str
    status: str
    risk_score: float
    hidden_endpoints: list[str]
    reached_endpoints: list[str]
    findings: list[Finding]
    hidden_endpoint_responses: list[HiddenEndpointResponse] = Field(default_factory=list)


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
    hidden_endpoint_responses: list[HiddenEndpointResponse] = Field(default_factory=list)


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


def _responses_from_observation_dicts(
    hidden: list[str], observations: list[dict[str, Any]]
) -> list[HiddenEndpointResponse]:
    by_path: dict[str, dict[str, Any]] = {}
    for obs in observations:
        path = str(obs.get("normalized_path") or obs.get("path") or "")
        if not path or path in by_path:
            continue
        by_path[path] = obs
    out: list[HiddenEndpointResponse] = []
    for path in hidden:
        obs = by_path.get(path)
        if obs is None:
            continue
        headers = obs.get("selected_headers") or {}
        content_type = None
        if isinstance(headers, dict):
            content_type = headers.get("content-type") or headers.get("Content-Type")
        fields = obs.get("response_fields") or obs.get("extracted_fields") or []
        if not isinstance(fields, list):
            fields = []
        out.append(
            HiddenEndpointResponse(
                path=path,
                status_code=int(obs.get("status_code") or 0),
                response_bytes=int(obs.get("response_bytes") or 0),
                response_fields=[str(f) for f in fields],
                content_type=str(content_type) if content_type else None,
            )
        )
    return out


def responses_from_observations(
    hidden: list[str], observations: list[LiveObservation]
) -> list[HiddenEndpointResponse]:
    return _responses_from_observation_dicts(
        hidden, [o.model_dump(mode="json") for o in observations]
    )


def _load_raw_observations(repo_root: Path, plan_id: str, run_id: str) -> list[dict[str, Any]]:
    raw_path = repo_root / "results" / "raw" / "live" / plan_id / f"{run_id}.json"
    if not raw_path.is_file():
        return []
    try:
        doc = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    payload = doc.get("payload") or {}
    observations = payload.get("observations")
    if isinstance(observations, list):
        return [o for o in observations if isinstance(o, dict)]
    exchanges = payload.get("exchanges")
    if isinstance(exchanges, list):
        # Map exchange shape onto observation-like dicts for the helper.
        mapped: list[dict[str, Any]] = []
        for ex in exchanges:
            if not isinstance(ex, dict):
                continue
            mapped.append(
                {
                    "normalized_path": ex.get("path"),
                    "status_code": ex.get("status_code"),
                    "response_bytes": 0,
                    "response_fields": ex.get("extracted_fields") or [],
                    "selected_headers": {},
                }
            )
        return mapped
    return []


def load_evidence_rows(
    derived_root: Path, *, repo_root: Path | None = None
) -> list[LiveEvidenceRow]:
    root = repo_root if repo_root is not None else derived_root.parent.parent
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
        precomputed = payload.get("hidden_endpoint_responses")
        if isinstance(precomputed, list) and precomputed:
            responses = [
                HiddenEndpointResponse.model_validate(item)
                for item in precomputed
                if isinstance(item, dict)
            ]
        else:
            responses = _responses_from_observation_dicts(
                hidden, _load_raw_observations(root, plan_id, run_id)
            )
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
                hidden_endpoint_responses=responses,
            )
        )
    return rows


@router.get("/evidence", response_model=list[LiveEvidenceRow])
async def get_live_evidence(request: Request) -> list[LiveEvidenceRow]:
    _require_demo(request)
    derived = REPO_ROOT / "results" / "derived"
    return load_evidence_rows(derived, repo_root=REPO_ROOT)


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
        observations, report = await execute_live_plan(
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

    hidden = list(report.hidden_endpoints)
    return LiveProbeResponse(
        run_id=report.run_id,
        provider=body.provider,
        plan_id=plan.id,
        status=report.status,
        risk_score=report.risk_score,
        hidden_endpoints=hidden,
        reached_endpoints=list(report.reached_endpoints),
        findings=list(report.findings),
        hidden_endpoint_responses=responses_from_observations(hidden, observations),
    )
