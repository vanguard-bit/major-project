from __future__ import annotations

from ait.models import (
    ComplianceFinding,
    ComplianceReport,
    ComplianceStandard,
    ComplianceStatus,
    FindingCategory,
    RunReport,
    Severity,
)


def _make_report(
    run_id: str,
    standard: ComplianceStandard,
    findings: list[ComplianceFinding],
) -> ComplianceReport:
    passed = sum(1 for f in findings if f.status == ComplianceStatus.PASS)
    failed = sum(1 for f in findings if f.status == ComplianceStatus.FAIL)
    warned = sum(1 for f in findings if f.status == ComplianceStatus.WARN)
    if failed > 0:
        overall = ComplianceStatus.FAIL
    elif warned > 0:
        overall = ComplianceStatus.WARN
    else:
        overall = ComplianceStatus.PASS
    return ComplianceReport(
        run_id=run_id,
        standard=standard,
        overall_status=overall,
        findings=findings,
        passed=passed,
        failed=failed,
        warned=warned,
    )


def _has_hidden_endpoints(report: RunReport) -> bool:
    return len(report.hidden_endpoints) > 0


def _has_sensitive_access(report: RunReport) -> bool:
    return len(report.sensitive_fields_accessed) > 0


def _has_high_risk(report: RunReport) -> bool:
    return report.risk_score >= 50


def check_soc2(report: RunReport) -> ComplianceReport:
    """SOC 2 Trust Service Criteria compliance check."""
    findings: list[ComplianceFinding] = []

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.SOC2,
            control_id="CC6.1",
            control_name="Logical and Physical Access Controls",
            status=ComplianceStatus.FAIL if _has_hidden_endpoints(report) else ComplianceStatus.PASS,
            detail=(
                f"Hidden endpoint access detected: {', '.join(report.hidden_endpoints)}"
                if _has_hidden_endpoints(report)
                else "No unauthorized endpoint access detected."
            ),
            remediation="Restrict integration permissions to declared endpoints only.",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.SOC2,
            control_id="CC6.6",
            control_name="Logical Access Security Measures",
            status=ComplianceStatus.FAIL if _has_sensitive_access(report) else ComplianceStatus.PASS,
            detail=(
                f"Sensitive fields accessed without approval: {', '.join(report.sensitive_fields_accessed)}"
                if _has_sensitive_access(report)
                else "No unapproved sensitive data access detected."
            ),
            remediation="Enforce field-level access controls and data minimisation.",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.SOC2,
            control_id="CC7.2",
            control_name="System Monitoring",
            status=ComplianceStatus.WARN if _has_high_risk(report) else ComplianceStatus.PASS,
            detail=(
                f"Risk score {report.risk_score}/100 exceeds recommended threshold."
                if _has_high_risk(report)
                else f"Risk score {report.risk_score}/100 is within acceptable range."
            ),
            remediation="Review and address all HIGH/CRITICAL findings to reduce risk score.",
        )
    )

    divergence_finding = any(
        f.category.value == "behavioral_divergence" for f in report.findings
    )
    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.SOC2,
            control_id="CC8.1",
            control_name="Change Management",
            status=ComplianceStatus.FAIL if divergence_finding else ComplianceStatus.PASS,
            detail=(
                "Behavioral divergence between baseline and mutated phases detected."
                if divergence_finding
                else "No behavioural divergence detected."
            ),
            remediation="Ensure state mutations do not unlock undeclared data pathways.",
        )
    )

    return _make_report(report.run_id, ComplianceStandard.SOC2, findings)


def check_gdpr(report: RunReport) -> ComplianceReport:
    """GDPR compliance check."""
    findings: list[ComplianceFinding] = []

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.GDPR,
            control_id="Art.5(1)(c)",
            control_name="Data Minimisation",
            status=ComplianceStatus.FAIL if _has_sensitive_access(report) else ComplianceStatus.PASS,
            detail=(
                f"Personal data fields accessed beyond declared need: {', '.join(report.sensitive_fields_accessed)}"
                if _has_sensitive_access(report)
                else "Data access appears limited to declared scope."
            ),
            remediation="Remove access to personal data fields not required for the integration's stated purpose.",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.GDPR,
            control_id="Art.25",
            control_name="Data Protection by Design",
            status=ComplianceStatus.FAIL if _has_hidden_endpoints(report) else ComplianceStatus.PASS,
            detail=(
                "Integration accesses undeclared endpoints that may expose personal data."
                if _has_hidden_endpoints(report)
                else "Integration adheres to declared endpoint scope."
            ),
            remediation="Implement allowlist-based endpoint access controls from the design stage.",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.GDPR,
            control_id="Art.32",
            control_name="Security of Processing",
            status=ComplianceStatus.WARN if _has_high_risk(report) else ComplianceStatus.PASS,
            detail=(
                f"Elevated risk score ({report.risk_score}/100) indicates insufficient security measures."
                if _has_high_risk(report)
                else "Security measures appear adequate based on current findings."
            ),
            remediation="Implement appropriate technical measures to address identified security gaps.",
        )
    )

    return _make_report(report.run_id, ComplianceStandard.GDPR, findings)


