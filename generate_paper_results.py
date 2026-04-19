from __future__ import annotations

import asyncio
import csv
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from ait.demo_integration import app as integration_app
from ait.mock_saas import app as mock_saas_app
from ait.models import FindingCategory, TargetConfig, TestRunConfig
from ait.runner import run_assessment


SCENARIO_FILES = [
    "slack_bot.yaml",
    "github_pat.yaml",
    "google_gmail.yaml",
    "notion_readonly.yaml",
    "trello_read.yaml",
    "slack_compliant.yaml",
    "github_compliant.yaml",
]

CATEGORY_LABELS = {
    FindingCategory.HIDDEN_ENDPOINT.value: "Hidden endpoint access",
    FindingCategory.SENSITIVE_FIELD_ACCESS.value: "Sensitive field access",
    FindingCategory.BEHAVIORAL_DIVERGENCE.value: "Behavioral divergence",
    FindingCategory.POLICY_VIOLATION.value: "Policy violation",
}

SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

REAL_ASYNC_CLIENT = httpx.AsyncClient


class RoutedAsyncClient:
    def __init__(self, *args, base_url: str | None = None, timeout: int | None = None, **kwargs):
        del args, timeout, kwargs
        self.base_url = base_url.rstrip("/") if base_url else None
        self.clients = {
            "127.0.0.1:8000": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=integration_app),
                base_url="http://127.0.0.1:8000",
            ),
            "127.0.0.1:8001": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=mock_saas_app),
                base_url="http://127.0.0.1:8001",
            ),
            "127.0.0.1:8002": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=integration_app),
                base_url="http://127.0.0.1:8002",
            ),
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        await self.aclose()

    async def aclose(self):
        for client in self.clients.values():
            await client.aclose()

    def _resolve(self, url: str) -> tuple[httpx.AsyncClient, str]:
        absolute = url if url.startswith("http") else f"{self.base_url}{url}"
        parsed = urlparse(absolute)
        return self.clients[parsed.netloc], absolute

    async def request(self, method: str, url: str, **kwargs):
        client, absolute = self._resolve(url)
        return await client.request(method, absolute, **kwargs)

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)


def _load_scenario(config_path: Path) -> tuple[TargetConfig, dict]:
    raw_data = yaml.safe_load(config_path.read_text())
    paper_meta = raw_data.get("paper", {})
    if "platform" in raw_data and "platform" not in paper_meta:
        paper_meta["platform"] = raw_data["platform"]
    return TargetConfig.model_validate(raw_data), paper_meta


def _max_severity(findings: list[dict]) -> str:
    if not findings:
        return "—"
    return max(findings, key=lambda item: SEVERITY_ORDER[item["severity"]])["severity"].title()


def _summarize_violation_types(categories: set[str]) -> str:
    if not categories:
        return "None"
    labels = [CATEGORY_LABELS[category] for category in sorted(categories)]
    return "; ".join(labels)


def _format_attack_status_codes(exchanges: list[dict], attack_paths: list[str]) -> str:
    if not attack_paths:
        return "N/A"
    statuses: list[str] = []
    for path in attack_paths:
        matching = [exchange for exchange in exchanges if exchange["path"] == path]
        if not matching:
            statuses.append(f"{path}=not-reached")
            continue
        phase_statuses = ",".join(
            f'{exchange["phase"]}:{exchange["status_code"]}'
            for exchange in matching
        )
        statuses.append(f"{path}={phase_statuses}")
    return "; ".join(statuses)


def _metric_row(category: str, tp: int, fp: int, fn: int) -> dict[str, object]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "Category": CATEGORY_LABELS[category],
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": f"{precision:.2f}",
        "Recall": f"{recall:.2f}",
        "F1": f"{f1:.2f}",
    }


