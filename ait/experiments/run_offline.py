from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any

import typer

from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.experiments.benchmark_analysis import BenchmarkConfig, run_benchmark_pipeline
from ait.experiments.metrics import evaluate_categories, micro_average
from ait.experiments.mock_executor import execute_scenario
from ait.experiments.replay_incidents import run_replay_pipeline
from ait.experiments.risk_sensitivity import run_sensitivity_pipeline
from ait.experiments.run_scenarios import _outcome_payload, _print_outcome
from ait.experiments.scenario_loader import load_scenarios
from ait.experiments.schema import ScenarioOutcome

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SEED = 20260727


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_artifact_paths(output_root: Path) -> list[Path]:
    root = Path(output_root)
    paths = sorted(p for p in root.rglob("*.json") if p.is_file())
    # Exclude the manifest itself if regenerating
    return [p for p in paths if p.name != "offline_manifest.json"]


async def _run_scenarios(
    scenario_root: Path,
    output_root: Path,
    command: list[str],
) -> tuple[int, list[ScenarioOutcome]]:
    scenarios = load_scenarios(scenario_root, suite="all")
    outcomes: list[ScenarioOutcome] = []
    failures = 0
    raw_dir = output_root / "raw" / "scenarios"
    for scenario in scenarios:
        outcome = await execute_scenario(scenario)
        outcomes.append(outcome)
        _print_outcome(outcome)
        if outcome.expected_categories != outcome.observed_categories:
            failures += 1
        envelope = ArtifactEnvelope(
            provenance=collect_provenance(command, seed=SEED),
            experiment="scenarios",
            configuration={
                "suite": "all",
                "scenario_id": scenario.id,
                "scenario_suite": scenario.suite,
                "platform_style": scenario.platform_style,
            },
            payload=_outcome_payload(outcome),
        )
        write_artifact(raw_dir / f"{scenario.id}.json", envelope)

    category_metrics = evaluate_categories(outcomes)
    micro = micro_average(category_metrics)
    derived = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=SEED),
        experiment="scenario_metrics",
        configuration={"suite": "all", "scenario_count": len(outcomes)},
        payload={
            "categories": [m.model_dump(mode="json") for m in category_metrics],
            "micro": micro.model_dump(mode="json"),
            "scenario_results": [
                {
                    "scenario_id": o.scenario_id,
                    "passed": o.expected_categories == o.observed_categories,
                    "expected_categories": sorted(c.value for c in o.expected_categories),
                    "observed_categories": sorted(c.value for c in o.observed_categories),
                }
                for o in outcomes
            ],
        },
    )
    write_artifact(output_root / "derived" / "scenario_metrics.json", derived)
    typer.echo(
        f"Scenarios: {len(outcomes)} PASS={len(outcomes) - failures} FAIL={failures}"
    )
    return failures, outcomes

def run_offline(
    output_root: Path,
    scenario_root: Path,
    incident_root: Path,
    command: list[str],
    *,
    benchmark_widths: list[int] | None = None,
    benchmark_warmups: int = 10,
    benchmark_repetitions: int = 100,
) -> int:
    output_root = Path(output_root)
    typer.echo("=== 1/4 scenarios ===")
    failures, outcomes = asyncio.run(_run_scenarios(scenario_root, output_root, command))
    if failures:
        typer.echo("Stopping: scenario suite failed.", err=True)
        return 1

    typer.echo("=== 2/4 risk sensitivity ===")
    rows = run_sensitivity_pipeline(outcomes, output_root, command)
    typer.echo(f"Sensitivity rows: {len(rows)}")

    typer.echo("=== 3/4 incident replay ===")
    replay_outcomes = run_replay_pipeline(incident_root, output_root, command)
    replay_failures = sum(1 for o in replay_outcomes if not o.exact_match)
    if replay_failures:
        typer.echo("Stopping: incident replay failed.", err=True)
        return 1

    typer.echo("=== 4/4 benchmark ===")
    widths = benchmark_widths if benchmark_widths is not None else [10, 50, 100, 500, 1000]
    config = BenchmarkConfig(
        widths=widths,
        warmups=benchmark_warmups,
        repetitions=benchmark_repetitions,
        seed=SEED,
    )
    summaries = run_benchmark_pipeline(config, output_root, command)
    typer.echo(f"Benchmark widths: {len(summaries)}")

    artifacts = _collect_artifact_paths(output_root)
    entries: list[dict[str, Any]] = []
    for path in artifacts:
        entries.append(
            {
                "path": str(path.relative_to(output_root)),
                "sha256": _sha256_file(path),
            }
        )
    manifest = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=SEED),
        experiment="offline_manifest",
        configuration={
            "scenario_root": str(scenario_root),
            "incident_root": str(incident_root),
            "benchmark": config.model_dump(mode="json"),
        },
        payload={"artifacts": entries, "artifact_count": len(entries)},
    )
    write_artifact(output_root / "derived" / "offline_manifest.json", manifest)
    typer.echo(f"Offline manifest: {len(entries)} artifacts")
    return 0


@app.command()
def main(
    output_root: Path = typer.Option(Path("results"), "--output-root"),
    scenario_root: Path = typer.Option(Path("configs/scenarios"), "--scenario-root"),
    incident_root: Path = typer.Option(Path("configs/incidents"), "--incident-root"),
    widths: str = typer.Option(
        "10,50,100,500,1000",
        "--widths",
        help="Benchmark widths (comma-separated)",
    ),
    warmups: int = typer.Option(10, "--warmups"),
    repetitions: int = typer.Option(100, "--repetitions"),
) -> None:
    command = ["python", "-m", "ait.experiments.run_offline", *sys.argv[1:]]
    width_list = [int(p.strip()) for p in widths.split(",") if p.strip()]
    code = run_offline(
        output_root=output_root,
        scenario_root=scenario_root,
        incident_root=incident_root,
        command=command,
        benchmark_widths=width_list,
        benchmark_warmups=warmups,
        benchmark_repetitions=repetitions,
    )
    raise typer.Exit(code)


if __name__ == "__main__":
    app()
