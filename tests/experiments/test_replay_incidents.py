from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
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


def test_endpoint_qualified_label_mismatch(tmp_path: Path):
    path = tmp_path / "endpoint-mismatch.yaml"
    path.write_text(
        yaml.safe_dump(
            _minimal_incident(
                labels=[
                    {
                        "category": "hidden_endpoint",
                        "endpoint": "/reconstruction/wrong-path",
                    },
                    {"category": "behavioral_divergence"},
                    {
                        "category": "sensitive_field_access",
                        "endpoint": "/reconstruction/excess-scope/resource",
                    },
                ]
            )
        ),
        encoding="utf-8",
    )
    outcome = run_replay(path)
    assert outcome.exact_match is False


def test_endpoint_qualified_label_match(tmp_path: Path):
    path = tmp_path / "endpoint-ok.yaml"
    path.write_text(
        yaml.safe_dump(
            _minimal_incident(
                labels=[
                    {
                        "category": "hidden_endpoint",
                        "endpoint": "/reconstruction/excess-scope/resource",
                    },
                    {"category": "behavioral_divergence"},
                    {
                        "category": "sensitive_field_access",
                        "endpoint": "/reconstruction/excess-scope/resource",
                    },
                ]
            )
        ),
        encoding="utf-8",
    )
    outcome = run_replay(path)
    assert outcome.exact_match is True


def test_load_incident_requires_reconstruction_true(tmp_path: Path):
    data = _minimal_incident()
    data["reconstruction"] = False
    path = tmp_path / "no.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="reconstruction"):
        load_incident(path)


def test_load_incident_rejects_unknown_target_key(tmp_path: Path):
    data = _minimal_incident()
    data["target"]["unexpected_key"] = "nope"
    path = tmp_path / "extra.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError, TypeError)):
        load_incident(path)


def test_load_incident_rejects_non_http_url(tmp_path: Path):
    data = _minimal_incident()
    data["source_urls"] = ["ftp://example.test/x"]
    path = tmp_path / "ftp.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError, TypeError)):
        load_incident(path)


def test_load_incident_rejects_naive_timestamp(tmp_path: Path):
    data = _minimal_incident()
    data["source_accessed_utc"] = "2026-07-27T00:00:00"
    path = tmp_path / "naive.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError, TypeError)):
        load_incident(path)


def test_load_incident_rejects_empty_documented_behavior(tmp_path: Path):
    data = _minimal_incident()
    data["documented_behavior"] = ["  "]
    path = tmp_path / "empty-doc.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises((ValidationError, ValueError, TypeError)):
        load_incident(path)


def test_replay_raw_artifact_includes_provenance_fields(tmp_path: Path):
    from ait.experiments.replay_incidents import run_replay_pipeline

    incidents = tmp_path / "incidents"
    incidents.mkdir()
    (incidents / "ok.yaml").write_text(
        yaml.safe_dump(_minimal_incident("ok")), encoding="utf-8"
    )
    output = tmp_path / "results"
    run_replay_pipeline(
        incidents, output, command=["python", "-m", "ait.experiments.replay_incidents"]
    )
    raw = json.loads((output / "raw" / "replay" / "ok.json").read_text(encoding="utf-8"))
    payload = raw["payload"]
    assert payload["source_urls"]
    assert payload["documented_behavior"]
    assert payload["mapping_assumptions"]
    assert payload["expected_labels"]
    assert payload["fixture_hash"]
    assert payload["exchanges"]
    assert len(payload["fixture_hash"]) == 64


def test_empty_incident_root_pipeline_raises(tmp_path: Path):
    from ait.experiments.replay_incidents import run_replay_pipeline

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="incident"):
        run_replay_pipeline(empty, tmp_path / "out", command=["test"])


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
