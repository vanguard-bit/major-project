from ait.analysis import analyze_run
from ait.models import CapturedExchange, TargetConfig


def test_analysis_detects_hidden_endpoint_and_sensitive_field():
    target = TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
            "expected_endpoints": ["/api/v1/customers"],
            "sensitive_markers": ["billing_email", "tax_id"],
        }
    )
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
