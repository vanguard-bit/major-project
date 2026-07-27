from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ait.artifacts import read_artifact
from ait.experiments.reproducibility import run_reproducibility
from ait.experiments.scenario_loader import load_scenarios


def _write_compliant(path: Path, scenario_id: str = "crm-repro") -> None:
    data = {
        "schema_version": "1.0.0",
        "id": scenario_id,
        "suite": "crm",
        "platform_style": "generic-crm",
        "description": "Reproducibility fixture.",
        "target": {
            "name": scenario_id,
            "base_url": "http://mock.invalid/",
            "integration_sync_url": "http://integration.invalid/sync",
            "audit_base_url": "http://mock.invalid/",
            "expected_endpoints": ["/api/v1/customers"],
            "sensitive_markers": ["billing_email"],
        },
        "exchanges": [
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [{"customer_id": "c1"}],
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [{"customer_id": "c1"}],
            },
        ],
        "expected_labels": [],
    }
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.mark.anyio
async def test_reproducibility_five_runs_agree(tmp_path: Path):
    scenarios = tmp_path / "scenarios" / "crm"
    scenarios.mkdir(parents=True)
    _write_compliant(scenarios / "ok.yaml")
    protocol = tmp_path / "evaluation_protocol.yaml"
    protocol.write_text(
        "schema_version: '1.0.0'\nseed: 20260727\n"
        "unit_of_analysis: scenario\n"
        "primary_categories: [hidden_endpoint]\n"
        "primary_metrics: [micro_f1]\n"
        "uncertainty: {method: wilson, confidence_level: 0.95}\n"
        "repetitions: {deterministic_offline: 5}\n"
        "failure_policy: count_detector_crash_as_miss\n"
        "scenario_globs: {primary: ['crm/**/*.yaml']}\n"
        "hypotheses: {H1: noise, H2: partial, H3: order, H4: alias, H5: boundary}\n",
        encoding="utf-8",
    )
    output = tmp_path / "results"
    summary = await run_reproducibility(
        scenario_root=tmp_path / "scenarios",
        protocol_path=protocol,
        output_root=output,
        repetitions=5,
        command=["test-repro"],
    )
    assert summary["repetitions"] == 5
    assert summary["identical_finding_category_sets"] == 5
    assert summary["identical_risk_scores"] == 5
    assert summary["detector_crashes"] == 0
    assert summary["accepted"] is True
    assert summary["mismatches"] == []
    envelope = read_artifact(output / "derived" / "reproducibility.json")
    assert envelope.configuration["protocol_sha256"]
    assert envelope.payload["accepted"] is True


@pytest.mark.anyio
async def test_reproducibility_loads_only_primary_suites(tmp_path: Path):
    root = tmp_path / "scenarios"
    crm = root / "crm"
    rob = root / "robustness"
    crm.mkdir(parents=True)
    rob.mkdir(parents=True)
    _write_compliant(crm / "ok.yaml")
    rob_data = {
        "schema_version": "1.0.0",
        "id": "rob-skip",
        "suite": "robustness",
        "platform_style": "generic-crm",
        "description": "Should not enter primary reproducibility.",
        "parent_scenario_id": "crm-repro",
        "target": {
            "name": "rob-skip",
            "base_url": "http://mock.invalid/",
            "integration_sync_url": "http://integration.invalid/sync",
            "audit_base_url": "http://mock.invalid/",
            "expected_endpoints": ["/api/v1/customers"],
            "sensitive_markers": [],
        },
        "exchanges": [
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [],
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [],
            },
        ],
        "expected_labels": [],
    }
    (rob / "r.yaml").write_text(yaml.safe_dump(rob_data), encoding="utf-8")
    assert [s.id for s in load_scenarios(root, suite="all")] == ["crm-repro"]
