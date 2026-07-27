from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ait.analysis import calculate_risk_score
from ait.experiments.risk_sensitivity import (
    app,
    classify_risk,
    derive_sensitivity_summary,
    run_sensitivity,
    run_sensitivity_pipeline,
)
from ait.experiments.schema import ScenarioOutcome
from ait.models import RunReport


def _outcome(
    scenario_id: str,
    *,
    hidden: list[str],
    sensitive: list[str],
    divergence: list[str],
    risk_score: float,
) -> ScenarioOutcome:
    return ScenarioOutcome(
        scenario_id=scenario_id,
        expected_categories=set(),
        observed_categories=set(),
        report=RunReport(
            run_id=scenario_id,
            target_name=scenario_id,
            status="completed",
            reached_endpoints=[],
            hidden_endpoints=hidden,
            sensitive_fields_accessed=sensitive,
            divergence_summary=divergence,
            risk_score=risk_score,
            findings=[],
        ),
    )


def test_classify_risk_band_boundaries():
    assert classify_risk(0) == "low"
    assert classify_risk(25) == "low"
    assert classify_risk(25.01) == "medium"
    assert classify_risk(50) == "medium"
    assert classify_risk(50.01) == "high"
    assert classify_risk(75) == "high"
    assert classify_risk(75.01) == "critical"
    assert classify_risk(100) == "critical"


def test_classify_risk_rejects_negative():
    with pytest.raises(ValueError, match="non-negative"):
        classify_risk(-0.1)


def test_run_sensitivity_manual_arithmetic_fixture():
    """Manually verified: 1 hidden, 1 sensitive, 0 divergence.

    Base: 25 + 20 = 45 (medium)
    hidden_endpoint @ 0.7: 17.5 + 20 = 37.5 (medium)
    hidden_endpoint @ 1.3: 32.5 + 20 = 52.5 (high)
    sensitive_field @ 0.7: 25 + 14 = 39.0 (medium)
    sensitive_field @ 1.3: 25 + 26 = 51.0 (high)
    divergence @ any: unchanged 45.0 (medium)
    """
    outcome = _outcome(
        "fixture-s1",
        hidden=["/hidden"],
        sensitive=["secret"],
        divergence=[],
        risk_score=45.0,
    )
    rows = run_sensitivity([outcome], multipliers=[0.7, 1.0, 1.3])
    by_key = {(r.varied_weight, r.multiplier): r for r in rows}

    assert len(rows) == 9  # 3 weights × 3 multipliers

    expected = {
        ("hidden_endpoint", 0.7): 37.5,
        ("hidden_endpoint", 1.0): 45.0,
        ("hidden_endpoint", 1.3): 52.5,
        ("sensitive_field", 0.7): 39.0,
        ("sensitive_field", 1.0): 45.0,
        ("sensitive_field", 1.3): 51.0,
        ("divergence", 0.7): 45.0,
        ("divergence", 1.0): 45.0,
        ("divergence", 1.3): 45.0,
    }
    for key, score in expected.items():
        row = by_key[key]
        assert row.score == score
        assert row.band == classify_risk(score)
        # Independent recomputation
        weights_kwargs = {
            "hidden_endpoint": 25.0,
            "sensitive_field": 20.0,
            "divergence": 15.0,
        }
        varied, multiplier = key
        weights_kwargs[varied] = weights_kwargs[varied] * multiplier
        from ait.analysis import RiskWeights

        recomputed = round(
            calculate_risk_score(1, 1, 0, weights=RiskWeights(**weights_kwargs)),
            2,
        )
        assert recomputed == score


def test_derive_sensitivity_summary_min_max_and_transitions():
    outcome = _outcome(
        "fixture-s1",
        hidden=["/hidden"],
        sensitive=["secret"],
        divergence=[],
        risk_score=45.0,
    )
    rows = run_sensitivity([outcome], multipliers=[0.7, 1.0, 1.3])
    summary = derive_sensitivity_summary(rows)
    assert summary["row_count"] == 9
    scenario = summary["scenarios"][0]
    assert scenario["scenario_id"] == "fixture-s1"
    assert scenario["min_score"] == 37.5
    assert scenario["max_score"] == 52.5
    transitions = scenario["band_transitions"]
    assert isinstance(transitions, list)
    assert transitions
    assert all(isinstance(t, dict) for t in transitions)
    high = [
        t
        for t in transitions
        if t["resulting_band"] == "high" and t["baseline_band"] == "medium"
    ]
    assert high
    assert {t["varied_weight"] for t in high} <= {"hidden_endpoint", "sensitive_field"}
    for t in high:
        assert t["multiplier"] == 1.3
        assert set(t) >= {"baseline_band", "resulting_band", "varied_weight", "multiplier"}


def test_run_sensitivity_pipeline_writes_artifacts(tmp_path: Path):
    outcome = _outcome(
        "fixture-s1",
        hidden=["/hidden"],
        sensitive=[],
        divergence=[],
        risk_score=25.0,
    )
    rows = run_sensitivity_pipeline(
        [outcome],
        tmp_path,
        command=["python", "-m", "ait.experiments.risk_sensitivity"],
    )
    assert len(rows) == 9
    raw = tmp_path / "raw" / "sensitivity" / "sensitivity_rows.json"
    derived = tmp_path / "derived" / "sensitivity_summary.json"
    assert raw.is_file()
    assert derived.is_file()
    payload = json.loads(raw.read_text(encoding="utf-8"))
    assert payload["experiment"] == "risk_sensitivity"
    assert len(payload["payload"]["rows"]) == 9


def test_sensitivity_cli_smoke(tmp_path: Path):
    # Minimal scenario root with one compliant scenario
    import yaml

    root = tmp_path / "scenarios" / "crm"
    root.mkdir(parents=True)
    scenario = {
        "schema_version": "1.0.0",
        "id": "sens-cli-ok",
        "suite": "crm",
        "platform_style": "generic-crm",
        "description": "Compliant fixture for sensitivity CLI.",
        "target": {
            "name": "sens-cli-ok",
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
    (root / "ok.yaml").write_text(yaml.safe_dump(scenario), encoding="utf-8")
    output = tmp_path / "results"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--suite",
            "crm",
            "--scenario-root",
            str(tmp_path / "scenarios"),
            "--output-root",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Sensitivity rows:" in result.output
    assert (output / "raw" / "sensitivity" / "sensitivity_rows.json").is_file()
