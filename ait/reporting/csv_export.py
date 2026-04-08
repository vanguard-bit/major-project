from __future__ import annotations

import csv
import io

from ait.models import RunReport


def export_findings_csv(report: RunReport) -> str:
    """Export security findings to CSV format.

    Returns a CSV string with one row per finding.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "run_id",
            "target_name",
            "severity",
            "category",
            "endpoint",
            "title",
            "evidence",
            "expected_behavior",
            "observed_behavior",
            "confidence",
            "remediation_note",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for finding in report.findings:
        writer.writerow(
            {
                "run_id": report.run_id,
                "target_name": report.target_name,
                "severity": finding.severity.value,
                "category": finding.category.value,
                "endpoint": finding.endpoint,
                "title": finding.title,
                "evidence": finding.evidence,
                "expected_behavior": finding.expected_behavior,
                "observed_behavior": finding.observed_behavior,
                "confidence": finding.confidence,
                "remediation_note": finding.remediation_note,
            }
        )
    return output.getvalue()


def export_compliance_csv(report: RunReport) -> str:
    """Export compliance findings to CSV format.

    Returns a CSV string with one row per compliance control check.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "run_id",
            "standard",
            "control_id",
            "control_name",
            "status",
            "detail",
            "remediation",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for cr in report.compliance_reports:
        for finding in cr.findings:
            writer.writerow(
                {
                    "run_id": report.run_id,
                    "standard": finding.standard.value,
                    "control_id": finding.control_id,
                    "control_name": finding.control_name,
                    "status": finding.status.value,
                    "detail": finding.detail,
                    "remediation": finding.remediation,
                }
            )
    return output.getvalue()
