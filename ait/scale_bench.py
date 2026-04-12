"""Synthetic scalability check for the Analysis Engine (no network)."""

from __future__ import annotations

import time
from statistics import mean

from ait.analysis import analyze_run
from ait.models import CapturedExchange, TargetConfig, TokenConfig


def build_scale_fixture(allowlisted: int, run_id: str = "scalebench") -> tuple[TargetConfig, list[CapturedExchange]]:
    """``allowlisted`` paths plus one undeclared path (hidden endpoint)."""
    paths = [f"/ep/{i}" for i in range(allowlisted)]
    hidden = "/ep/unlisted"
    exchanges: list[CapturedExchange] = []
    for phase in ("baseline", "mutated"):
        for p in paths:
            exchanges.append(
                CapturedExchange(
                    run_id=run_id,
                    phase=phase,
                    method="GET",
                    path=p,
                    status_code=200,
                    response_body={},
                    extracted_fields=[],
                    contains_sensitive_marker=False,
                )
            )
        exchanges.append(
            CapturedExchange(
                run_id=run_id,
                phase=phase,
                method="GET",
                path=hidden,
                status_code=200,
                response_body={},
                extracted_fields=[],
                contains_sensitive_marker=False,
            )
        )
    target = TargetConfig(
        name="Synthetic Scale",
        base_url="http://127.0.0.1:8001",
        integration_sync_url="http://127.0.0.1:8000/sync",
        audit_base_url="http://127.0.0.1:8001/",
        token_config=TokenConfig(token="demo-static-access-token"),
        expected_endpoints=paths,
        sensitive_markers=[],
    )
    return target, exchanges


def time_analyze_ms(allowlisted: int, repeats: int = 40) -> tuple[float, int, int]:
    target, exchanges = build_scale_fixture(allowlisted)
    durations: list[float] = []
    report = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        report = analyze_run("scalebench", target, exchanges)
        durations.append((time.perf_counter() - t0) * 1000)
    assert report is not None
    return mean(durations), len(report.findings), report.risk_score


def tabulate_rows() -> list[tuple[int, float, int, int]]:
    rows: list[tuple[int, float, int, int]] = []
    for n in (10, 50, 100):
        ms, findings, risk = time_analyze_ms(n)
        rows.append((n, round(ms, 3), findings, risk))
    return rows
