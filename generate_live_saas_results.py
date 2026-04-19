from __future__ import annotations

import asyncio
import csv
import json
import os
import time
from pathlib import Path

import yaml
from pydantic import ValidationError

from ait.live_runner import LiveScenario, run_live_assessment
from ait.models import TestRunConfig


LIVE_TEST_CASES_DIR = Path("live_test_cases")
LIVE_RESULTS_DIR = Path("results/live_saas")
DOTENV_FILES = [Path(".env.live"), Path(".env")]


def _load_dotenv() -> None:
    for dotenv_path in DOTENV_FILES:
        if not dotenv_path.exists():
            continue
        for line in dotenv_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _load_scenario(path: Path) -> tuple[LiveScenario, dict]:
    raw = yaml.safe_load(path.read_text())
    return LiveScenario.model_validate(raw), raw.get("paper", {})


def _severity(findings: list[dict]) -> str:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if not findings:
        return "—"
    return max(findings, key=lambda item: order[item["severity"]])["severity"].title()


def _violation_type(report: dict) -> str:
    labels: list[str] = []
    if report["hidden_endpoints"]:
        labels.append("Hidden endpoint access")
    if report["sensitive_fields_accessed"]:
        labels.append("Sensitive field access")
    if report["divergence_summary"]:
        labels.append("Behavioral divergence")
    findings = report.get("findings", [])
    if any(finding.get("category") == "policy_violation" for finding in findings):
        labels.append("Policy violation")
    return "; ".join(labels) if labels else "None"


async def main() -> None:
    _load_dotenv()
    LIVE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (LIVE_RESULTS_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Live SaaS Results",
                "",
                "This directory contains only measured live-run outputs.",
                "Skipped scenarios indicate missing credentials, schema problems, or execution failures.",
            ]
        )
        + "\n"
    )

    results_rows: list[dict[str, object]] = []
    raw_runs: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []

    scenario_files = sorted(LIVE_TEST_CASES_DIR.glob("*.yaml"))
    if not scenario_files:
        summary = {
            "generated_at": time.strftime("%Y-%m-%d"),
            "executed_scenarios": 0,
            "skipped_scenarios": 0,
            "reason": "No live scenario YAML files were found in live_test_cases/.",
        }
        (LIVE_RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
        return

    for index, scenario_path in enumerate(scenario_files, start=1):
        try:
            scenario, paper = _load_scenario(scenario_path)
        except ValidationError as exc:
            skipped.append({"config_file": scenario_path.name, "reason": f"schema error: {exc.errors()}"})
            continue

        if not os.getenv(scenario.auth_env_var):
            skipped.append(
                {
                    "config_file": scenario_path.name,
                    "reason": f"missing auth env var {scenario.auth_env_var}",
                }
            )
            continue

        started = time.perf_counter()
        try:
            run = await run_live_assessment(scenario, TestRunConfig())
        except Exception as exc:  # noqa: BLE001
            skipped.append({"config_file": scenario_path.name, "reason": f"execution error: {type(exc).__name__}: {exc}"})
            continue
        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        report = run.report
        if report is None:
            skipped.append({"config_file": scenario_path.name, "reason": "missing report"})
            continue

        report_dump = report.model_dump(mode="json")
        findings = [finding.model_dump(mode="json") for finding in run.findings]
        attack_requests = [request for request in scenario.requests if request.expected_behavior == "denied"]
        attack_statuses = []
        for attack_request in attack_requests:
            path = attack_request.path if attack_request.path.startswith("/") else f"/{attack_request.path}"
            matches = [exchange for exchange in run.exchanges if exchange.path == path]
            if matches:
                attack_statuses.append(
                    f"{path}=" + ",".join(f"{entry.phase}:{entry.status_code}" for entry in matches)
                )
            else:
                attack_statuses.append(f"{path}=not-reached")

        results_rows.append(
            {
                "#": index,
                "Platform": paper.get("platform", scenario.target.name),
                "Integration Scenario": paper.get("scenario_label", scenario.target.name),
                "Declared Scope": ", ".join(scenario.target.expected_scopes) or "N/A",
                "Violation Type": _violation_type(report_dump),
                "Risk Score": report.risk_score,
                "Severity": _severity(findings),
                "Detected?": "✅ Yes" if report.risk_score > 0 else "No findings",
                "Duration (ms)": duration_ms,
                "Hidden Endpoints": ", ".join(report.hidden_endpoints) or "None",
                "Sensitive Fields": ", ".join(report.sensitive_fields_accessed) or "None",
                "Attack Status Codes": "; ".join(attack_statuses) or "N/A",
                "Config File": scenario_path.name,
            }
        )
        raw_runs.append(
            {
                "config_file": scenario_path.name,
                "paper": paper,
                "run": run.model_dump(mode="json"),
            }
        )

    summary = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "executed_scenarios": len(results_rows),
        "skipped_scenarios": len(skipped),
        "skipped": skipped,
    }

    (LIVE_RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    (LIVE_RESULTS_DIR / "raw_run_artifacts.json").write_text(json.dumps(raw_runs, indent=2))
    (LIVE_RESULTS_DIR / "skipped.json").write_text(json.dumps(skipped, indent=2))

    if results_rows:
        with (LIVE_RESULTS_DIR / "results_table.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=results_rows[0].keys())
            writer.writeheader()
            writer.writerows(results_rows)

    paper_note_lines = [
        "# Live SaaS Results",
        "",
        f"Executed scenarios: {len(results_rows)}",
        f"Skipped scenarios: {len(skipped)}",
        "",
        "This directory contains only measured live-run outputs. Skipped scenarios indicate missing credentials, schema problems, or execution failures.",
    ]
    (LIVE_RESULTS_DIR / "README.md").write_text("\n".join(paper_note_lines) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
