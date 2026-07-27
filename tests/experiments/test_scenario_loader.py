from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ait.experiments.scenario_loader import load_scenario, load_scenarios, normalize_path

MINIMAL = {
    "schema_version": "1.0.0",
    "id": "crm-minimal",
    "suite": "crm",
    "platform_style": "generic-crm",
    "description": "Minimal valid scenario.",
    "target": {
        "name": "crm-minimal",
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
            "response_body": [{"customer_id": "cust-001"}],
        },
        {
            "phase": "mutated",
            "method": "GET",
            "path": "/api/v1/customers",
            "response_body": [{"customer_id": "cust-001"}],
        },
    ],
    "expected_labels": [],
}


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_normalize_path_sorts_query_pairs_and_keeps_path_params():
    assert normalize_path("/api/v1/items?b=2&a=1") == "/api/v1/items?a=1&b=2"
    assert normalize_path("/api/v1/customers/cust-001") == "/api/v1/customers/cust-001"
    assert normalize_path("/api/v1/items?a=1&a=0") == "/api/v1/items?a=0&a=1"


def test_load_scenario_accepts_minimal_valid_yaml(tmp_path: Path):
    path = _write_yaml(tmp_path / "ok.yaml", MINIMAL)
    scenario = load_scenario(path)
    assert scenario.id == "crm-minimal"
    assert scenario.schema_version == "1.0.0"
    assert len(scenario.exchanges) == 2


def test_load_scenario_rejects_unknown_keys(tmp_path: Path):
    data = {**MINIMAL, "unexpected_key": True}
    path = _write_yaml(tmp_path / "bad.yaml", data)
    with pytest.raises(ValidationError):
        load_scenario(path)


def test_load_scenario_rejects_unsupported_schema_version(tmp_path: Path):
    data = {**MINIMAL, "schema_version": "9.9.9"}
    path = _write_yaml(tmp_path / "bad.yaml", data)
    with pytest.raises(ValidationError):
        load_scenario(path)


def test_load_scenario_rejects_empty_exchanges(tmp_path: Path):
    data = {**MINIMAL, "exchanges": []}
    path = _write_yaml(tmp_path / "bad.yaml", data)
    with pytest.raises(ValidationError):
        load_scenario(path)


def test_load_scenario_rejects_path_without_leading_slash(tmp_path: Path):
    data = {
        **MINIMAL,
        "exchanges": [
            {
                "phase": "baseline",
                "method": "GET",
                "path": "api/v1/customers",
                "response_body": [],
            }
        ],
    }
    path = _write_yaml(tmp_path / "bad.yaml", data)
    with pytest.raises(ValidationError):
        load_scenario(path)


def test_load_scenario_rejects_duplicate_exchange_records(tmp_path: Path):
    exchange = {
        "phase": "baseline",
        "method": "GET",
        "path": "/api/v1/customers",
        "response_body": [],
    }
    data = {**MINIMAL, "exchanges": [exchange, exchange]}
    path = _write_yaml(tmp_path / "bad.yaml", data)
    with pytest.raises(ValidationError):
        load_scenario(path)


def test_load_scenario_normalizes_query_strings_on_paths(tmp_path: Path):
    data = {
        **MINIMAL,
        "exchanges": [
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/items?b=2&a=1",
                "response_body": [],
            },
            {
                "phase": "mutated",
                "method": "GET",
                "path": "/api/v1/customers/cust-001",
                "response_body": [],
            },
        ],
    }
    path = _write_yaml(tmp_path / "q.yaml", data)
    scenario = load_scenario(path)
    assert scenario.exchanges[0].path == "/api/v1/items?a=1&b=2"
    assert scenario.exchanges[1].path == "/api/v1/customers/cust-001"


def test_load_scenario_rejects_duplicate_after_query_normalization(tmp_path: Path):
    data = {
        **MINIMAL,
        "exchanges": [
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/items?b=2&a=1",
                "response_body": [],
            },
            {
                "phase": "baseline",
                "method": "GET",
                "path": "/api/v1/items?a=1&b=2",
                "response_body": [],
            },
        ],
    }
    path = _write_yaml(tmp_path / "dup-q.yaml", data)
    with pytest.raises(ValidationError):
        load_scenario(path)


def test_load_scenarios_rejects_duplicate_ids(tmp_path: Path):
    _write_yaml(tmp_path / "a.yaml", MINIMAL)
    other = {**MINIMAL, "id": "crm-minimal", "description": "Duplicate id."}
    _write_yaml(tmp_path / "b.yaml", other)
    with pytest.raises(ValueError, match="duplicate"):
        load_scenarios(tmp_path)


def test_load_scenarios_skips_schema_example(tmp_path: Path):
    scenarios_root = tmp_path / "scenarios"
    crm = scenarios_root / "crm"
    crm.mkdir(parents=True)
    _write_yaml(crm / "ok.yaml", MINIMAL)
    _write_yaml(scenarios_root / "schema.example.yaml", {**MINIMAL, "id": "schema-example"})
    loaded = load_scenarios(scenarios_root)
    assert [s.id for s in loaded] == ["crm-minimal"]
