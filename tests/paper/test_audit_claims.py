"""Tests for empirical claim audit against artifact availability."""

from __future__ import annotations

from pathlib import Path

import yaml

from ait.paper.audit_claims import audit_claims


def _write_minimal_metrics(path: Path) -> str:
    import hashlib

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"experiment":"scenario_metrics","configuration":{},'
        '"payload":{"micro":{"f1":1.0,"precision":1.0,"recall":1.0}},'
        '"provenance":{"schema_version":"1.0.0",'
        '"generated_at_utc":"2026-07-27T00:00:00+00:00","command":["t"],'
        '"seed":1,"git_commit":null,"python_version":"3.12","platform":"t"}}\n',
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_passes_when_required_evidence_resolves(tmp_path: Path):
    metrics = tmp_path / "derived" / "scenario_metrics.json"
    digest = _write_minimal_metrics(metrics)
    (tmp_path / "configs").mkdir()
    paper_yaml = tmp_path / "configs" / "paper_artifacts.yaml"
    paper_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "scenario_metrics": {
                    "path": "derived/scenario_metrics.json",
                    "sha256": digest,
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
    claims_yaml = tmp_path / "configs" / "claims.yaml"
    claims_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "claims": [
                    {
                        "id": "mock-overall-f1",
                        "text_pattern": "micro-average F1",
                        "documents": ["main.tex"],
                        "evidence": {
                            "artifact": "scenario_metrics",
                            "json_pointer": "/payload/micro/f1",
                        },
                        "required": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "main.tex").write_text(
        "% CLAIM:mock-overall-f1\n"
        "The micro-average F1 is reported in the generated table.\n",
        encoding="utf-8",
    )
    result = audit_claims(
        claims_path=claims_yaml,
        manifest_path=paper_yaml,
        repo_root=tmp_path,
    )
    assert result.ok
    assert result.errors == []


def test_audit_rejects_required_null_artifact(tmp_path: Path):
    (tmp_path / "configs").mkdir()
    paper_yaml = tmp_path / "configs" / "paper_artifacts.yaml"
    paper_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
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
    claims_yaml = tmp_path / "configs" / "claims.yaml"
    claims_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "claims": [
                    {
                        "id": "live-required",
                        "text_pattern": "GitHub smoke",
                        "documents": ["main.tex"],
                        "evidence": {
                            "artifact": "github_smoke",
                            "json_pointer": "/payload/x",
                        },
                        "required": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "main.tex").write_text(
        "% CLAIM:live-required\nGitHub smoke probe reported findings.\n",
        encoding="utf-8",
    )
    result = audit_claims(
        claims_path=claims_yaml,
        manifest_path=paper_yaml,
        repo_root=tmp_path,
    )
    assert not result.ok
    assert any("null" in e.lower() or "unavailable" in e.lower() for e in result.errors)


def test_audit_rejects_unknown_claim_marker(tmp_path: Path):
    (tmp_path / "configs").mkdir()
    paper_yaml = tmp_path / "configs" / "paper_artifacts.yaml"
    paper_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
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
    claims_yaml = tmp_path / "configs" / "claims.yaml"
    claims_yaml.write_text(
        yaml.safe_dump({"schema_version": "1.0.0", "claims": []}),
        encoding="utf-8",
    )
    (tmp_path / "main.tex").write_text(
        "% CLAIM:fabricated-number\nWe observed F1 of 0.99.\n",
        encoding="utf-8",
    )
    result = audit_claims(
        claims_path=claims_yaml,
        manifest_path=paper_yaml,
        repo_root=tmp_path,
    )
    assert not result.ok
    assert any("fabricated-number" in e for e in result.errors)


def test_optional_null_claim_ok_without_marker(tmp_path: Path):
    (tmp_path / "configs").mkdir()
    paper_yaml = tmp_path / "configs" / "paper_artifacts.yaml"
    paper_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
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
    claims_yaml = tmp_path / "configs" / "claims.yaml"
    claims_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "claims": [
                    {
                        "id": "live-optional",
                        "text_pattern": "optional live finding",
                        "documents": ["main.tex"],
                        "evidence": {
                            "artifact": "github_smoke",
                            "json_pointer": "/payload/x",
                        },
                        "required": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "main.tex").write_text(
        "Design background without empirical live claims.\n",
        encoding="utf-8",
    )
    result = audit_claims(
        claims_path=claims_yaml,
        manifest_path=paper_yaml,
        repo_root=tmp_path,
    )
    assert result.ok
