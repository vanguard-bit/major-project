from __future__ import annotations

import io
from typing import TYPE_CHECKING

from ait.models import RunReport

if TYPE_CHECKING:
    pass


def generate_pdf_report(report: RunReport) -> bytes:
    """Generate a PDF executive summary report.

    Returns raw PDF bytes.  Requires ``reportlab`` to be installed.
    """
    try:
        from reportlab.lib import colors  # type: ignore[import-not-found]
        from reportlab.lib.pagesizes import letter  # type: ignore[import-not-found]
        from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-not-found]
        from reportlab.lib.units import inch  # type: ignore[import-not-found]
        from reportlab.platypus import (  # type: ignore[import-not-found]
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is required for PDF generation: pip install reportlab"
        ) from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("Adversarial Integration Tester Report", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))

    # Executive Summary
    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    summary_data = [
        ["Run ID", report.run_id],
        ["Target", report.target_name],
        ["Status", report.status],
        ["Risk Score", f"{report.risk_score}/100"],
        ["Total Findings", str(len(report.findings))],
        ["Hidden Endpoints", str(len(report.hidden_endpoints))],
        ["Sensitive Fields", ", ".join(report.sensitive_fields_accessed) or "None"],
    ]
    summary_table = Table(summary_data, colWidths=[2 * inch, 4 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    # Findings
    if report.findings:
        story.append(Paragraph("Security Findings", styles["Heading1"]))
        finding_data = [["Severity", "Category", "Endpoint", "Title"]]
        for f in report.findings:
            finding_data.append(
                [
                    f.severity.value.upper(),
                    f.category.value.replace("_", " ").title(),
                    f.endpoint[:40] + ("…" if len(f.endpoint) > 40 else ""),
                    f.title[:50] + ("…" if len(f.title) > 50 else ""),
                ]
            )
        findings_table = Table(
            finding_data,
            colWidths=[1 * inch, 1.5 * inch, 1.8 * inch, 2.2 * inch],
        )
        findings_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightyellow]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(findings_table)
        story.append(Spacer(1, 0.3 * inch))

    # Compliance
    if report.compliance_reports:
        story.append(Paragraph("Compliance Summary", styles["Heading1"]))
        comp_data = [["Standard", "Status", "Passed", "Failed", "Warned"]]
        for cr in report.compliance_reports:
            comp_data.append(
                [
                    cr.standard.value.upper(),
                    cr.overall_status.value.upper(),
                    str(cr.passed),
                    str(cr.failed),
                    str(cr.warned),
                ]
            )
        comp_table = Table(comp_data, colWidths=[1.2 * inch, 1.2 * inch, 1 * inch, 1 * inch, 1 * inch])
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkgreen),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(comp_table)

    doc.build(story)
    return buffer.getvalue()
