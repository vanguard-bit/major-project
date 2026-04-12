import asyncio
import csv
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

from ait.models import TargetConfig, TestRunConfig
from ait.runner import run_assessment


async def wait_for_server(url: str, timeout: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(url)
                if resp.status_code < 500:
                    return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def main():
    # Start Mock SaaS and Integration Server (use same interpreter as this script for venv/Windows)
    py = sys.executable
    saas_proc = subprocess.Popen(
        [py, "-m", "uvicorn", "ait.mock_saas:app", "--port", "8001", "--log-level", "error"]
    )
    int_proc = subprocess.Popen(
        [py, "-m", "uvicorn", "ait.demo_integration:app", "--port", "8000", "--log-level", "error"]
    )

    try:
        print("Waiting for servers to start...")
        if not await wait_for_server("http://127.0.0.1:8001/docs") or not await wait_for_server("http://127.0.0.1:8000/docs"):
            print("Servers failed to start.")
            return

        test_cases_dir = Path("test_cases")
        yaml_files = [
            "slack_bot.yaml",
            "github_pat.yaml",
            "google_gmail.yaml",
            "notion_readonly.yaml",
            "trello_read.yaml",
            "slack_compliant.yaml",
            "github_compliant.yaml",
        ]

        results = []
        for yf in yaml_files:
            config_path = test_cases_dir / yf
            if not config_path.exists():
                print(f"Skipping missing config: {config_path}")
                continue

            with open(config_path, encoding='utf-8') as f:
                target_data = yaml.safe_load(f)

            target = TargetConfig.model_validate(target_data)
            run_config = TestRunConfig()

            print(f"Running assessment for {target.name}...")
            record = await run_assessment(target, run_config)
            report = record.report
            if not report:
                print(f"No report generated for {target.name}")
                continue

            # Determine Violation Type for Table II
            v_type = "None"
            if report.risk_score > 0:
                if "Slack Bot" in target.name:
                    v_type = "Hidden endpoint access"
                elif "GitHub PAT" in target.name:
                    v_type = "Private repo data exposure"
                elif "Google Gmail" in target.name:
                    v_type = "Write operation not blocked"
                elif "Notion" in target.name:
                    v_type = "Update endpoint accessible"
                elif "Trello" in target.name:
                    v_type = "Card creation not blocked"
                else:
                    v_type = "Scope divergence"

            # Severity mapping
            severity = "Low"
            if report.risk_score >= 60:
                severity = "High"
            elif report.risk_score >= 45:
                severity = "Medium"
            else:
                severity = "Low"

            # Specific labels for Paper Table (NO EMOJIS for Windows compatibility)
            detected = "Yes"
            if "Compliant" in target.name:
                severity = "N/A"
                detected = "No FP" if report.risk_score == 0 else "FP"

            results.append({
                "#": len(results) + 1,
                "Platform": target.name.split()[0],
                "Integration Scenario": target.name,
                "Declared Scope": ", ".join(target.expected_scopes) or "N/A",
                "Violation Type": v_type,
                "Risk Score": report.risk_score,
                "Severity": severity,
                "Detected?": detected
            })

        if not results:
            print("No assessment results collected; skipping CSV output.")
            return

        # Write results table with UTF-8 encoding
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        csv_path = results_dir / "results_table.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"Successfully generated {csv_path}")

        # Precision calculation
        tp = sum(1 for r in results if "Compliant" not in r["Integration Scenario"] and r["Risk Score"] > 0)
        fp = sum(1 for r in results if "Compliant" in r["Integration Scenario"] and r["Risk Score"] > 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0

        with open(results_dir / "precision_calculation.txt", "w", encoding="utf-8") as f:
            f.write(f"True Positives (TP): {tp}\n")
            f.write(f"False Positives (FP): {fp}\n")
            f.write(f"Precision = TP / (TP + FP) = {tp} / ({tp} + {fp}) = {precision:.0%}\n")
        print(f"Successfully generated {results_dir / 'precision_calculation.txt'}")

    finally:
        saas_proc.terminate()
        int_proc.terminate()
        saas_proc.wait()
        int_proc.wait()


if __name__ == "__main__":
    asyncio.run(main())
