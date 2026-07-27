from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import typer

from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.experiments.metrics import evaluate_categories, micro_average
from ait.experiments.mock_executor import execute_scenario
from ait.experiments.scenario_loader import load_scenarios
from ait.experiments.schema import ScenarioOutcome

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


def _outcome_payload(outcome: ScenarioOutcome) -> dict[str, Any]:
    return {
        "scenario_id": outcome.scenario_id,
        "target": (
            outcome.target.model_dump(mode="json") if outcome.target is not None else None
        ),
        "expected_labels": [label.model_dump(mode="json") for label in outcome.expected_labels],
        "exchanges": [exchange.model_dump(mode="json") for exchange in outcome.exchanges],
        "expected_categories": sorted(c.value for c in outcome.expected_categories),
        "observed_categories": sorted(c.value for c in outcome.observed_categories),
        "passed": outcome.expected_categories == outcome.observed_categories,
        "report": outcome.report.model_dump(mode="json"),
    }


def _print_outcome(outcome: ScenarioOutcome) -> None:
    expected = sorted(c.value for c in outcome.expected_categories)
    observed = sorted(c.value for c in outcome.observed_categories)
    status = "PASS" if outcome.expected_categories == outcome.observed_categories else "FAIL"
    typer.echo(
        f"{status} {outcome.scenario_id} expected={expected} observed={observed}"
    )


async def _run(
    suite: str,
    scenario_root: Path,
    output_root: Path,
    command: list[str],
) -> int:
    scenarios = load_scenarios(scenario_root, suite=suite)
    if not scenarios:
        typer.echo("No scenarios discovered; refusing empty corpus.", err=True)
        return 1

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
            provenance=collect_provenance(command),
            experiment="scenarios",
            configuration={
                "suite": suite,
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
        provenance=collect_provenance(command),
        experiment="scenario_metrics",
        configuration={"suite": suite, "scenario_count": len(outcomes)},
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
    return 1 if failures else 0


@app.command()
def main(
    suite: str = typer.Option("all", help="Scenario suite: all, crm, or platform"),
    scenario_root: Path = typer.Option(
        Path("configs/scenarios"),
        "--scenario-root",
        help="Root directory containing scenario YAML files",
    ),
    output_root: Path = typer.Option(
        Path("results"),
        "--output-root",
        help="Root directory for raw and derived artifacts",
    ),
) -> None:
    command = ["python", "-m", "ait.experiments.run_scenarios", *sys.argv[1:]]
    code = asyncio.run(_run(suite, scenario_root, output_root, command))
    raise typer.Exit(code)


if __name__ == "__main__":
    app()
