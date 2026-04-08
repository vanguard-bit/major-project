from __future__ import annotations

from ait.models import (
    ComplianceFinding,
    ComplianceReport,
    ComplianceStandard,
    ComplianceStatus,
    RunReport,
)
from ait.compliance.checker import (
    check_soc2,
    check_gdpr,
    check_hipaa,
    check_pci_dss,
)

__all__ = [
    "check_soc2",
    "check_gdpr",
    "check_hipaa",
    "check_pci_dss",
    "run_all_compliance_checks",
]


def run_all_compliance_checks(report: RunReport) -> list[ComplianceReport]:
    """Run all compliance frameworks and return their reports."""
    results = []
    for checker in (check_soc2, check_gdpr, check_hipaa, check_pci_dss):
        results.append(checker(report))
    return results
