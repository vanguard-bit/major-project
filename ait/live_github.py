"""Optional live observation against api.github.com (read-only GETs).

Requires ``AIT_GITHUB_TOKEN`` (fine-grained or classic PAT). Intended for a
tiny sandbox experiment: policy allowlists only ``/user`` but the probe
also calls ``/user/repos`` (including a paginated second page),
``/user/orgs``, producing multiple hidden-endpoint signals under AIT's
Analysis Engine. This does not exfiltrate private repository contents beyond
what GitHub returns for the token's normal permissions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import yaml

from ait.analysis import analyze_run
from ait.models import CapturedExchange, RunRecord, TargetConfig, TestRunConfig


def _extracted_keys(body: Any) -> list[str]:
    if isinstance(body, dict):
        return sorted(body.keys())
    if isinstance(body, list) and body and isinstance(body[0], dict):
        return sorted(body[0].keys())
    return []


async def collect_github_exchanges(token: str, run_id: str) -> list[CapturedExchange]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    exchanges: list[CapturedExchange] = []
    async with httpx.AsyncClient(base_url="https://api.github.com", headers=headers, timeout=30) as client:
        for phase in ("baseline", "mutated"):
            for path, params in (
                ("/user", None),
                ("/user/repos", {"per_page": "3"}),
                ("/user/repos", {"per_page": "3", "page": "2"}),
                ("/user/orgs", None),
            ):
                response = await client.get(path, params=params)
                ctype = response.headers.get("content-type", "")
                if "json" in ctype:
                    try:
                        body = response.json()
                    except Exception:  # noqa: BLE001
                        body = {"_raw": response.text[:2000]}
                else:
                    body = {"_text": response.text[:2000]}
                observed_path = response.request.url.path
                fields = _extracted_keys(body)
                exchanges.append(
                    CapturedExchange(
                        run_id=run_id,
                        phase=phase,
                        method="GET",
                        path=observed_path,
                        status_code=response.status_code,
                        response_body=body if isinstance(body, dict) else {"_non_dict": True},
                        extracted_fields=fields,
                        contains_sensitive_marker=False,
                    )
                )
    return exchanges


def load_live_github_target(config_path: Path | None = None) -> TargetConfig:
    path = config_path or Path(__file__).resolve().parent.parent / "test_cases" / "github_live_sandbox.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    token = os.environ.get("AIT_GITHUB_TOKEN", "").strip()
    if not token:
        raise ValueError("Set AIT_GITHUB_TOKEN to a GitHub PAT with at least read:user (read-only probe).")
    raw.setdefault("token_config", {})["token"] = token
    return TargetConfig.model_validate(raw)


async def run_live_github_sandbox(
    config_path: Path | None = None,
    run_config: TestRunConfig | None = None,
) -> RunRecord:
    target = load_live_github_target(config_path)
    run_id = uuid4().hex[:12]
    token = target.token_config.token or ""
    exchanges = await collect_github_exchanges(token, run_id)
    report = analyze_run(run_id, target, exchanges)
    cfg = run_config or TestRunConfig()
    return RunRecord(
        run_id=run_id,
        status="completed",
        target=target,
        config=cfg,
        findings=report.findings,
        exchanges=exchanges,
        report=report,
    )
