from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from ait.experiments.run_offline import app, run_offline


def _write_minimal_scenario(root: Path, scenario_id: str = "off-ok") -> None:
    suite = root / "crm"
    suite.mkdir(parents=True)
    scenario = {
        "schema_version": "1.0.0",
        "id": scenario_id,
        "suite": "crm",
        "platform_style": "generic-crm",
        "description": "Minimal offline fixture.",
        "target": {
            "name": scenario_id,
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
    (suite / f"{scenario_id}.yaml").write_text(yaml.safe_dump(scenario), encoding="utf-8")


def _write_minimal_incident(root: Path, incident_id: str = "off-incident") -> None:
    root.mkdir(parents=True, exist_ok=True)
    incident = {
        "schema_version": "1.0.0",
        "id": incident_id,
        "incident_name": "Offline Test Incident",
        "reconstruction": True,
        "source_urls": ["https://example.test/postmortem"],
        "source_accessed_utc": "2026-07-27T00:00:00Z",
        "documented_behavior": ["Synthetic documented behavior."],
        "mapping_assumptions": ["Synthetic mapping for offline tests."],
        "target": {
            "name": incident_id,
            "base_url": "http://reconstruction.invalid/",
            "integration_sync_url": "http://reconstruction.invalid/sync",
            "audit_base_url": "http://reconstruction.invalid/",
            "expected_endpoints": ["/reconstruction/allowed/resource"],
            "sensitive_markers": [],
        },
        "exchanges": [
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/reconstruction/allowed/resource",
                "response_body": {"id": "1"},
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/reconstruction/allowed/resource",
                "response_body": {"id": "1"},
            },
        ],
        "expected_labels": [],
    }
    (root / f"{incident_id}.yaml").write_text(yaml.safe_dump(incident), encoding="utf-8")


def test_empty_scenario_root_fails_without_success_manifest(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"
    code = run_offline(
        output_root=output,
        scenario_root=scenarios,
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[10],
        benchmark_warmups=0,
        benchmark_repetitions=1,
        reproducibility_repetitions=1,
    )
    assert code != 0
    assert not (output / "derived" / "offline_manifest.json").exists()


def test_empty_incident_root_fails_without_success_manifest(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    _write_minimal_scenario(scenarios)
    incidents = tmp_path / "incidents"
    incidents.mkdir()
    output = tmp_path / "out"
    code = run_offline(
        output_root=output,
        scenario_root=scenarios,
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[10],
        benchmark_warmups=0,
        benchmark_repetitions=1,
        reproducibility_repetitions=1,
    )
    assert code != 0
    assert not (output / "derived" / "offline_manifest.json").exists()


def test_empty_benchmark_widths_fails_without_success_manifest(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    _write_minimal_scenario(scenarios)
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"
    code = run_offline(
        output_root=output,
        scenario_root=scenarios,
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[],
        benchmark_warmups=0,
        benchmark_repetitions=1,
    )
    assert code != 0
    assert not (output / "derived" / "offline_manifest.json").exists()


def test_missing_scenario_root_fails(tmp_path: Path):
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"
    code = run_offline(
        output_root=output,
        scenario_root=tmp_path / "missing-scenarios",
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[10],
        benchmark_warmups=0,
        benchmark_repetitions=1,
    )
    assert code != 0
    assert not (output / "derived" / "offline_manifest.json").exists()


def test_manifest_excludes_stale_unrelated_json(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    _write_minimal_scenario(scenarios)
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"
    stale = output / "raw" / "junk" / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"experiment":"unrelated","payload":{}}', encoding="utf-8")

    code = run_offline(
        output_root=output,
        scenario_root=scenarios,
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[10],
        benchmark_warmups=0,
        benchmark_repetitions=1,
        reproducibility_repetitions=1,
    )
    assert code == 0
    manifest = json.loads(
        (output / "derived" / "offline_manifest.json").read_text(encoding="utf-8")
    )
    paths = [entry["path"] for entry in manifest["payload"]["artifacts"]]
    assert all("stale.json" not in p for p in paths)
    assert "raw/junk/stale.json" not in paths


def test_failed_run_invalidates_prior_success_manifest(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    _write_minimal_scenario(scenarios)
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"

    assert (
        run_offline(
            output_root=output,
            scenario_root=scenarios,
            incident_root=incidents,
            command=["python", "-m", "ait.experiments.run_offline"],
            benchmark_widths=[10],
            benchmark_warmups=0,
            benchmark_repetitions=1,
            reproducibility_repetitions=1,
        )
        == 0
    )
    assert (output / "derived" / "offline_manifest.json").exists()

    # Second run fails at scenarios (empty root) and must not leave a success manifest.
    empty_scenarios = tmp_path / "empty-scenarios"
    empty_scenarios.mkdir()
    code = run_offline(
        output_root=output,
        scenario_root=empty_scenarios,
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[10],
        benchmark_warmups=0,
        benchmark_repetitions=1,
    )
    assert code != 0
    assert not (output / "derived" / "offline_manifest.json").exists()


def test_offline_cli_ordering_and_success(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    _write_minimal_scenario(scenarios)
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--output-root",
            str(output),
            "--scenario-root",
            str(scenarios),
            "--incident-root",
            str(incidents),
            "--widths",
            "10",
            "--warmups",
            "0",
            "--repetitions",
            "1",
            "--reproducibility-repetitions",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "=== 1/6 scenarios ===" in result.output
    assert "=== 2/6 risk sensitivity ===" in result.output
    assert "=== 3/6 incident replay ===" in result.output
    assert "=== 4/6 benchmark ===" in result.output
    assert "=== 5/6 robustness ===" in result.output
    assert "=== 6/6 reproducibility" in result.output
    assert result.output.index("=== 1/6") < result.output.index("=== 2/6")
    assert result.output.index("=== 5/6") < result.output.index("=== 6/6")
    manifest = json.loads(
        (output / "derived" / "offline_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["experiment"] == "offline_manifest"
    assert manifest["payload"]["artifact_count"] == len(manifest["payload"]["artifacts"])
    assert manifest["payload"]["artifact_count"] > 0
    paths = [entry["path"] for entry in manifest["payload"]["artifacts"]]
    assert any(p.endswith("robustness_metrics.json") for p in paths)
    assert any(p.endswith("reproducibility.json") for p in paths)
    assert manifest["payload"]["phase5"]["robustness_in_scope_passed"] is True
    assert manifest["payload"]["phase5"]["reproducibility_accepted"] is True
    assert (output / "derived" / "robustness_metrics.json").is_file()
    assert (output / "derived" / "reproducibility.json").is_file()


def test_first_failure_stops_before_later_stages(tmp_path: Path):
    scenarios = tmp_path / "scenarios"
    suite = scenarios / "crm"
    suite.mkdir(parents=True)
    # Intentionally mismatched labels so scenario stage fails.
    bad = {
        "schema_version": "1.0.0",
        "id": "off-fail",
        "suite": "crm",
        "platform_style": "generic-crm",
        "description": "Fails label match.",
        "target": {
            "name": "off-fail",
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
        "expected_labels": [{"category": "hidden_endpoint"}],
    }
    (suite / "off-fail.yaml").write_text(yaml.safe_dump(bad), encoding="utf-8")
    incidents = tmp_path / "incidents"
    _write_minimal_incident(incidents)
    output = tmp_path / "out"
    code = run_offline(
        output_root=output,
        scenario_root=scenarios,
        incident_root=incidents,
        command=["python", "-m", "ait.experiments.run_offline"],
        benchmark_widths=[10],
        benchmark_warmups=0,
        benchmark_repetitions=1,
        reproducibility_repetitions=1,
    )
    assert code != 0
    assert not (output / "raw" / "benchmark" / "benchmark_raw.json").exists()
    assert not (output / "derived" / "offline_manifest.json").exists()
