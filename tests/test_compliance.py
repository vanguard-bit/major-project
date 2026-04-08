"""Tests for the compliance framework."""
from __future__ import annotations

import pytest

from ait.models import (
    ComplianceStatus,
    ComplianceStandard,
    Finding,
    FindingCategory,
    RunReport,
    Severity,
)
from ait.compliance.checker import check_soc2, check_gdpr, check_hipaa, check_pci_dss
from ait.compliance import run_all_compliance_checks


def _clean_report(**overrides) -> RunReport:
    defaults = {
        "run_id": "run-1",
        "target_name": "demo",
        "status": "completed",
        "reached_endpoints": ["/api/v1/customers"],
        "hidden_endpoints": [],
        "sensitive_fields_accessed": [],
        "divergence_summary": [],
        "risk_score": 0,
        "findings": [],
    }
    defaults.update(overrides)
    return RunReport.model_validate(defaults)


def _failing_report() -> RunReport:
    return _clean_report(
        hidden_endpoints=["/api/v1/customers/cust-001/billing"],
        sensitive_fields_accessed=["billing_email", "tax_id"],
        risk_score=80,
        findings=[
            Finding(
                severity=Severity.HIGH,
                category=FindingCategory.BEHAVIORAL_DIVERGENCE,
                endpoint="/api/v1/customers/cust-001/billing",
                title="Behavioral divergence",
                evidence="mutated only",
                expected_behavior="no divergence",
                observed_behavior="divergence",
                remediation_note="fix it",
            )
        ],
    )


# ── SOC 2 ──────────────────────────────────────────────────────────────────────

def test_soc2_passes_on_clean_report():
    report = check_soc2(_clean_report())
    assert report.standard == ComplianceStandard.SOC2
    assert report.overall_status == ComplianceStatus.PASS
    assert report.failed == 0


def test_soc2_fails_on_hidden_endpoint():
    report = check_soc2(_failing_report())
    assert report.overall_status == ComplianceStatus.FAIL
    assert report.failed > 0


# ── GDPR ───────────────────────────────────────────────────────────────────────

def test_gdpr_passes_on_clean_report():
    report = check_gdpr(_clean_report())
    assert report.standard == ComplianceStandard.GDPR
    assert report.overall_status == ComplianceStatus.PASS


def test_gdpr_fails_when_sensitive_fields_accessed():
    run_report = _clean_report(sensitive_fields_accessed=["billing_email"])
    report = check_gdpr(run_report)
    assert report.overall_status == ComplianceStatus.FAIL


# ── HIPAA ──────────────────────────────────────────────────────────────────────

def test_hipaa_passes_on_clean_report():
    report = check_hipaa(_clean_report())
    assert report.standard == ComplianceStandard.HIPAA
    assert report.overall_status == ComplianceStatus.PASS


def test_hipaa_fails_on_unauthorized_access():
    report = check_hipaa(_failing_report())
    assert report.overall_status in (ComplianceStatus.FAIL, ComplianceStatus.WARN)


# ── PCI DSS ────────────────────────────────────────────────────────────────────

def test_pci_dss_passes_on_clean_report():
    report = check_pci_dss(_clean_report())
    assert report.standard == ComplianceStandard.PCI_DSS
    assert report.overall_status == ComplianceStatus.PASS


def test_pci_dss_fails_on_billing_data_access():
    run_report = _clean_report(sensitive_fields_accessed=["billing_email", "tax_id"])
    report = check_pci_dss(run_report)
    assert report.overall_status == ComplianceStatus.FAIL


# ── run_all_compliance_checks ──────────────────────────────────────────────────

def test_run_all_returns_four_reports():
    reports = run_all_compliance_checks(_clean_report())
    assert len(reports) == 4
    standards = {r.standard for r in reports}
    assert standards == {
        ComplianceStandard.SOC2,
        ComplianceStandard.GDPR,
        ComplianceStandard.HIPAA,
        ComplianceStandard.PCI_DSS,
    }


def test_run_all_stores_run_id():
    reports = run_all_compliance_checks(_clean_report())
    for r in reports:
        assert r.run_id == "run-1"
