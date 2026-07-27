from __future__ import annotations

import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import typer
from pydantic import BaseModel, Field, field_validator

from ait.analysis import analyze_run
from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.models import CapturedExchange, TargetConfig

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SEED_DEFAULT = 20260727


class BenchmarkConfig(BaseModel):
    widths: list[int] = Field(default_factory=lambda: [10, 50, 100, 500, 1000], min_length=1)
    warmups: int = Field(default=10, ge=0)
    repetitions: int = Field(default=100, ge=1)
    seed: int = SEED_DEFAULT

    @field_validator("widths")
    @classmethod
    def widths_must_be_positive(cls, values: list[int]) -> list[int]:
        if any(width < 1 for width in values):
            raise ValueError("each width must be >= 1")
        return values


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


def _read_processor_model() -> str:
    candidates = [
        Path("/proc/cpuinfo"),
        Path("/sys/devices/virtual/dmi/id/product_name"),
    ]
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.name == "cpuinfo":
            for line in text.splitlines():
                if line.lower().startswith("model name"):
                    _, _, value = line.partition(":")
                    model = value.strip()
                    if model:
                        return model
        else:
            model = text.strip()
            if model and model.lower() not in {"none", "default string"}:
                return model
    cpu = platform.processor() or platform.machine()
    return cpu if cpu else "unknown"


def _cpu_affinity_metadata() -> tuple[list[int] | str, bool]:
    try:
        if hasattr(os, "sched_getaffinity"):
            affinity = sorted(os.sched_getaffinity(0))
            cpu_count = os.cpu_count() or 0
            affinity_set = bool(cpu_count and len(affinity) < cpu_count)
            return affinity, affinity_set
    except (AttributeError, OSError):
        pass
    return "unknown", False


def _host_metadata() -> dict:
    affinity, affinity_set = _cpu_affinity_metadata()
    return {
        "cpu": platform.processor() or platform.machine() or "unknown",
        "processor_model": _read_processor_model(),
        "logical_cpu_count": os.cpu_count(),
        "cpu_affinity": affinity,
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "cpu_affinity_set": affinity_set,
    }


def _assert_identical_risk_scores(risk_scores: list[float], *, width: int) -> None:
    if not risk_scores:
        raise ValueError(f"no risk scores recorded for width={width}")
    unique = set(risk_scores)
    if len(unique) != 1:
        raise ValueError(
            f"risk scores diverged across repetitions for width={width}: {sorted(unique)}"
        )


def _measure_width(config: BenchmarkConfig, width: int) -> tuple[BenchmarkSummary, list[float]]:
    target, exchanges = build_synthetic_case(width, config.seed)
    for warmup_id in range(config.warmups):
        analyze_run(f"warmup-{width}-{warmup_id}", target, exchanges)

    # Precompute repetition IDs outside the timed region.
    rep_ids = [f"bench-{width}-{rep}" for rep in range(config.repetitions)]
    durations_ms: list[float] = []
    risk_scores: list[float] = []
    for run_id in rep_ids:
        start = time.perf_counter_ns()
        report = analyze_run(run_id, target, exchanges)
        end = time.perf_counter_ns()
        durations_ms.append((end - start) / 1_000_000.0)
        risk_scores.append(float(report.risk_score))
    _assert_identical_risk_scores(risk_scores, width=width)
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
    return summary, durations_ms


def run_benchmark(config: BenchmarkConfig) -> list[BenchmarkSummary]:
    if not config.widths:
        raise ValueError("benchmark widths must be non-empty")
    return [_measure_width(config, width)[0] for width in config.widths]


def run_benchmark_pipeline(
    config: BenchmarkConfig,
    output_root: Path,
    command: list[str],
    *,
    produced: list[Path] | None = None,
) -> list[BenchmarkSummary]:
    if not config.widths:
        raise ValueError("benchmark widths must be non-empty")
    host = _host_metadata()
    raw_widths: list[dict] = []
    summaries: list[BenchmarkSummary] = []

    for width in config.widths:
        summary, durations_ms = _measure_width(config, width)
        summaries.append(summary)
        raw_widths.append(
            {
                "width": width,
                "durations_ms": durations_ms,
                "risk_scores": summary.risk_scores,
            }
        )

    raw = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=config.seed),
        experiment="benchmark_analysis",
        configuration=config.model_dump(mode="json"),
        payload={"host": host, "widths": raw_widths},
    )
    written = write_artifact(output_root / "raw" / "benchmark" / "benchmark_raw.json", raw)
    if produced is not None:
        produced.append(written)

    derived = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=config.seed),
        experiment="benchmark_summary",
        configuration=config.model_dump(mode="json"),
        payload={
            "host": host,
            "summaries": [s.model_dump(mode="json") for s in summaries],
        },
    )
    written = write_artifact(output_root / "derived" / "benchmark_summary.json", derived)
    if produced is not None:
        produced.append(written)
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
    from pydantic import ValidationError

    command = ["python", "-m", "ait.experiments.benchmark_analysis", *sys.argv[1:]]
    try:
        config = BenchmarkConfig(
            widths=_parse_widths(widths),
            warmups=warmups,
            repetitions=repetitions,
            seed=seed,
        )
        summaries = run_benchmark_pipeline(config, output_root, command)
    except (ValueError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Benchmark widths: {len(summaries)}")


if __name__ == "__main__":
    app()