def check_hipaa(report: RunReport) -> ComplianceReport:
    """HIPAA Security Rule compliance check."""
    findings: list[ComplianceFinding] = []

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.HIPAA,
            control_id="164.312(a)(1)",
            control_name="Access Control",
            status=ComplianceStatus.FAIL if _has_hidden_endpoints(report) else ComplianceStatus.PASS,
            detail=(
                "Unauthorized access to protected endpoints detected."
                if _has_hidden_endpoints(report)
                else "Access controls appear to be functioning correctly."
            ),
            remediation="Implement unique user identification and emergency access procedures.",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.HIPAA,
            control_id="164.312(b)",
            control_name="Audit Controls",
            status=ComplianceStatus.PASS,
            detail="Audit logging is implemented via the AIT audit trail mechanism.",
            remediation="",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.HIPAA,
            control_id="164.312(e)(1)",
            control_name="Transmission Security",
            status=ComplianceStatus.WARN if _has_sensitive_access(report) else ComplianceStatus.PASS,
            detail=(
                "Sensitive health-adjacent fields accessed; verify transmission encryption."
                if _has_sensitive_access(report)
                else "No sensitive transmission issues detected."
            ),
            remediation="Ensure all PHI is transmitted only over encrypted channels (TLS 1.2+).",
        )
    )

    return _make_report(report.run_id, ComplianceStandard.HIPAA, findings)


def check_pci_dss(report: RunReport) -> ComplianceReport:
    """PCI DSS compliance check."""
    findings: list[ComplianceFinding] = []

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.PCI_DSS,
            control_id="Req.7",
            control_name="Restrict Access to System Components",
            status=ComplianceStatus.FAIL if _has_hidden_endpoints(report) else ComplianceStatus.PASS,
            detail=(
                f"Access to undeclared endpoints violates need-to-know principle: {', '.join(report.hidden_endpoints)}"
                if _has_hidden_endpoints(report)
                else "Access is limited to declared system components."
            ),
            remediation="Implement role-based access control and deny-by-default policies.",
        )
    )

    billing_fields = {"billing_email", "tax_id", "card_number", "cvv", "pan"}
    accessed_billing = set(report.sensitive_fields_accessed) & billing_fields
    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.PCI_DSS,
            control_id="Req.3",
            control_name="Protect Stored Account Data",
            status=ComplianceStatus.FAIL if accessed_billing else ComplianceStatus.PASS,
            detail=(
                f"Cardholder/billing data fields accessed: {', '.join(sorted(accessed_billing))}"
                if accessed_billing
                else "No cardholder data fields accessed."
            ),
            remediation="Minimise storage and access of cardholder data; use tokenisation.",
        )
    )

    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.PCI_DSS,
            control_id="Req.10",
            control_name="Log and Monitor All Access",
            status=ComplianceStatus.PASS,
            detail="Audit trail captured for all API exchanges via AIT audit log.",
            remediation="",
        )
    )

    scope_violations = [
        f for f in report.findings if f.category.value == "scope_violation"
    ]
    findings.append(
        ComplianceFinding(
            standard=ComplianceStandard.PCI_DSS,
            control_id="Req.6",
            control_name="Develop and Maintain Secure Systems",
            status=ComplianceStatus.FAIL if scope_violations else ComplianceStatus.PASS,
            detail=(
                f"{len(scope_violations)} scope violation(s) indicate insecure authorisation design."
                if scope_violations
                else "No scope violations detected."
            ),
            remediation="Follow OAuth 2.0 best practices and apply the principle of least privilege.",
        )
    )

    return _make_report(report.run_id, ComplianceStandard.PCI_DSS, findings)
