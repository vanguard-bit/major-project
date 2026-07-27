"""Tests for input/artifact staleness detection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ait.paper.check_stale import check_stale, collect_input_hashes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_check_stale_passes_when_hashes_match(tmp_path: Path):
    scenario = tmp_path / "configs" / "scenarios" / "crm" / "a.yaml"
    scenario.parent.mkdir(parents=True)
    scenario.write_text("id: a\n", encoding="utf-8")
    incident = tmp_path / "configs" / "incidents" / "i.yaml"
    incident.parent.mkdir(parents=True)
    incident.write_text("id: i\n", encoding="utf-8")
    sources = tmp_path / "configs" / "incidents" / "SOURCES.md"
    sources.write_text("# sources\n", encoding="utf-8")
    protocol = tmp_path / "configs" / "evaluation_protocol.yaml"
    protocol.write_text("schema_version: '1.0.0'\n", encoding="utf-8")
    analysis = tmp_path / "ait" / "analysis.py"
    analysis.parent.mkdir(parents=True)
    analysis.write_text("DEFAULT_RISK_WEIGHTS = 1\n", encoding="utf-8")
    exp = tmp_path / "ait" / "experiments" / "run_offline.py"
    exp.parent.mkdir(parents=True)
    exp.write_text("print('x')\n", encoding="utf-8")

    input_hashes = collect_input_hashes(tmp_path)
    derived = tmp_path / "results" / "derived"
    derived.mkdir(parents=True)
    metrics = derived / "scenario_metrics.json"
    metrics.write_text('{"experiment":"scenario_metrics","payload":{},"configuration":{},'
                       '"provenance":{"schema_version":"1.0.0","generated_at_utc":'
                       '"2026-07-27T00:00:00+00:00","command":["t"],"seed":1,'
                       '"git_commit":null,"python_version":"3.12","platform":"t"}}\n',
                       encoding="utf-8")
    metrics_hash = _sha(metrics.read_bytes())
    offline = {
        "experiment": "offline_manifest",
        "configuration": {},
        "payload": {
            "artifacts": [
                {"path": "derived/scenario_metrics.json", "sha256": metrics_hash}
            ],
            "artifact_count": 1,
            "input_hashes": input_hashes,
        },
        "provenance": {
            "schema_version": "1.0.0",
            "generated_at_utc": "2026-07-27T00:00:00+00:00",
            "command": ["t"],
            "seed": 1,
            "git_commit": None,
            "python_version": "3.12",
            "platform": "t",
        },
    }
    offline_path = derived / "offline_manifest.json"
    offline_path.write_text(json.dumps(offline) + "\n", encoding="utf-8")

    paper = tmp_path / "configs" / "paper_artifacts.yaml"
    paper.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "offline_manifest": {
                    "path": "results/derived/offline_manifest.json",
                    "sha256": _sha(offline_path.read_bytes()),
                },
                "scenario_metrics": {
                    "path": "results/derived/scenario_metrics.json",
                    "sha256": metrics_hash,
                },
                "live_runs": {
                    "github_readonly": None,
                    "github_smoke": None,
                    "notion_readonly": None,
                },
                "tool_comparison": None,
            }
        ),
        encoding="utf-8",
    )
    result = check_stale(repo_root=tmp_path, manifest_path=paper)
    assert result.ok, result.errors


def test_check_stale_fails_when_input_byte_changes(tmp_path: Path):
    scenario = tmp_path / "configs" / "scenarios" / "crm" / "a.yaml"
    scenario.parent.mkdir(parents=True)
    scenario.write_text("id: a\n", encoding="utf-8")
    incident = tmp_path / "configs" / "incidents" / "i.yaml"
    incident.parent.mkdir(parents=True)
    incident.write_text("id: i\n", encoding="utf-8")
    sources = tmp_path / "configs" / "incidents" / "SOURCES.md"
    sources.write_text("# sources\n", encoding="utf-8")
    protocol = tmp_path / "configs" / "evaluation_protocol.yaml"
    protocol.write_text("schema_version: '1.0.0'\n", encoding="utf-8")
    analysis = tmp_path / "ait" / "analysis.py"
    analysis.parent.mkdir(parents=True)
    analysis.write_text("DEFAULT_RISK_WEIGHTS = 1\n", encoding="utf-8")
    exp = tmp_path / "ait" / "experiments" / "run_offline.py"
    exp.parent.mkdir(parents=True)
    exp.write_text("print('x')\n", encoding="utf-8")

    input_hashes = collect_input_hashes(tmp_path)
    derived = tmp_path / "results" / "derived"
    derived.mkdir(parents=True)
    metrics = derived / "scenario_metrics.json"
    metrics.write_text('{"experiment":"scenario_metrics","payload":{},"configuration":{},'
                       '"provenance":{"schema_version":"1.0.0","generated_at_utc":'
                       '"2026-07-27T00:00:00+00:00","command":["t"],"seed":1,'
                       '"git_commit":null,"python_version":"3.12","platform":"t"}}\n',
                       encoding="utf-8")
    metrics_hash = _sha(metrics.read_bytes())
    offline = {
        "experiment": "offline_manifest",
        "configuration": {},
        "payload": {
            "artifacts": [
                {"path": "derived/scenario_metrics.json", "sha256": metrics_hash}
            ],
            "artifact_count": 1,
            "input_hashes": input_hashes,
        },
        "provenance": {
            "schema_version": "1.0.0",
            "generated_at_utc": "2026-07-27T00:00:00+00:00",
            "command": ["t"],
            "seed": 1,
            "git_commit": None,
            "python_version": "3.12",
            "platform": "t",
        },
    }
    offline_path = derived / "offline_manifest.json"
    offline_path.write_text(json.dumps(offline) + "\n", encoding="utf-8")
    paper = tmp_path / "configs" / "paper_artifacts.yaml"
    paper.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "offline_manifest": {
                    "path": "results/derived/offline_manifest.json",
                    "sha256": _sha(offline_path.read_bytes()),
                },
                "scenario_metrics": {
                    "path": "results/derived/scenario_metrics.json",
                    "sha256": metrics_hash,
                },
                "live_runs": {
                    "github_readonly": None,
                    "github_smoke": None,
                    "notion_readonly": None,
                },
                "tool_comparison": None,
            }
        ),
        encoding="utf-8",
    )
    # Change one input byte after recording hashes
    scenario.write_text("id: a\nchanged\n", encoding="utf-8")
    result = check_stale(repo_root=tmp_path, manifest_path=paper)
    assert not result.ok
    assert any("stale" in e.lower() or "mismatch" in e.lower() for e in result.errors)
