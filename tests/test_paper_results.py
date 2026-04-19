from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path

import generate_paper_results


def test_generate_paper_results_outputs_measured_artifacts():
    asyncio.run(generate_paper_results.main())

    summary = json.loads(Path("results/summary.json").read_text())
    assert summary["scenario_count"] == 7
    assert summary["violation_scenarios"] == 5
    assert summary["compliant_scenarios"] == 2
    assert summary["precision"] == 1.0

    metric_rows = list(csv.DictReader(Path("results/detection_metrics.csv").open()))
    assert [row["Category"] for row in metric_rows] == [
        "Hidden endpoint access",
        "Sensitive field access",
        "Behavioral divergence",
    ]
    assert all(row["Precision"] == "1.00" for row in metric_rows)

    result_rows = list(csv.DictReader(Path("results/results_table.csv").open()))
    assert len(result_rows) == 7
    assert sum(row["Detected?"] == "✅ Yes" for row in result_rows) == 5
    assert sum(row["Detected?"] == "✅ (No FP)" for row in result_rows) == 2
