from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from ait.experiments.run_scenarios import app


def _scenario(
    scenario_id: str,
    *,
    suite: str = "crm",
    labels: list[dict] | None = None,
    include_hidden: bool = False,
) -> dict:
    exchanges = [
        {
            "phase": "baseline",
            "method": "GET",
            "path": "/api/v1/customers",
            "response_body": [{"customer_id": "cust-001"}],
        },
        {
            "phase": "mutated",
            "method": "GET",
            "path": "/api/v1/customers",
            "response_body": [{"customer_id": "cust-001"}],
        },
    ]
    if include_hidden:
        exchanges.append(
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers/cust-001/billing",
                "response_body": {"plan": "enterprise"},
            }
        )
    return {
        "schema_version": "1.0.0",
        "id": scenario_id,
        "suite": suite,
        "platform_style": "generic-crm",
        "description": "CLI fixture scenario.",
        "target": {
            "name": scenario_id,
            "base_url": "http://mock.invalid/",
            "integration_sync_url": "http://integration.invalid/sync",
            "audit_base_url": "http://mock.invalid/",
            "expected_endpoints": ["/api/v1/customers"],
            "sensitive_markers": [],
        },
        "exchanges": exchanges,
        "expected_labels": labels or [],
    }


def test_run_scenarios_cli_writes_artifacts_and_passes(tmp_path: Path):
    root = tmp_path / "scenarios"
    crm = root / "crm"
    crm.mkdir(parents=True)
    (crm / "ok.yaml").write_text(yaml.safe_dump(_scenario("cli-ok")), encoding="utf-8")
    output = tmp_path / "results"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--suite",
            "all",
            "--scenario-root",
            str(root),
            "--output-root",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output
    raw = output / "raw" / "scenarios" / "cli-ok.json"
    derived = output / "derived" / "scenario_metrics.json"
    assert raw.is_file()
    assert derived.is_file()
    envelope = json.loads(raw.read_text(encoding="utf-8"))
    assert envelope["experiment"] == "scenarios"
    assert envelope["payload"]["scenario_id"] == "cli-ok"


def test_run_scenarios_cli_exits_one_on_label_mismatch(tmp_path: Path):
    root = tmp_path / "scenarios"
    crm = root / "crm"
    crm.mkdir(parents=True)
    # Hidden endpoint observed but no label -> mismatch
    (crm / "bad.yaml").write_text(
        yaml.safe_dump(_scenario("cli-bad", include_hidden=True, labels=[])),
        encoding="utf-8",
    )
    output = tmp_path / "results"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--suite",
            "crm",
            "--scenario-root",
            str(root),
            "--output-root",
            str(output),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output


def test_run_scenarios_skips_schema_example(tmp_path: Path):
    root = tmp_path / "scenarios"
    crm = root / "crm"
    crm.mkdir(parents=True)
    (crm / "ok.yaml").write_text(yaml.safe_dump(_scenario("cli-skip-ok")), encoding="utf-8")
    (root / "schema.example.yaml").write_text(
        yaml.safe_dump(_scenario("schema-example")),
        encoding="utf-8",
    )
    output = tmp_path / "results"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--suite", "all", "--scenario-root", str(root), "--output-root", str(output)],
    )
    assert result.exit_code == 0, result.output
    assert not (output / "raw" / "scenarios" / "schema-example.json").exists()
    assert (output / "raw" / "scenarios" / "cli-skip-ok.json").exists()
