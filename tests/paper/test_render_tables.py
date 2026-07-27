"""Golden-file style tests for paper table rendering."""

from __future__ import annotations

from pathlib import Path

from ait.paper.render_tables import (
    GENERATED_HEADER_PREFIX,
    format_metric,
    format_risk,
    latex_escape,
    render_all,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "paper"


def test_render_all_writes_expected_fragments(tmp_path: Path):
    out = tmp_path / "generated"
    paths = render_all(FIXTURES / "paper_artifacts.yaml", out, root=FIXTURES)
    names = sorted(p.name for p in paths)
    assert names == sorted(
        [
            "mock_detection_results.tex",
            "platform_scenario_results.tex",
            "live_results.tex",
            "replay_results.tex",
            "risk_sensitivity.tex",
            "benchmark_results.tex",
            "robustness_results.tex",
            "tool_comparison.tex",
            "artifact_provenance.tex",
        ]
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert text.startswith(GENERATED_HEADER_PREFIX)
        assert "ait.paper.render_tables" in text

    mock = (out / "mock_detection_results.tex").read_text(encoding="utf-8")
    assert "1.000" in mock  # P/R/F1 three decimals
    assert "Overall" in mock or "micro" in mock.lower()
    assert "tp=" in mock.lower() or "TP" in mock or "3" in mock

    live = (out / "live_results.tex").read_text(encoding="utf-8")
    assert "NOT RUN" in live
    assert "No FP" not in live

    tools = (out / "tool_comparison.tex").read_text(encoding="utf-8")
    assert "NOT RUN" in tools

    robust = (out / "robustness_results.tex").read_text(encoding="utf-8")
    assert "NOT RUN" in robust

    bench = (out / "benchmark_results.tex").read_text(encoding="utf-8")
    assert "0.040" in bench  # median 0.04 -> three decimals
    assert "0.045" in bench  # p95
    assert "0.001" in bench  # mad

    platform = (out / "platform_scenario_results.tex").read_text(encoding="utf-8")
    assert "40" in platform or "40.00" in platform or "40.0" in platform
    assert "NOT RUN" not in platform or "platform-slack" in platform
    assert "No FP" not in platform

    replay = (out / "replay_results.tex").read_text(encoding="utf-8")
    assert "circleci" in replay.lower()
    assert "exact" in replay.lower() or "match" in replay.lower() or "Yes" in replay


def test_format_helpers():
    assert format_metric(1.0) == "1.000"
    assert format_metric(None) == "---"
    assert format_risk(25.0) == "25"
    assert format_risk(32.5) == "32.50"
    assert format_risk(0.0) == "0"
    assert latex_escape("behavioral_divergence") == r"behavioral\_divergence"


def test_unavailable_rows_never_zero_success(tmp_path: Path):
    out = tmp_path / "generated"
    render_all(FIXTURES / "paper_artifacts.yaml", out, root=FIXTURES)
    live = (out / "live_results.tex").read_text(encoding="utf-8")
    # Must not invent live success
    assert "BLOCKED" in live or "NOT RUN" in live
    for bad in ("No FP", "No finding"):
        assert bad not in live
