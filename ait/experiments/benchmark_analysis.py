from __future__ import annotations

import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import typer
from pydantic import BaseModel, Field

from ait.analysis import analyze_run
from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.models import CapturedExchange, TargetConfig

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SEED_DEFAULT = 20260727


class BenchmarkConfig(BaseModel):
    widths: list[int] = Field(default_factory=lambda: [10, 50, 100, 500, 1000])
    warmups: int = 10
    repetitions: int = 100
    seed: int = SEED_DEFAULT


class BenchmarkSummary(BaseModel):
    width: int
    repetitions: int
    median_ms: float
    p95_ms: float
    mad_ms: float
    min_ms: float
    max_ms: float
    risk_scores: list[float]


def build_synthetic_case(width: int, seed: int) -> tuple[TargetConfig, list[CapturedExchange]]:
    if width < 1:
        raise ValueError("width must be >= 1")
    allowed = [f"/api/v1/resources/item-{seed}-{i}" for i in range(width - 1)]
    hidden = f"/reconstruction/hidden/item-{seed}"
    target = TargetConfig.model_validate(
        {
            "name": f"benchmark-w{width}",
            "base_url": "http://benchmark.invalid/",
            "integration_sync_url": "http://benchmark.invalid/sync",
            "audit_base_url": "http://benchmark.invalid/",
            "expected_endpoints": list(allowed),
            "sensitive_markers": [],
        }
    )
    exchanges: list[CapturedExchange] = []
    run_id = f"bench-{seed}-{width}"
    # Both phases see the same allowlisted + hidden paths so only hidden_endpoint
    # contributes to the risk score (stable across repetitions).
    for phase in ("baseline", "mutated"):
        for path in allowed:
            exchanges.append(
                CapturedExchange(
                    run_id=run_id,
                    phase=phase,
                    method="GET",
                    path=path,
                    status_code=200,
                    response_body={"id": path},
                    extracted_fields=["id"],
                )
            )
        exchanges.append(
            CapturedExchange(
                run_id=run_id,
                phase=phase,
                method="GET",
                path=hidden,
                status_code=200,
                response_body={"id": "hidden"},
                extracted_fields=["id"],
            )
        )
    return target, exchanges


def _percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("empty values")
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile / 100.0 * len(ordered)) - 1)
    return ordered[rank]


def _mad(values: list[float]) -> float:
    if not values:
        return 0.0
    med = statistics.median(values)
    return float(statistics.median([abs(v - med) for v in values]))


def _host_metadata() -> dict:
    affinity_set = False
    try:
        if hasattr(os, "sched_getaffinity"):
            affinity = os.sched_getaffinity(0)
            # Affinity is "set" if restricted relative to apparent CPU count
            cpu_count = os.cpu_count() or 0
            affinity_set = bool(cpu_count and len(affinity) < cpu_count)
    except (AttributeError, OSError):
        affinity_set = False
    return {
        "cpu": platform.processor() or platform.machine(),
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "cpu_affinity_set": affinity_set,
    }


def run_benchmark(config: BenchmarkConfig) -> list[BenchmarkSummary]:
    summaries: list[BenchmarkSummary] = []
    for width in config.widths:
        target, exchanges = build_synthetic_case(width, config.seed)
        # Warmups excluded from statistics
        for _ in range(config.warmups):
            analyze_run(f"warmup-{width}", target, exchanges)
        durations_ms: list[float] = []
        risk_scores: list[float] = []
        for rep in range(config.repetitions):
            start = time.perf_counter_ns()
            report = analyze_run(f"bench-{width}-{rep}", target, exchanges)
            end = time.perf_counter_ns()
            durations_ms.append((end - start) / 1_000_000.0)
            risk_scores.append(float(report.risk_score))
        summaries.append(
            BenchmarkSummary(
                width=width,
                repetitions=config.repetitions,
                median_ms=float(statistics.median(durations_ms)),
                p95_ms=_percentile_nearest_rank(durations_ms, 95),
                mad_ms=_mad(durations_ms),
                min_ms=min(durations_ms),
                max_ms=max(durations_ms),
                risk_scores=risk_scores,
            )
        )
    return summaries


def run_benchmark_pipeline(
    config: BenchmarkConfig,
    output_root: Path,
    command: list[str],
) -> list[BenchmarkSummary]:
    host = _host_metadata()
    raw_widths: list[dict] = []
    summaries: list[BenchmarkSummary] = []

    for width in config.widths:
        target, exchanges = build_synthetic_case(width, config.seed)
        for _ in range(config.warmups):
            analyze_run(f"warmup-{width}", target, exchanges)
        durations_ms: list[float] = []
        risk_scores: list[float] = []
        for rep in range(config.repetitions):
            start = time.perf_counter_ns()
            report = analyze_run(f"bench-{width}-{rep}", target, exchanges)
            end = time.perf_counter_ns()
            durations_ms.append((end - start) / 1_000_000.0)
            risk_scores.append(float(report.risk_score))
        summary = BenchmarkSummary(
            width=width,
            repetitions=config.repetitions,
            median_ms=float(statistics.median(durations_ms)),
            p95_ms=_percentile_nearest_rank(durations_ms, 95),
            mad_ms=_mad(durations_ms),
            min_ms=min(durations_ms),
            max_ms=max(durations_ms),
            risk_scores=risk_scores,
        )
        summaries.append(summary)
        raw_widths.append(
            {
                "width": width,
                "durations_ms": durations_ms,
                "risk_scores": risk_scores,
            }
        )

    raw = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=config.seed),
        experiment="benchmark_analysis",
        configuration=config.model_dump(mode="json"),
        payload={"host": host, "widths": raw_widths},
    )
    write_artifact(output_root / "raw" / "benchmark" / "benchmark_raw.json", raw)

    derived = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=config.seed),
        experiment="benchmark_summary",
        configuration=config.model_dump(mode="json"),
        payload={
            "host": host,
            "summaries": [s.model_dump(mode="json") for s in summaries],
        },
    )
    write_artifact(output_root / "derived" / "benchmark_summary.json", derived)
    return summaries


def _parse_widths(value: str) -> list[int]:
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise typer.BadParameter("widths must be a non-empty comma-separated list")
    return [int(p) for p in parts]


@app.command()
def main(
    widths: str = typer.Option(
        "10,50,100,500,1000",
        "--widths",
        help="Comma-separated endpoint widths",
    ),
    warmups: int = typer.Option(10, "--warmups"),
    repetitions: int = typer.Option(100, "--repetitions"),
    seed: int = typer.Option(SEED_DEFAULT, "--seed"),
    output_root: Path = typer.Option(Path("results"), "--output-root"),
) -> None:
    command = ["python", "-m", "ait.experiments.benchmark_analysis", *sys.argv[1:]]
    config = BenchmarkConfig(
        widths=_parse_widths(widths),
        warmups=warmups,
        repetitions=repetitions,
        seed=seed,
    )
    summaries = run_benchmark_pipeline(config, output_root, command)
    typer.echo(f"Benchmark widths: {len(summaries)}")


if __name__ == "__main__":
    app()
