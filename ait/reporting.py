from __future__ import annotations

from html import escape

from ait.models import RunReport


def render_html_report(report: RunReport) -> str:
    findings_html = "".join(
        (
            "<li>"
            f"<strong>{escape(finding.severity.value.upper())}</strong> "
            f"{escape(finding.title)}<br>"
            f"<code>{escape(finding.endpoint)}</code><br>"
            f"{escape(finding.observed_behavior)}"
            "</li>"
        )
        for finding in report.findings
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AIT Report {escape(report.run_id)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; background: #faf7f1; color: #182027; }}
    .card {{
      background: white; padding: 1.25rem; border-radius: 12px;
      margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }}
    code {{ background: #f1efe8; padding: 0.125rem 0.25rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Adversarial Integration Tester Report</h1>
    <p><strong>Run ID:</strong> {escape(report.run_id)}</p>
    <p><strong>Target:</strong> {escape(report.target_name)}</p>
    <p><strong>Risk score:</strong> {report.risk_score}</p>
    <p><strong>Status:</strong> {escape(report.status)}</p>
  </div>
  <div class="card">
    <h2>Hidden Endpoints</h2>
    <p>{", ".join(escape(item) for item in report.hidden_endpoints) or "None"}</p>
    <h2>Sensitive Fields Accessed</h2>
    <p>{", ".join(escape(item) for item in report.sensitive_fields_accessed) or "None"}</p>
    <h2>Divergence Summary</h2>
    <p>{", ".join(escape(item) for item in report.divergence_summary) or "None"}</p>
  </div>
  <div class="card">
    <h2>Findings</h2>
    <ol>{findings_html}</ol>
  </div>
</body>
</html>"""
