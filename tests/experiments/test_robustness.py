from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ait.artifacts import read_artifact
from ait.experiments.robustness import (
    build_evasion_corpus,
    build_robustness_corpus,
    inject_health_polls,
    load_evaluation_protocol,
    protocol_sha256,
    run_robustness_suite,
)
from ait.experiments.scenario_loader import load_scenario, load_scenarios
from ait.experiments.schema import ScenarioDefinition


def _minimal_parent(**overrides: object) -> dict:
    data = {
        "schema_version": "1.0.0",
        "id": "crm-parent",
        "suite": "crm",
        "platform_style": "generic-crm",
        "description": "Parent for transforms.",
        "target": {
            "name": "crm-parent",
            "base_url": "http://mock.invalid/",
            "integration_sync_url": "http://integration.invalid/sync",
            "audit_base_url": "http://mock.invalid/",
            "expected_endpoints": ["/api/v1/customers"],
            "sensitive_markers": ["billing_email", "tax_id"],
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
    data.update(overrides)
    return data


def test_load_scenarios_all_excludes_robustness_and_evasion(tmp_path: Path):
    crm = tmp_path / "crm"
    rob = tmp_path / "robustness"
    eva = tmp_path / "evasion"
    crm.mkdir()
    rob.mkdir()
    eva.mkdir()
    (crm / "ok.yaml").write_text(yaml.safe_dump(_minimal_parent()), encoding="utf-8")
    rob_data = {
        **_minimal_parent(id="rob-1", suite="robustness"),
        "parent_scenario_id": "crm-parent",
        "labels_invariant": True,
        "observable_by_model": True,
    }
    (rob / "r.yaml").write_text(yaml.safe_dump(rob_data), encoding="utf-8")
    eva_data = {
        **_minimal_parent(id="eva-1", suite="evasion"),
        "parent_scenario_id": "crm-parent",
        "labels_invariant": False,
        "observable_by_model": False,
    }
    (eva / "e.yaml").write_text(yaml.safe_dump(eva_data), encoding="utf-8")

    loaded = load_scenarios(tmp_path, suite="all")
    assert [s.id for s in loaded] == ["crm-parent"]

    robustness = load_scenarios(tmp_path, suite="robustness")
    assert [s.id for s in robustness] == ["rob-1"]
    assert robustness[0].parent_scenario_id == "crm-parent"
    assert robustness[0].observable_by_model is True

    evasion = load_scenarios(tmp_path, suite="evasion")
    assert [s.id for s in evasion] == ["eva-1"]
    assert evasion[0].observable_by_model is False


def test_exchange_sequence_allows_retries_of_same_path(tmp_path: Path):
    data = _minimal_parent(
        exchanges=[
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers",
                "sequence": 0,
                "response_body": [],
            },
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers",
                "sequence": 1,
                "status_code": 429,
                "response_body": {"error": "rate_limited"},
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [],
            },
        ]
    )
    path = tmp_path / "retry.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    scenario = load_scenario(path)
    assert len(scenario.exchanges) == 3


def test_inject_health_polls_preserves_parent_and_labels():
    parent = ScenarioDefinition.model_validate(_minimal_parent())
    transformed = inject_health_polls(parent, count=8)
    assert transformed.parent_scenario_id == parent.id
    assert transformed.labels_invariant is True
    assert transformed.suite == "robustness"
    assert "/health" in transformed.target.expected_endpoints
    health = [e for e in transformed.exchanges if e.path == "/health"]
    assert len(health) == 16


@pytest.mark.anyio
async def test_build_robustness_corpus_covers_required_transforms(tmp_path: Path):
    crm = tmp_path / "crm"
    crm.mkdir()
    hidden = _minimal_parent(
        id="crm-s1-hidden-both-phases",
        exchanges=[
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [{"customer_id": "c1"}],
            },
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers/c1/billing",
                "response_body": {"plan": "enterprise"},
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [{"customer_id": "c1"}],
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers/c1/billing",
                "response_body": {"plan": "enterprise"},
            },
        ],
        expected_labels=[
            {"category": "hidden_endpoint", "endpoint": "/api/v1/customers/c1/billing"}
        ],
    )
    sensitive = _minimal_parent(
        id="crm-s2-sensitive-allowed-path",
        target={
            **_minimal_parent()["target"],
            "name": "crm-s2",
            "expected_endpoints": [
                "/api/v1/customers",
                "/api/v1/customers/c1/billing",
            ],
        },
        exchanges=[
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [{"customer_id": "c1"}],
            },
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/customers/c1/billing",
                "response_body": {"plan": "enterprise"},
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers",
                "response_body": [{"customer_id": "c1"}],
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers/c1/billing",
                "response_body": {
                    "billing_email": "a@example.test",
                    "tax_id": "TAX",
                    "plan": "enterprise",
                },
            },
        ],
        expected_labels=[
            {
                "category": "sensitive_field_access",
                "endpoint": "/api/v1/customers/c1/billing",
            }
        ],
    )
    (crm / "hidden.yaml").write_text(yaml.safe_dump(hidden), encoding="utf-8")
    (crm / "sensitive.yaml").write_text(yaml.safe_dump(sensitive), encoding="utf-8")

    corpus = build_robustness_corpus(tmp_path)
    ids = {s.id for s in corpus}
    assert any("health-0" in i for i in ids)
    assert any("health-8" in i for i in ids)
    assert any("health-32" in i for i in ids)
    assert any("health-128" in i for i in ids)
    assert any("query-order" in i for i in ids)
    assert any("retry" in i for i in ids)
    assert any("429" in i for i in ids)
    assert any("partial-sensitive" in i for i in ids)
    assert any("nested-sensitive" in i for i in ids)
    assert any("endpoint-order" in i for i in ids)
    assert any("ambiguous-profile" in i for i in ids)
    assert any("empty-bodies" in i for i in ids)
    assert any("path-normalize" in i for i in ids)
    assert all(s.parent_scenario_id for s in corpus)
    assert all(s.suite == "robustness" for s in corpus)


