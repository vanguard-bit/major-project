from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from ait.experiments.replay_incidents import (
    app,
    load_incident,
    run_replay,
)
from ait.models import FindingCategory


def _minimal_incident(
    incident_id: str = "test-reconstruction",
    *,
    include_hidden: bool = True,
    labels: list[dict] | None = None,
) -> dict:
    exchanges = [
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
    ]
    if include_hidden:
        exchanges.append(
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/reconstruction/excess-scope/resource",
                "response_body": {"secret_token": "x", "id": "2"},
            }
        )
    return {
        "schema_version": "1.0.0",
        "id": incident_id,
        "incident_name": "Test Incident",
        "reconstruction": True,
        "source_urls": ["https://example.test/postmortem"],
        "source_accessed_utc": "2026-07-27T00:00:00Z",
        "documented_behavior": ["Synthetic documented behavior for unit tests."],
        "mapping_assumptions": [
            "Undeclared /reconstruction/excess-scope/resource maps to hidden_endpoint."
        ],
        "target": {
            "name": incident_id,
            "base_url": "http://reconstruction.invalid/",
            "integration_sync_url": "http://reconstruction.invalid/sync",
            "audit_base_url": "http://reconstruction.invalid/",
            "expected_endpoints": ["/reconstruction/allowed/resource"],
            "sensitive_markers": ["secret_token"],
        },
        "exchanges": exchanges,
        "expected_labels": labels
        if labels is not None
        else [
            {"category": "hidden_endpoint"},
            {"category": "behavioral_divergence"},
            {"category": "sensitive_field_access"},
        ],
    }


def test_run_replay_exact_match(tmp_path: Path):
    path = tmp_path / "ok.yaml"
    path.write_text(yaml.safe_dump(_minimal_incident()), encoding="utf-8")
    outcome = run_replay(path)
    assert outcome.reconstruction is True
    assert outcome.exact_match is True
    assert FindingCategory.HIDDEN_ENDPOINT in outcome.observed_categories
    assert FindingCategory.SENSITIVE_FIELD_ACCESS in outcome.observed_categories
    assert FindingCategory.BEHAVIORAL_DIVERGENCE in outcome.observed_categories


def test_run_replay_mismatch(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.safe_dump(_minimal_incident(labels=[])),
        encoding="utf-8",
    )
    outcome = run_replay(path)
    assert outcome.exact_match is False


def test_load_incident_requires_reconstruction_true(tmp_path: Path):
    data = _minimal_incident()
    data["reconstruction"] = False
    path = tmp_path / "no.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="reconstruction"):
        load_incident(path)


def test_committed_incident_fixtures_match():
    root = Path("configs/incidents")
    for name in ("circleci_2023.yaml", "okta_2022.yaml", "github_2022.yaml"):
        outcome = run_replay(root / name)
        assert outcome.exact_match, (
            f"{name}: expected={sorted(c.value for c in outcome.expected_categories)} "
            f"observed={sorted(c.value for c in outcome.observed_categories)}"
        )


def test_replay_cli_writes_artifacts_and_exits_nonzero_on_mismatch(tmp_path: Path):
    incidents = tmp_path / "incidents"
    incidents.mkdir()
    (incidents / "ok.yaml").write_text(yaml.safe_dump(_minimal_incident("ok")), encoding="utf-8")
    (incidents / "bad.yaml").write_text(
        yaml.safe_dump(_minimal_incident("bad", labels=[])),
        encoding="utf-8",
    )
    output = tmp_path / "results"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["--incident-root", str(incidents), "--output-root", str(output)],
    )
    assert result.exit_code == 1, result.output
    assert (output / "raw" / "replay" / "ok.json").is_file()
    assert (output / "derived" / "replay_match_table.json").is_file()
    table = json.loads(
        (output / "derived" / "replay_match_table.json").read_text(encoding="utf-8")
    )
    assert table["experiment"] == "replay_match_table"
