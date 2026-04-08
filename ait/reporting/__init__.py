from __future__ import annotations

from html import escape

from ait.models import RunReport

# Re-export original function for backward compatibility
__all__ = ["render_html_report", "render_dashboard_html"]


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
    compliance_html = ""
    if report.compliance_reports:
        rows = "".join(
            f"<tr><td>{escape(cr.standard.value.upper())}</td>"
            f"<td>{escape(cr.overall_status.value.upper())}</td>"
            f"<td>{cr.passed}</td><td>{cr.failed}</td><td>{cr.warned}</td></tr>"
            for cr in report.compliance_reports
        )
        compliance_html = f"""
  <div class="card">
    <h2>Compliance Summary</h2>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
      <thead><tr><th>Standard</th><th>Status</th><th>Passed</th><th>Failed</th><th>Warned</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AIT Report {escape(report.run_id)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; background: #faf7f1; color: #182027; }}
    .card {{ background: white; padding: 1.25rem; border-radius: 12px; margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }}
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
  {compliance_html}
</body>
</html>"""


def render_dashboard_html(report: RunReport) -> str:
    """Render an interactive HTML dashboard with charts and metrics."""
    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for f in report.findings:
        severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1
        category_counts[f.category.value] = category_counts.get(f.category.value, 0) + 1

    sev_labels = list(severity_counts.keys())
    sev_values = list(severity_counts.values())
    cat_labels = list(category_counts.keys())
    cat_values = list(category_counts.values())

    endpoint_rows = "".join(
        f"<tr><td>{escape(ep)}</td><td>{'⚠️ Hidden' if ep in report.hidden_endpoints else '✅ Expected'}</td></tr>"
        for ep in report.reached_endpoints
    )

    compliance_rows = ""
    if report.compliance_reports:
        for cr in report.compliance_reports:
            status_emoji = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(cr.overall_status.value, "❓")
            compliance_rows += (
                f"<tr><td>{escape(cr.standard.value.upper())}</td>"
                f"<td>{status_emoji} {escape(cr.overall_status.value.upper())}</td>"
                f"<td>{cr.passed}/{cr.passed + cr.failed + cr.warned}</td></tr>"
            )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AIT Dashboard – {escape(report.run_id)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; background: #f0f4f8; color: #1a202c; }}
    h1 {{ color: #2d3748; }} h2 {{ color: #4a5568; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
    .card {{ background: white; padding: 1.5rem; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
    .metric {{ font-size: 3rem; font-weight: bold; color: #e53e3e; }}
    .metric.ok {{ color: #38a169; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid #e2e8f0; text-align: left; }}
    th {{ background: #f7fafc; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>🔍 AIT Security Dashboard</h1>
  <p><strong>Run:</strong> {escape(report.run_id)} &nbsp;|&nbsp;
     <strong>Target:</strong> {escape(report.target_name)} &nbsp;|&nbsp;
     <strong>Status:</strong> {escape(report.status)}</p>

  <div class="grid">
    <div class="card">
      <h2>Risk Score</h2>
      <div class="metric {'ok' if report.risk_score < 50 else ''}">{report.risk_score}<span style="font-size:1.5rem">/100</span></div>
    </div>
    <div class="card">
      <h2>Findings by Severity</h2>
      <canvas id="sevChart" height="200"></canvas>
    </div>
    <div class="card">
      <h2>Findings by Category</h2>
      <canvas id="catChart" height="200"></canvas>
    </div>
    <div class="card">
      <h2>Endpoint Access Heat Map</h2>
      <table>
        <thead><tr><th>Endpoint</th><th>Status</th></tr></thead>
        <tbody>{endpoint_rows}</tbody>
      </table>
    </div>
  </div>

  {"<div class='card' style='margin-top:1.5rem'><h2>Compliance Summary</h2><table><thead><tr><th>Standard</th><th>Status</th><th>Controls Passed</th></tr></thead><tbody>" + compliance_rows + "</tbody></table></div>" if compliance_rows else ""}

  <script>
    new Chart(document.getElementById('sevChart'), {{
      type: 'doughnut',
      data: {{
        labels: {sev_labels},
        datasets: [{{ data: {sev_values}, backgroundColor: ['#fc8181','#f6ad55','#68d391','#63b3ed'] }}]
      }},
      options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
    }});
    new Chart(document.getElementById('catChart'), {{
      type: 'bar',
      data: {{
        labels: {cat_labels},
        datasets: [{{ label: 'Count', data: {cat_values}, backgroundColor: '#667eea' }}]
      }},
      options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
    }});
  </script>
</body>
</html>"""
