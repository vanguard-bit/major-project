from __future__ import annotations

import httpx
import pytest

from ait.analysis import analyze_run, extract_field_paths, field_matches_sensitive_marker
from ait.experiments.mock_executor import execute_scenario, scripted_transport_handler
from ait.experiments.schema import ExchangeSpec, ScenarioDefinition
from ait.models import CapturedExchange, FindingCategory, TargetConfig


def test_extract_field_paths_nested_and_list():
    body = {
        "billing": {"tax_id": "TAX-1", "email": "a@example.test"},
        "items": [{"sku": "A"}, {"sku": "B"}],
    }
    paths = extract_field_paths(body)
    assert "billing.tax_id" in paths
    assert "billing.email" in paths
    assert "items.sku" in paths


def test_field_matches_sensitive_marker_leaf_and_dotted():
    markers = {"tax_id", "billing.email"}
    assert field_matches_sensitive_marker("tax_id", markers)
    assert field_matches_sensitive_marker("billing.tax_id", markers)
    assert field_matches_sensitive_marker("billing.email", markers)
    assert not field_matches_sensitive_marker("plan", markers)
    assert not field_matches_sensitive_marker("billing.plan", markers)


def test_analyze_run_matches_nested_sensitive_leaf_marker():
    target = TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://mock.invalid/",
            "integration_sync_url": "http://integration.invalid/sync",
            "audit_base_url": "http://mock.invalid/",
            "expected_endpoints": ["/api/v1/customers/cust-001/profile"],
            "sensitive_markers": ["tax_id"],
        }
    )
    nested = {"billing": {"tax_id": "TAX-1"}}
    fields = sorted(extract_field_paths(nested))
    exchanges = [
        CapturedExchange(
            run_id="run-nested",
            phase="baseline",
            method="GET",
            path="/api/v1/customers/cust-001/profile",
            status_code=200,
            response_body=nested,
            extracted_fields=fields,
            contains_sensitive_marker=True,
        ),
        CapturedExchange(
            run_id="run-nested",
            phase="mutated",
            method="GET",
            path="/api/v1/customers/cust-001/profile",
            status_code=200,
            response_body=nested,
            extracted_fields=fields,
            contains_sensitive_marker=True,
        ),
    ]
    report = analyze_run("run-nested", target, exchanges)
    assert any(f.category == FindingCategory.SENSITIVE_FIELD_ACCESS for f in report.findings)
    accessed = report.sensitive_fields_accessed
    assert "billing.tax_id" in accessed or "tax_id" in accessed


def test_scripted_transport_handler_rejects_method_or_path_mismatch():
    pending = [
        ExchangeSpec(phase="baseline", method="GET", path="/api/v1/customers", response_body=[])
    ]
    handler = scripted_transport_handler(pending)
    bad = httpx.Request("POST", "http://mock.invalid/api/v1/customers")
    with pytest.raises(ValueError, match="mismatch"):
        handler(bad)


@pytest.mark.anyio
async def test_execute_scenario_captures_exchanges_and_findings():
    scenario = ScenarioDefinition.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "crm-s3-like",
            "suite": "crm",
            "platform_style": "generic-crm",
            "description": "Mutated-only billing with sensitive fields.",
            "target": {
                "name": "crm-s3-like",
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
                    "response_body": [{"customer_id": "cust-001"}],
                },
                {
                    "phase": "mutated",
                    "method": "GET",
                    "path": "/api/v1/customers",
                    "response_body": [{"customer_id": "cust-001"}],
                },
                {
                    "phase": "mutated",
                    "method": "GET",
                    "path": "/api/v1/customers/cust-001/billing",
                    "response_body": {
                        "billing_email": "run-marker@example.test",
                        "tax_id": "TAX-RUN-MARKER",
                    },
                },
            ],
            "expected_labels": [
                {"category": "hidden_endpoint", "endpoint": "/api/v1/customers/cust-001/billing"},
                {
                    "category": "sensitive_field_access",
                    "endpoint": "/api/v1/customers/cust-001/billing",
                },
                {"category": "behavioral_divergence"},
            ],
        }
    )

    outcome = await execute_scenario(scenario)

    assert outcome.scenario_id == "crm-s3-like"
    assert outcome.report.run_id == "crm-s3-like"
    assert len(outcome.report.reached_endpoints) == 2
    assert "/api/v1/customers/cust-001/billing" in outcome.report.hidden_endpoints
    assert "billing_email" in outcome.report.sensitive_fields_accessed
    assert outcome.report.divergence_summary
    assert outcome.report.risk_score > 0
    assert outcome.expected_categories == {
        FindingCategory.HIDDEN_ENDPOINT,
        FindingCategory.SENSITIVE_FIELD_ACCESS,
        FindingCategory.BEHAVIORAL_DIVERGENCE,
    }
    assert outcome.observed_categories == outcome.expected_categories


@pytest.mark.anyio
async def test_execute_scenario_uses_stable_run_id_from_scenario_id():
    scenario = ScenarioDefinition.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "stable-id-case",
            "suite": "crm",
            "platform_style": "generic-crm",
            "description": "Stable run id.",
            "target": {
                "name": "stable-id-case",
                "base_url": "http://mock.invalid/",
                "integration_sync_url": "http://integration.invalid/sync",
                "audit_base_url": "http://mock.invalid/",
                "expected_endpoints": ["/api/v1/customers"],
            },
            "exchanges": [
                {
                    "phase": "baseline",
                    "method": "GET",
                    "path": "/api/v1/customers",
                    "response_body": [],
                },
                {
                    "phase": "mutated",
                    "method": "GET",
                    "path": "/api/v1/customers",
                    "response_body": [],
                },
            ],
            "expected_labels": [],
        }
    )
    first = await execute_scenario(scenario)
    second = await execute_scenario(scenario)
    assert first.report.run_id == "stable-id-case"
    assert second.report.run_id == first.report.run_id
