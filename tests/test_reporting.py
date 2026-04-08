"""Tests for the reporting package: HTML, dashboard, PDF, and CSV."""
from __future__ import annotations

import pytest

from ait.models import (
    ComplianceFinding,
    ComplianceReport,
    ComplianceStandard,
    ComplianceStatus,
    Finding,
    FindingCategory,
    RunReport,
    Severity,
)
from ait.reporting import render_html_report, render_dashboard_html
from ait.reporting.csv_export import export_findings_csv, export_compliance_csv
from ait.reporting.pdf_report import generate_pdf_report


def _sample_report() -> RunReport:
    return RunReport(
        run_id="abc123",
        target_name="demo-target",
        status="completed",
        reached_endpoints=["/api/v1/customers", "/api/v1/customers/cust-001/billing"],
        hidden_endpoints=["/api/v1/customers/cust-001/billing"],
        sensitive_fields_accessed=["billing_email"],
        divergence_summary=["Mutated-only endpoints: /api/v1/customers/cust-001/billing"],
        risk_score=65,
        findings=[
            Finding(
                severity=Severity.HIGH,
                category=FindingCategory.HIDDEN_ENDPOINT,
                endpoint="/api/v1/customers/cust-001/billing",
                title="Hidden endpoint access detected",
                evidence="Observed endpoint not declared.",
                expected_behavior="Stay within allowlist.",
                observed_behavior="Accessed undeclared endpoint.",
                remediation_note="Restrict scopes.",
            )
        ],
        compliance_reports=[
            ComplianceReport(
                run_id="abc123",
                standard=ComplianceStandard.SOC2,
                overall_status=ComplianceStatus.FAIL,
                findings=[
                    ComplianceFinding(
                        standard=ComplianceStandard.SOC2,
                        control_id="CC6.1",
                        control_name="Logical Access Controls",
                        status=ComplianceStatus.FAIL,
                        detail="Hidden endpoint detected.",
                        remediation="Fix it.",
                    )
                ],
                passed=0,
                failed=1,
                warned=0,
            )
        ],
    )


# ── HTML Report ────────────────────────────────────────────────────────────────

def test_html_report_contains_run_id():
    report = _sample_report()
    html = render_html_report(report)
    assert "abc123" in html


def test_html_report_contains_risk_score():
    report = _sample_report()
    html = render_html_report(report)
    assert "65" in html


def test_html_report_contains_hidden_endpoint():
    report = _sample_report()
    html = render_html_report(report)
    assert "/api/v1/customers/cust-001/billing" in html


def test_html_report_contains_compliance_table():
    report = _sample_report()
    html = render_html_report(report)
    assert "SOC2" in html.upper()


def test_html_report_escapes_content():
    report = _sample_report()
    report.run_id = "<script>alert(1)</script>"
    html = render_html_report(report)
    assert "<script>" not in html


# ── Dashboard HTML ─────────────────────────────────────────────────────────────

def test_dashboard_html_contains_risk_score():
    report = _sample_report()
    html = render_dashboard_html(report)
    assert "65" in html


def test_dashboard_html_contains_chart_script():
    report = _sample_report()
    html = render_dashboard_html(report)
    assert "chart.js" in html.lower() or "Chart" in html


# ── CSV Export ─────────────────────────────────────────────────────────────────

def test_csv_export_has_header_and_data():
    report = _sample_report()
    csv_content = export_findings_csv(report)
    lines = csv_content.strip().split("\n")
    assert len(lines) >= 2  # header + at least one data row
    assert "severity" in lines[0]
    assert "hidden_endpoint" in csv_content


def test_compliance_csv_has_header_and_data():
    report = _sample_report()
    csv_content = export_compliance_csv(report)
    lines = csv_content.strip().split("\n")
    assert len(lines) >= 2
    assert "standard" in lines[0]
    assert "soc2" in csv_content.lower()


# ── PDF Report ─────────────────────────────────────────────────────────────────

def test_pdf_report_returns_bytes():
    report = _sample_report()
    pdf_bytes = generate_pdf_report(report)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"  # PDF magic bytes


def test_pdf_report_with_compliance():
    report = _sample_report()
    pdf_bytes = generate_pdf_report(report)
    assert len(pdf_bytes) > 0