def test_build_evasion_corpus_marks_model_boundary(tmp_path: Path):
    crm = tmp_path / "crm"
    crm.mkdir()
    (crm / "ok.yaml").write_text(yaml.safe_dump(_minimal_parent()), encoding="utf-8")
    corpus = build_evasion_corpus(tmp_path)
    ids = {s.id for s in corpus}
    assert "eva-fn1-out-of-band" in ids
    assert "eva-fn2-shared-token" in ids
    assert "eva-fn3-delayed" in ids
    assert "eva-fn4-field-alias" in ids
    assert all(s.observable_by_model is False for s in corpus)
    assert all(s.suite == "evasion" for s in corpus)


def test_malformed_evasion_case_fails_validation(tmp_path: Path):
    path = tmp_path / "eva-malformed.yaml"
    path.write_text("schema_version: '1.0.0'\nid: broken\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_scenario(path)


@pytest.mark.anyio
async def test_run_robustness_suite_separates_in_scope_and_boundary(tmp_path: Path):
    protocol = tmp_path / "evaluation_protocol.yaml"
    protocol.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "seed": 20260727,
                "unit_of_analysis": "scenario",
                "primary_categories": [
                    "hidden_endpoint",
                    "sensitive_field_access",
                    "behavioral_divergence",
                ],
                "primary_metrics": ["per_category_precision", "per_category_recall"],
                "uncertainty": {"method": "wilson", "confidence_level": 0.95},
                "repetitions": {"deterministic_offline": 5},
                "failure_policy": "count_detector_crash_as_miss",
                "scenario_globs": {
                    "primary": ["crm/**/*.yaml", "platform/**/*.yaml"],
                    "robustness": ["robustness/**/*.yaml"],
                    "evasion": ["evasion/**/*.yaml"],
                },
                "hypotheses": {
                    "H1": "hidden endpoint labels are detected under benign log noise",
                    "H2": "sensitive field labels are detected when exposure is partial",
                    "H3": "endpoint order and harmless query variation do not create divergence",
                    "H4": "aliased sensitive fields remain a known false negative",
                    "H5": (
                        "delayed/out-of-band/shared-token cases remain "
                        "outside the detector model"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    crm = tmp_path / "scenarios" / "crm"
    crm.mkdir(parents=True)
    (crm / "ok.yaml").write_text(yaml.safe_dump(_minimal_parent()), encoding="utf-8")

    output = tmp_path / "results"
    summary = await run_robustness_suite(
        scenario_root=tmp_path / "scenarios",
        protocol_path=protocol,
        output_root=output,
        command=["test"],
    )
    assert summary["protocol_sha256"] == protocol_sha256(protocol)
    assert "in_scope" in summary
    assert "model_boundary" in summary
    artifact = output / "derived" / "robustness_metrics.json"
    assert artifact.exists()
    envelope = read_artifact(artifact)
    assert envelope.configuration["protocol_sha256"] == summary["protocol_sha256"]
    assert "in_scope" in envelope.payload
    assert "model_boundary" in envelope.payload


def test_load_evaluation_protocol_and_hash():
    root = Path(__file__).resolve().parents[2]
    protocol_path = root / "configs" / "evaluation_protocol.yaml"
    protocol = load_evaluation_protocol(protocol_path)
    assert protocol["seed"] == 20260727
    assert set(protocol["hypotheses"]) == {"H1", "H2", "H3", "H4", "H5"}
    assert protocol["uncertainty"]["method"] == "wilson"
    assert protocol["uncertainty"]["confidence_level"] == 0.95
    assert protocol["repetitions"]["deterministic_offline"] == 5
    digest = protocol_sha256(protocol_path)
    assert len(digest) == 64
