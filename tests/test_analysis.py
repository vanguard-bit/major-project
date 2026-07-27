import pytest
from pydantic import ValidationError

from ait.analysis import (
    DEFAULT_RISK_WEIGHTS,
    RiskWeights,
    analyze_run,
    calculate_risk_score,
)
from ait.models import CapturedExchange, TargetConfig


def _demo_target(**overrides) -> TargetConfig:
    data = {
        "name": "demo",
        "base_url": "http://127.0.0.1:8001/",
        "integration_sync_url": "http://127.0.0.1:8002/sync",
        "audit_base_url": "http://127.0.0.1:8001/",
        "expected_endpoints": ["/api/v1/customers"],
        "sensitive_markers": ["billing_email", "tax_id"],
    }
    data.update(overrides)
    return TargetConfig.model_validate(data)


def test_analysis_detects_hidden_endpoint_and_sensitive_field():
    target = _demo_target()
    exchanges = [
        CapturedExchange(
            run_id="run-1",
            phase="baseline",
            method="GET",
            path="/api/v1/customers",
            status_code=200,
            response_body=[{"customer_id": "cust-001"}],
        ),
        CapturedExchange(
            run_id="run-1",
            phase="mutated",
            method="GET",
            path="/api/v1/customers/cust-001/billing",
            status_code=200,
            response_body={"billing_email": "x@example.test", "tax_id": "TAX-1"},
            extracted_fields=["billing_email", "tax_id"],
            contains_sensitive_marker=True,
        ),
    ]

    report = analyze_run("run-1", target, exchanges)

    assert "/api/v1/customers/cust-001/billing" in report.hidden_endpoints
    assert "billing_email" in report.sensitive_fields_accessed
    assert report.risk_score > 0
    # 1 hidden + 2 sensitive + 2 divergence lines (baseline-only + mutated-only)
    # = 25 + 40 + 30 = 95
    assert report.risk_score == 95.0
    assert isinstance(report.risk_score, float)


def test_calculate_risk_score_zero():
    assert calculate_risk_score(0, 0, 0) == 0.0


def test_calculate_risk_score_caps_at_100():
    assert calculate_risk_score(10, 10, 10) == 100.0


def test_calculate_risk_score_default_weights():
    # 1*25 + 1*20 + 1*15 = 60
    assert calculate_risk_score(1, 1, 1) == 60.0


def test_calculate_risk_score_fractional_perturbed_weights():
    weights = RiskWeights(
        hidden_endpoint=25.0 * 0.7,
        sensitive_field=20.0,
        divergence=15.0,
    )
    # 1*17.5 + 1*20 + 0*15 = 37.5
    assert calculate_risk_score(1, 1, 0, weights=weights) == 37.5


def test_calculate_risk_score_rejects_negative_counts():
    with pytest.raises(ValueError, match="negative"):
        calculate_risk_score(-1, 0, 0)
    with pytest.raises(ValueError, match="negative"):
        calculate_risk_score(0, -1, 0)
    with pytest.raises(ValueError, match="negative"):
        calculate_risk_score(0, 0, -1)


def test_analyze_run_accepts_custom_weights():
    target = _demo_target()
    exchanges = [
        CapturedExchange(
            run_id="run-w",
            phase="baseline",
            method="GET",
            path="/api/v1/customers/cust-001/billing",
            status_code=200,
            response_body={"plan": "enterprise"},
            extracted_fields=["plan"],
        ),
        CapturedExchange(
            run_id="run-w",
            phase="mutated",
            method="GET",
            path="/api/v1/customers/cust-001/billing",
            status_code=200,
            response_body={"plan": "enterprise"},
            extracted_fields=["plan"],
        ),
    ]
    weights = RiskWeights(hidden_endpoint=10.0, sensitive_field=20.0, divergence=15.0)
    report = analyze_run("run-w", target, exchanges, weights=weights)
    assert report.risk_score == 10.0


def test_default_risk_weights_match_legacy_constants():
    assert DEFAULT_RISK_WEIGHTS.hidden_endpoint == 25.0
    assert DEFAULT_RISK_WEIGHTS.sensitive_field == 20.0
    assert DEFAULT_RISK_WEIGHTS.divergence == 15.0
    assert DEFAULT_RISK_WEIGHTS.cap == 100.0


def test_risk_weights_are_frozen():
    with pytest.raises((ValidationError, TypeError, AttributeError)):
        DEFAULT_RISK_WEIGHTS.hidden_endpoint = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value",
    [
        ("hidden_endpoint", float("nan")),
        ("hidden_endpoint", float("inf")),
        ("hidden_endpoint", -1.0),
        ("sensitive_field", float("nan")),
        ("sensitive_field", float("-inf")),
        ("sensitive_field", -0.1),
        ("divergence", float("inf")),
        ("divergence", -5.0),
        ("cap", float("nan")),
        ("cap", float("inf")),
        ("cap", 0.0),
        ("cap", -1.0),
    ],
)
def test_risk_weights_reject_non_finite_or_invalid(field: str, value: float):
    kwargs = {
        "hidden_endpoint": 25.0,
        "sensitive_field": 20.0,
        "divergence": 15.0,
        "cap": 100.0,
    }
    kwargs[field] = value
    with pytest.raises((ValidationError, ValueError, TypeError)):
        RiskWeights(**kwargs)


def test_calculate_risk_score_default_is_not_caller_mutable_singleton():
    """Callers must not be able to permanently mutate shared defaults."""
    score_before = calculate_risk_score(1, 0, 0)
    weights = RiskWeights(
        hidden_endpoint=1.0,
        sensitive_field=20.0,
        divergence=15.0,
        cap=100.0,
    )
    assert calculate_risk_score(1, 0, 0, weights=weights) == 1.0
    assert calculate_risk_score(1, 0, 0) == score_before
    assert DEFAULT_RISK_WEIGHTS.hidden_endpoint == 25.0
