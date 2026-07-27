"""Tests for paper artifact manifest and claim models."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from ait.paper.models import (
    ClaimsRegistry,
    PaperArtifactsManifest,
    load_claims_registry,
    load_paper_artifacts_manifest,
    resolve_json_pointer,
    sha256_file,
    verify_artifact_ref,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "paper"


def _write_json(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_hash_mismatch_fails(tmp_path: Path):
    artifact = tmp_path / "derived" / "scenario_metrics.json"
    digest = _write_json(
        artifact,
        '{"experiment":"scenario_metrics","payload":{"micro":{"f1":1.0}},'
        '"configuration":{},"provenance":{"schema_version":"1.0.0",'
        '"generated_at_utc":"2026-07-27T00:00:00+00:00","command":["x"],'
        '"seed":1,"git_commit":null,"python_version":"3.12","platform":"test"}}\n',
    )
    manifest_path = tmp_path / "paper_artifacts.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "offline_manifest": None,
                "scenario_metrics": {
                    "path": str(artifact.relative_to(tmp_path)),
                    "sha256": "0" * 64,
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
    with pytest.raises(ValueError, match="hash mismatch"):
        load_paper_artifacts_manifest(manifest_path, root=tmp_path)
    # sanity: correct hash would differ
    assert digest != "0" * 64


def test_missing_file_fails(tmp_path: Path):
    manifest_path = tmp_path / "paper_artifacts.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "scenario_metrics": {
                    "path": "derived/missing.json",
                    "sha256": "a" * 64,
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
    with pytest.raises(ValueError, match="missing"):
        load_paper_artifacts_manifest(manifest_path, root=tmp_path)


def test_null_optional_artifact_accepted(tmp_path: Path):
    artifact = tmp_path / "derived" / "scenario_metrics.json"
    digest = _write_json(
        artifact,
        '{"experiment":"scenario_metrics","payload":{"micro":{"f1":1.0}},'
        '"configuration":{},"provenance":{"schema_version":"1.0.0",'
        '"generated_at_utc":"2026-07-27T00:00:00+00:00","command":["x"],'
        '"seed":1,"git_commit":null,"python_version":"3.12","platform":"test"}}\n',
    )
    manifest_path = tmp_path / "paper_artifacts.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "scenario_metrics": {
                    "path": str(artifact.relative_to(tmp_path)),
                    "sha256": digest,
                },
                "live_runs": {
                    "github_readonly": None,
                    "github_smoke": None,
                    "notion_readonly": None,
                },
                "tool_comparison": None,
                "robustness_metrics": None,
            }
        ),
        encoding="utf-8",
    )
    manifest = load_paper_artifacts_manifest(manifest_path, root=tmp_path)
    assert manifest.tool_comparison is None
    assert manifest.live_runs.github_smoke is None
    assert not manifest.is_available("tool_comparison")
    assert manifest.is_available("scenario_metrics")


def test_wrong_schema_version_fails(tmp_path: Path):
    manifest_path = tmp_path / "paper_artifacts.yaml"
    manifest_path.write_text(
        yaml.safe_dump({"schema_version": "9.9.9", "live_runs": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema_version"):
        load_paper_artifacts_manifest(manifest_path, root=tmp_path)


def test_claims_registry_loads_fixture():
    registry = load_claims_registry(FIXTURES / "claims.yaml")
    assert isinstance(registry, ClaimsRegistry)
    assert registry.schema_version == "1.0.0"
    assert any(c.id == "mock-overall-f1" for c in registry.claims)


def test_json_pointer_resolves():
    data = {"payload": {"micro": {"f1": 1.0}}}
    assert resolve_json_pointer(data, "/payload/micro/f1") == 1.0


def test_verify_artifact_ref_ok(tmp_path: Path):
    path = tmp_path / "x.json"
    digest = _write_json(path, '{"a":1}\n')
    verify_artifact_ref(path, digest)
    assert sha256_file(path) == digest


def test_paper_artifacts_model_rejects_partial_ref():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PaperArtifactsManifest.model_validate(
            {
                "schema_version": "1.0.0",
                "scenario_metrics": {"path": "x.json"},  # missing sha256
                "live_runs": {
                    "github_readonly": None,
                    "github_smoke": None,
                    "notion_readonly": None,
                },
            }
        )


def test_live_artifact_selection_requires_completed(tmp_path: Path):
    from ait.paper.models import validate_live_artifact

    completed = tmp_path / "live_ok.json"
    completed.write_text(
        json.dumps(
            {
                "experiment": "live",
                "configuration": {"run_status": "completed"},
                "payload": {"status": "completed", "report": {}},
            }
        ),
        encoding="utf-8",
    )
    validate_live_artifact(completed)

    status = tmp_path / "run.status.json"
    status.write_text(
        json.dumps(
            {
                "experiment": "live",
                "payload": {"status": "blocked", "reason": "no creds"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="status artifact"):
        validate_live_artifact(status)

    failed = tmp_path / "live_fail.json"
    failed.write_text(
        json.dumps(
            {
                "experiment": "live",
                "payload": {"status": "failed"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not completed"):
        validate_live_artifact(failed)

    wrong_exp = tmp_path / "not_live.json"
    wrong_exp.write_text(
        json.dumps({"experiment": "scenarios", "payload": {"status": "completed"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="experiment"):
        validate_live_artifact(wrong_exp)


def test_load_manifest_rejects_blocked_live_selection(tmp_path: Path):
    blocked = tmp_path / "raw" / "live" / "x.status.json"
    blocked.parent.mkdir(parents=True)
    blocked.write_text(
        json.dumps(
            {
                "experiment": "live",
                "payload": {"status": "blocked"},
                "provenance": {},
                "configuration": {},
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(blocked.read_bytes()).hexdigest()
    manifest_path = tmp_path / "paper_artifacts.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "live_runs": {
                    "github_readonly": {
                        "path": str(blocked.relative_to(tmp_path)),
                        "sha256": digest,
                    },
                    "github_smoke": None,
                    "notion_readonly": None,
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="status artifact|not completed"):
        load_paper_artifacts_manifest(manifest_path, root=tmp_path)
