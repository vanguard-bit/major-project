from __future__ import annotations

import json
import math
from pathlib import Path

from typer.testing import CliRunner

from ait.analysis import analyze_run
from ait.experiments.benchmark_analysis import (
    BenchmarkConfig,
    app,
    build_synthetic_case,
    run_benchmark,
    run_benchmark_pipeline,
)


def test_build_synthetic_case_width_and_single_hidden():
    target, exchanges = build_synthetic_case(width=10, seed=20260727)
    assert len(target.expected_endpoints) == 9
    paths = {ex.path for ex in exchanges}
    hidden = paths - set(target.expected_endpoints)
    assert len(hidden) == 1
    report = analyze_run("bench", target, exchanges)
    assert len(report.hidden_endpoints) == 1
    assert report.risk_score == 25.0


def test_run_benchmark_shape_and_positive_durations():
    config = BenchmarkConfig(widths=[10], warmups=1, repetitions=3, seed=20260727)
    summaries = run_benchmark(config)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.width == 10
    assert summary.repetitions == 3
    assert summary.median_ms > 0
    assert summary.p95_ms > 0
    assert summary.mad_ms >= 0
    assert summary.min_ms > 0
    assert summary.max_ms >= summary.min_ms
    assert len(summary.risk_scores) == 3
    assert len(set(summary.risk_scores)) == 1


def test_run_benchmark_independent_percentile_recompute(tmp_path: Path):
    config = BenchmarkConfig(widths=[10], warmups=1, repetitions=3, seed=20260727)
    result = run_benchmark_pipeline(
        config,
        tmp_path,
        command=["python", "-m", "ait.experiments.benchmark_analysis"],
    )
    raw = json.loads(
        (tmp_path / "raw" / "benchmark" / "benchmark_raw.json").read_text(encoding="utf-8")
    )
    durations = raw["payload"]["widths"][0]["durations_ms"]
    assert len(durations) == 3
    sorted_d = sorted(durations)
    idx = max(0, math.ceil(0.95 * len(sorted_d)) - 1)
    expected_p95 = sorted_d[idx]
    assert abs(result[0].p95_ms - expected_p95) < 1e-9
    host = raw["payload"]["host"]
    assert "cpu" in host
    assert "processor_model" in host
    assert host["processor_model"]  # model string or "unknown"
    assert "logical_cpu_count" in host
    assert host["logical_cpu_count"] is None or host["logical_cpu_count"] >= 1
    assert "cpu_affinity" in host
    assert host["cpu_affinity"] == "unknown" or isinstance(host["cpu_affinity"], list)
    assert "os" in host
    assert "python_version" in host
    assert "architecture" in host
    assert "cpu_affinity_set" in host


def test_run_benchmark_asserts_identical_risk_scores(monkeypatch):
    from ait.experiments import benchmark_analysis as ba
    from ait.models import RunReport

    calls = {"n": 0}

    def flaky_analyze(run_id, target, exchanges, weights=None):
        calls["n"] += 1
        score = 25.0 if calls["n"] == 1 else 30.0
        return RunReport(
            run_id=run_id,
            target_name=target.name,
            status="completed",
            reached_endpoints=[],
            hidden_endpoints=["/x"],
            sensitive_fields_accessed=[],
            divergence_summary=[],
            risk_score=score,
            findings=[],
        )

    monkeypatch.setattr(ba, "analyze_run", flaky_analyze)
    config = ba.BenchmarkConfig(widths=[10], warmups=0, repetitions=2, seed=1)
    try:
        ba.run_benchmark(config)
        raised = False
    except ValueError as exc:
        raised = True
        assert "risk score" in str(exc).lower()
    assert raised


def test_benchmark_config_rejects_empty_widths():
    import pytest
    from pydantic import ValidationError

    from ait.experiments.benchmark_analysis import BenchmarkConfig

    with pytest.raises(ValidationError):
        BenchmarkConfig(widths=[], warmups=1, repetitions=1)


def test_benchmark_cli(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--widths",
            "10",
            "--warmups",
            "1",
            "--repetitions",
            "3",
            "--output-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "raw" / "benchmark" / "benchmark_raw.json").is_file()
    assert (tmp_path / "derived" / "benchmark_summary.json").is_file()
