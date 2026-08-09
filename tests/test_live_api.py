from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ait.api import app
from ait.models import Finding, FindingCategory, RunReport, Severity


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _local(client: TestClient, method: str, url: str, **kwargs):  # type: ignore[no-untyped-def]
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("host", "localhost")
    return client.request(method, url, headers=headers, **kwargs)


def test_live_probes_disabled_without_env(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.delenv("AIT_DEMO_LIVE_PROBES", raising=False)
    r = _local(
        client,
        "POST",
        "/live/probes",
        json={"provider": "github", "plan": "smoke", "token": "x"},
    )
    assert r.status_code == 404


def test_live_evidence_disabled_without_env(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.delenv("AIT_DEMO_LIVE_PROBES", raising=False)
    r = _local(client, "GET", "/live/evidence")
    assert r.status_code == 404


def test_live_probes_rejects_unknown_plan(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("AIT_DEMO_LIVE_PROBES", "1")
    r = _local(
        client,
        "POST",
        "/live/probes",
        json={"provider": "github", "plan": "evil", "token": "x"},
    )
    assert r.status_code == 422


def test_live_evidence_lists_summaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("AIT_DEMO_LIVE_PROBES", "1")
    results = tmp_path / "results" / "derived"
    results.mkdir(parents=True)
    doc = {
        "configuration": {
            "provider": "github",
            "plan_id": "github-smoke",
            "run_status": "completed",
        },
        "payload": {
            "status": "completed",
            "run_id": "run-1",
            "risk_score": 50.0,
            "hidden_endpoints": ["/user/orgs"],
            "reached_endpoints": ["/user", "/user/orgs"],
            "findings": [],
        },
    }
    (results / "live_github-smoke_run-1.json").write_text(json.dumps(doc), encoding="utf-8")

    import ait.live_api as live_api

    monkeypatch.setattr(live_api, "REPO_ROOT", tmp_path)

    r = _local(client, "GET", "/live/evidence")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["platform"] == "Github"
    assert rows[0]["scenario"] == "smoke"
    assert rows[0]["risk_score"] == 50.0
    assert "hidden" in rows[0]["result"]


def test_live_probes_happy_path_monkeypatched(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("AIT_DEMO_LIVE_PROBES", "1")
    report = RunReport(
        run_id="run-xyz",
        target_name="github-smoke",
        status="completed",
        reached_endpoints=["/user", "/user/orgs"],
        hidden_endpoints=["/user/orgs"],
        sensitive_fields_accessed=[],
        divergence_summary=[],
        risk_score=25.0,
        findings=[
            Finding(
                severity=Severity.MEDIUM,
                category=FindingCategory.HIDDEN_ENDPOINT,
                endpoint="/user/orgs",
                title="Hidden endpoint access detected",
                evidence="Observed undeclared endpoint",
                expected_behavior="Allowlist only",
                observed_behavior="Undeclared call",
                remediation_note="Reduce scopes",
            )
        ],
    )

    async def _fake_execute(plan, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs.get("token") == "paste-token"
        return [], report

    monkeypatch.setattr("ait.live_api.execute_live_plan", _fake_execute)
    r = _local(
        client,
        "POST",
        "/live/probes",
        json={"provider": "github", "plan": "smoke", "token": "paste-token"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == "run-xyz"
    assert body["risk_score"] == 25.0
    assert body["hidden_endpoints"] == ["/user/orgs"]
    assert body["findings"][0]["endpoint"] == "/user/orgs"
