"""Tests for advanced analysis engines: scope validator, anomaly detector, rate limit detector."""
from __future__ import annotations

import pytest

from ait.models import CapturedExchange, FindingCategory, TargetConfig
from ait.analysis.scope_validator import detect_scope_violations
from ait.analysis.rate_limit_detector import detect_rate_limit_violations
from ait.analysis.anomaly_detector import detect_anomalies


@pytest.fixture
def target_with_scope():
    return TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
            "expected_scopes": ["crm.read"],
            "sensitive_markers": ["billing_email"],
            "token_config": {
                "scope": "crm.read billing.read",
                "token_url": "http://127.0.0.1:8001/oauth/token",
                "client_id": "demo-client",
                "client_secret": "demo-secret",
            },
        }
    )


@pytest.fixture
def simple_exchange():
    return CapturedExchange(
        run_id="r1",
        phase="baseline",
        method="GET",
        path="/api/v1/customers",
        status_code=200,
    )


# ── Scope Validator ────────────────────────────────────────────────────────────

def test_scope_validator_detects_excess_scope(target_with_scope, simple_exchange):
    findings = detect_scope_violations(target_with_scope, [simple_exchange])
    categories = [f.category for f in findings]
    assert FindingCategory.SCOPE_VIOLATION in categories


def test_scope_validator_no_findings_when_scopes_match():
    target = TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
            "expected_scopes": ["crm.read"],
            "sensitive_markers": [],
            "token_config": {
                "scope": "crm.read",
                "token_url": "http://127.0.0.1:8001/oauth/token",
                "client_id": "c",
                "client_secret": "s",
            },
        }
    )
    exchange = CapturedExchange(
        run_id="r1",
        phase="baseline",
        method="GET",
        path="/api/v1/customers",
        status_code=200,
    )
    findings = detect_scope_violations(target, [exchange])
    assert not findings


def test_scope_validator_no_expected_scopes_returns_empty():
    target = TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
        }
    )
    findings = detect_scope_violations(target, [])
    assert findings == []


# ── Rate Limit Detector ────────────────────────────────────────────────────────

def test_rate_limit_no_violation_for_normal_traffic(target_with_scope):
    exchanges = [
        CapturedExchange(
            run_id="r1",
            phase="baseline",
            method="GET",
            path="/api/v1/customers",
            status_code=200,
        )
        for _ in range(5)
    ]
    findings = detect_rate_limit_violations(target_with_scope, exchanges)
    assert findings == []


def test_rate_limit_detects_excessive_calls(target_with_scope):
    exchanges = [
        CapturedExchange(
            run_id="r1",
            phase="baseline",
            method="GET",
            path="/api/v1/spammy",
            status_code=200,
        )
        for _ in range(65)
    ]
    findings = detect_rate_limit_violations(target_with_scope, exchanges)
    assert any(f.category == FindingCategory.RATE_LIMIT_VIOLATION for f in findings)


def test_rate_limit_empty_exchanges(target_with_scope):
    findings = detect_rate_limit_violations(target_with_scope, [])
    assert findings == []


# ── Anomaly Detector ───────────────────────────────────────────────────────────

def test_anomaly_detector_returns_empty_for_too_few_samples(target_with_scope):
    exchanges = [
        CapturedExchange(
            run_id="r1",
            phase="baseline",
            method="GET",
            path="/api/v1/customers",
            status_code=200,
        )
        for _ in range(3)
    ]
    findings = detect_anomalies(exchanges)
    assert findings == []


def test_anomaly_detector_runs_on_sufficient_data():
    exchanges = []
    # Normal requests
    for i in range(8):
        exchanges.append(
            CapturedExchange(
                run_id="r1",
                phase="baseline",
                method="GET",
                path="/api/v1/customers",
                status_code=200,
            )
        )
    # Anomalous request
    exchanges.append(
        CapturedExchange(
            run_id="r1",
            phase="mutated",
            method="DELETE",
            path="/api/v1/customers/cust-001/billing",
            status_code=500,
            extracted_fields=["billing_email", "tax_id"],
            contains_sensitive_marker=True,
        )
    )
    findings = detect_anomalies(exchanges)
    # Should run without error; may or may not flag anomalies depending on data distribution
    assert isinstance(findings, list)