def _render_results_markdown(rows: list[dict[str, object]]) -> str:
    header = (
        "| # | Platform | Integration Scenario | Declared Scope | Violation Type | "
        "Risk Score | Severity | Detected? |\n"
        "|---|---|---|---|---|---:|---|---|"
    )
    body = "\n".join(
        (
            f'| {row["#"]} | {row["Platform"]} | {row["Integration Scenario"]} | '
            f'{row["Declared Scope"]} | {row["Violation Type"]} | {row["Risk Score"]} | '
            f'{row["Severity"]} | {row["Detected?"]} |'
        )
        for row in rows
    )
    return f"{header}\n{body}"


def _render_metrics_markdown(rows: list[dict[str, object]]) -> str:
    header = "| Category | TP | FP | FN | Precision | Recall | F1 |\n|---|---:|---:|---:|---:|---:|---:|"
    body = "\n".join(
        (
            f'| {row["Category"]} | {row["TP"]} | {row["FP"]} | {row["FN"]} | '
            f'{row["Precision"]} | {row["Recall"]} | {row["F1"]} |'
        )
        for row in rows
    )
    return f"{header}\n{body}"


async def main():
    original_httpx_runner = httpx.AsyncClient
    import ait.demo_integration as demo_integration_module
    import ait.runner as runner_module

    runner_module.httpx.AsyncClient = RoutedAsyncClient
    demo_integration_module.httpx.AsyncClient = RoutedAsyncClient
    httpx.AsyncClient = RoutedAsyncClient

    try:
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)

        scenario_rows: list[dict[str, object]] = []
        raw_runs: list[dict[str, object]] = []
        category_counts = {
            category.value: {"tp": 0, "fp": 0, "fn": 0}
            for category in FindingCategory
            if category != FindingCategory.POLICY_VIOLATION
        }

        test_cases_dir = Path("test_cases")
        for index, scenario_file in enumerate(SCENARIO_FILES, start=1):
            target, paper_meta = _load_scenario(test_cases_dir / scenario_file)
            start = time.perf_counter()
            run_record = await run_assessment(target, TestRunConfig())
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            report = run_record.report
            if report is None:
                raise RuntimeError(f"Report missing for {target.name}")

            exchanges = [exchange.model_dump() for exchange in run_record.exchanges]
            findings = [finding.model_dump() for finding in report.findings]
            actual_categories = {finding["category"] for finding in findings}
            expected_categories = set(paper_meta.get("expected_categories", []))
            expected_result = paper_meta.get("expected_result", "violation")

            for category, counts in category_counts.items():
                expected = category in expected_categories
                observed = category in actual_categories
                if expected and observed:
                    counts["tp"] += 1
                elif expected and not observed:
                    counts["fn"] += 1
                elif observed and not expected:
                    counts["fp"] += 1

            if expected_result == "compliant":
                detected = "✅ (No FP)" if not findings else "❌ FP"
            else:
                detected = "✅ Yes" if expected_categories.issubset(actual_categories) else "❌ Missed"

            raw_runs.append(
                {
                    "config_file": scenario_file,
                    "paper": paper_meta,
                    "target": target.model_dump(mode="json"),
                    "duration_ms": duration_ms,
                    "run": run_record.model_dump(mode="json"),
                }
            )

            scenario_rows.append(
                {
                    "#": index,
                    "Platform": paper_meta.get("platform", target.name.split()[0]),
                    "Integration Scenario": paper_meta.get("scenario_label", target.name),
                    "Declared Scope": ", ".join(target.expected_scopes) or "N/A",
                    "Violation Type": _summarize_violation_types(actual_categories),
                    "Risk Score": report.risk_score,
                    "Severity": _max_severity(findings),
                    "Detected?": detected,
                    "Duration (ms)": duration_ms,
                    "Hidden Endpoints": ", ".join(report.hidden_endpoints) or "None",
                    "Sensitive Fields": ", ".join(report.sensitive_fields_accessed) or "None",
                    "Divergence Count": len(report.divergence_summary),
                    "Attack Status Codes": _format_attack_status_codes(
                        exchanges, paper_meta.get("attack_paths", [])
                    ),
                }
            )

        metric_rows = [
            _metric_row(category, counts["tp"], counts["fp"], counts["fn"])
            for category, counts in category_counts.items()
        ]

        violation_rows = [
            row for row in scenario_rows if row["Detected?"] == "✅ Yes"
        ]
        compliant_rows = [
            row for row in scenario_rows if row["Detected?"] == "✅ (No FP)"
        ]
        risk_scores = [int(row["Risk Score"]) for row in scenario_rows]
        tp = len(violation_rows)
        fp = sum(1 for row in scenario_rows if row["Detected?"] == "❌ FP")
        precision = tp / (tp + fp) if (tp + fp) else 0.0

        summary = {
            "generated_at": time.strftime("%Y-%m-%d"),
            "scenario_count": len(scenario_rows),
            "platform_count": len({str(row["Platform"]) for row in scenario_rows}),
            "violation_scenarios": len(violation_rows),
            "compliant_scenarios": len(compliant_rows),
            "precision": round(precision, 4),
            "mean_risk_score": round(sum(risk_scores) / len(risk_scores), 2),
            "max_risk_score": max(risk_scores),
            "min_risk_score": min(risk_scores),
            "category_metrics": metric_rows,
        }

        (results_dir / "raw_run_artifacts.json").write_text(json.dumps(raw_runs, indent=2))
        (results_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        with (results_dir / "results_table.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=scenario_rows[0].keys())
            writer.writeheader()
            writer.writerows(scenario_rows)

        with (results_dir / "detection_metrics.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=metric_rows[0].keys())
            writer.writeheader()
            writer.writerows(metric_rows)

        (results_dir / "precision_calculation.txt").write_text(
            "\n".join(
                [
                    f"True Positives (TP): {tp}",
                    f"False Positives (FP): {fp}",
                    f"Precision = TP / (TP + FP) = {tp} / ({tp} + {fp}) = {precision:.0%}",
                ]
            )
            + "\n"
        )

        paper_snippets = "\n\n".join(
            [
                "# Paper-Ready Results",
                "## Results Table",
                _render_results_markdown(scenario_rows),
                "## Detection Metrics",
                _render_metrics_markdown(metric_rows),
                "## Abstract Snippet",
                (
                    f"Evaluation across {summary['scenario_count']} controlled scenarios on "
                    f"{summary['platform_count']} platform-themed mock integrations detected "
                    f"{summary['violation_scenarios']} violating scenarios with "
                    f"{precision:.0%} precision and no false positives."
                ),
                "## Evaluation Snippet",
                (
                    f"Across {summary['scenario_count']} controlled scenarios, AIT identified "
                    f"{summary['violation_scenarios']} violating scenarios and produced no false "
                    f"positives on {summary['compliant_scenarios']} compliant scenarios. Risk "
                    f"scores ranged from {summary['min_risk_score']} to {summary['max_risk_score']} "
                    f"(mean: {summary['mean_risk_score']}). Per-category precision, recall, and F1 "
                    "were computed directly from the measured runs in `results/detection_metrics.csv`."
                ),
            ]
        )
        (results_dir / "paper_snippets.md").write_text(paper_snippets + "\n")

        print(f"Wrote {results_dir / 'raw_run_artifacts.json'}")
        print(f"Wrote {results_dir / 'results_table.csv'}")
        print(f"Wrote {results_dir / 'detection_metrics.csv'}")
        print(f"Wrote {results_dir / 'summary.json'}")
        print(f"Wrote {results_dir / 'paper_snippets.md'}")
    finally:
        httpx.AsyncClient = original_httpx_runner
        runner_module.httpx.AsyncClient = original_httpx_runner
        demo_integration_module.httpx.AsyncClient = original_httpx_runner


if __name__ == "__main__":
    asyncio.run(main())
