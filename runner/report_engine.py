"""
Phase 6 – Reporting Engine
Generates JSON + Markdown reports from collected findings.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ReportEngine:
    """
    Compiles all findings into structured JSON and human-readable Markdown reports.
    """

    SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def build_report(
        self,
        *,
        target_name: str,
        config: Dict[str, Any],
        fuzzer_results: List[Dict[str, Any]],
        taint_results: List[Dict[str, Any]],
        taint_leaks: List[Dict[str, Any]],
        analyzer_findings: List[Dict[str, Any]],
        divergence_anomalies: List[Dict[str, Any]],
        elapsed_seconds: float,
    ) -> Dict[str, Any]:
        """Assemble the master report dict."""

        endpoints_tested = list({r["endpoint"] for r in fuzzer_results + taint_results})
        all_findings = analyzer_findings + divergence_anomalies

        # Deduplicate by (type, endpoint, frozenset of relevant sub-keys)
        unique_findings = self._deduplicate(all_findings)

        critical = [f for f in unique_findings if f.get("severity") == "CRITICAL"]
        high      = [f for f in unique_findings if f.get("severity") == "HIGH"]
        taint_high = [l for l in taint_leaks if l.get("severity") == "HIGH"]

        risk = self._compute_risk(critical, high, taint_high)

        report = {
            "meta": {
                "target": target_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": round(elapsed_seconds, 2),
            },
            "summary": {
                "endpoints_tested": len(endpoints_tested),
                "total_requests": len(fuzzer_results) + len(taint_results),
                "total_findings": len(unique_findings),
                "critical_findings": len(critical),
                "high_findings": len(high),
                "taint_leaks_detected": len(taint_leaks),
                "unexpected_taint_leaks": len(taint_high),
                "risk_level": risk,
            },
            "endpoints_tested": sorted(endpoints_tested),
            "findings": sorted(unique_findings, key=lambda f: self.SEVERITY_ORDER.get(f.get("severity", "LOW"), 99)),
            "taint_leaks": taint_leaks,
            "metrics": {
                "endpoints_tested": len(endpoints_tested),
                "anomalies_detected": len(unique_findings),
                "taint_leaks": len(taint_leaks),
                "execution_time_sec": round(elapsed_seconds, 2),
            },
        }
        return report

    def save_json(self, report: Dict[str, Any], filename: Optional[str] = None) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"report_{ts}.json"
        path  = os.path.join(self.output_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return path

    def save_markdown(self, report: Dict[str, Any], filename: Optional[str] = None) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"report_{ts}.md"
        path  = os.path.join(self.output_dir, fname)
        md = self._render_markdown(report)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path

    # ── Markdown renderer ──────────────────────────────────────────────────────

    def _render_markdown(self, r: Dict[str, Any]) -> str:
        meta    = r["meta"]
        summary = r["summary"]
        findings = r.get("findings", [])
        leaks    = r.get("taint_leaks", [])

        risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(
            summary["risk_level"], "⚪"
        )

        lines = [
            f"# Adversarial Integration Test Report",
            f"",
            f"> **Target:** {meta['target']}  ",
            f"> **Generated:** {meta['generated_at']}  ",
            f"> **Execution Time:** {meta['elapsed_seconds']}s  ",
            f"",
            f"---",
            f"",
            f"## 📊 Executive Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Endpoints Tested | {summary['endpoints_tested']} |",
            f"| Total Requests Sent | {summary['total_requests']} |",
            f"| Total Findings | {summary['total_findings']} |",
            f"| Critical Findings | {summary['critical_findings']} |",
            f"| High Findings | {summary['high_findings']} |",
            f"| Taint Leaks Detected | {summary['taint_leaks_detected']} |",
            f"| Unexpected Taint Leaks | {summary['unexpected_taint_leaks']} |",
            f"| **Risk Level** | {risk_emoji} **{summary['risk_level']}** |",
            f"",
            f"---",
            f"",
            f"## 🌐 Endpoints Tested",
            f"",
        ]

        for ep in r.get("endpoints_tested", []):
            lines.append(f"- `{ep}`")

        lines += [
            f"",
            f"---",
            f"",
            f"## 🚨 Findings ({len(findings)} total)",
            f"",
        ]

        if not findings:
            lines.append("_No findings detected._")
        else:
            for i, f in enumerate(findings, 1):
                sev = f.get("severity", "UNKNOWN")
                sev_badge = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")
                lines.append(f"### {i}. {sev_badge} [{sev}] {f.get('type','UNKNOWN')}")
                lines.append(f"")
                lines.append(f"- **Endpoint:** `{f.get('endpoint','?')}`")
                lines.append(f"- **Strategy:** `{f.get('strategy','?')}`")
                lines.append(f"- **Detail:** {f.get('detail','')}")
                for key in ("unexpected_fields", "exposed_fields", "extra_fields",
                            "missing_fields", "extra_fields"):
                    if key in f:
                        lines.append(f"- **{key.replace('_',' ').title()}:** {', '.join(f'`{x}`' for x in f[key])}")
                lines.append(f"")

        lines += [
            f"---",
            f"",
            f"## 🧪 Taint Leak Analysis ({len(leaks)} leaks)",
            f"",
        ]

        if not leaks:
            lines.append("_No taint leaks detected._")
        else:
            for leak in leaks:
                flag = "⚠️ UNEXPECTED" if leak.get("unexpected") else "ℹ️ expected"
                lines.append(f"- **{flag}** | Taint `{leak['taint_id']}` (field: `{leak['field']}`) "
                             f"found in `{leak['found_in_endpoint']}` | Severity: **{leak['severity']}**")

        lines += [
            f"",
            f"---",
            f"",
            f"## 📈 Metrics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
        ]
        for k, v in r.get("metrics", {}).items():
            lines.append(f"| {k.replace('_',' ').title()} | {v} |")

        lines += [
            f"",
            f"---",
            f"",
            f"_Report generated by Adversarial Integration Tester v1.0_",
        ]

        return "\n".join(lines)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _deduplicate(self, findings: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for f in findings:
            key = (f.get("type"), f.get("endpoint"), f.get("severity"))
            sub = tuple(sorted(
                f.get("unexpected_fields", []) +
                f.get("exposed_fields", []) +
                f.get("extra_fields", [])
            ))
            full_key = key + sub
            if full_key not in seen:
                seen.add(full_key)
                unique.append(f)
        return unique

    def _compute_risk(self, critical, high, taint_high) -> str:
        if critical or taint_high:
            return "CRITICAL"
        if high:
            return "HIGH"
        return "MEDIUM"
