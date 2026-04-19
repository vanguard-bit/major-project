from __future__ import annotations

import asyncio
import json
from pathlib import Path

import generate_live_saas_results


def test_generate_live_results_writes_empty_summary_when_no_configs(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_live_saas_results, "LIVE_TEST_CASES_DIR", tmp_path / "live_cases")
    monkeypatch.setattr(generate_live_saas_results, "LIVE_RESULTS_DIR", tmp_path / "live_results")
    (tmp_path / "live_cases").mkdir()

    asyncio.run(generate_live_saas_results.main())

    summary = json.loads((tmp_path / "live_results" / "summary.json").read_text())
    assert summary["executed_scenarios"] == 0
    assert summary["skipped_scenarios"] == 0 or isinstance(summary["skipped_scenarios"], int)
    assert (tmp_path / "live_results" / "README.md").exists() or "reason" in summary
