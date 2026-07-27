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
    payload = envelope["payload"]
    assert payload["scenario_id"] == "cli-ok"
    assert "target" in payload
    assert payload["target"]["name"] == "cli-ok"
    assert payload["target"]["base_url"].startswith("http://mock.invalid")
    assert "expected_labels" in payload
    assert isinstance(payload["expected_labels"], list)
    assert "exchanges" in payload
    assert len(payload["exchanges"]) >= 2
    exchange = payload["exchanges"][0]
    assert exchange["method"] == "GET"
    assert exchange["path"] == "/api/v1/customers"
    assert exchange["request_headers"]
    assert "report" in payload
    assert "categories" not in payload  # derived metrics stay separate
    derived_payload = json.loads(derived.read_text(encoding="utf-8"))["payload"]
    assert "categories" in derived_payload
    assert "micro" in derived_payload


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


def test_run_scenarios_cli_exits_nonzero_on_empty_corpus(tmp_path: Path):
    root = tmp_path / "scenarios"
    root.mkdir(parents=True)
    output = tmp_path / "results"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--suite", "all", "--scenario-root", str(root), "--output-root", str(output)],
    )
    assert result.exit_code != 0, result.output


def test_run_scenarios_cli_is_deterministic_excluding_provenance(tmp_path: Path):
    root = tmp_path / "scenarios"
    crm = root / "crm"
    crm.mkdir(parents=True)
    (crm / "ok.yaml").write_text(yaml.safe_dump(_scenario("cli-det")), encoding="utf-8")
    runner = CliRunner()
    out_a = tmp_path / "results-a"
    out_b = tmp_path / "results-b"
    for output in (out_a, out_b):
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

    def _strip_provenance(path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("provenance", None)
        return data

    assert _strip_provenance(out_a / "raw" / "scenarios" / "cli-det.json") == _strip_provenance(
        out_b / "raw" / "scenarios" / "cli-det.json"
    )
    assert _strip_provenance(out_a / "derived" / "scenario_metrics.json") == _strip_provenance(
        out_b / "derived" / "scenario_metrics.json"
    )
