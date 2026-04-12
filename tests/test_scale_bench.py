from __future__ import annotations

from ait.scale_bench import build_scale_fixture, time_analyze_ms


def test_scale_fixture_hidden_endpoint():
    target, exchanges = build_scale_fixture(50)
    assert len(exchanges) == 102  # baseline + mutated, each with 50 allowlisted + 1 hidden
    from ait.analysis import analyze_run

    report = analyze_run("t", target, exchanges)
    assert report.hidden_endpoints == ["/ep/unlisted"]


def test_scale_analysis_stays_fast_enough():
    ms, findings, risk = time_analyze_ms(100, repeats=5)
    assert ms < 500.0
    assert findings > 0
    assert risk == 25
