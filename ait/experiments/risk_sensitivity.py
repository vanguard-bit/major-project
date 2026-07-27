from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import typer
from pydantic import BaseModel

from ait.analysis import DEFAULT_RISK_WEIGHTS, RiskWeights, calculate_risk_score
from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.experiments.mock_executor import execute_scenario
from ait.experiments.scenario_loader import load_scenarios
from ait.experiments.schema import ScenarioOutcome

WeightName = Literal["hidden_endpoint", "sensitive_field", "divergence"]
RiskBand = Literal["low", "medium", "high", "critical"]

DEFAULT_MULTIPLIERS: tuple[float, ...] = (0.7, 1.0, 1.3)
WEIGHT_NAMES: tuple[WeightName, ...] = (
    "hidden_endpoint",
    "sensitive_field",
    "divergence",
)

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


class SensitivityRow(BaseModel):
    scenario_id: str
    varied_weight: WeightName
    multiplier: float
    score: float
    band: RiskBand


def classify_risk(score: float) -> RiskBand:
    """Classify score into documented bands.

    Low: 0–25
    Medium: >25–50
    High: >50–75
    Critical: >75–100
    """
    if score < 0:
        raise ValueError(f"score must be non-negative, got {score}")
    if score <= 25:
        return "low"
    if score <= 50:
        return "medium"
    if score <= 75:
        return "high"
    return "critical"


def _perturbed_weights(varied: WeightName, multiplier: float) -> RiskWeights:
    base = DEFAULT_RISK_WEIGHTS
    values = {
        "hidden_endpoint": base.hidden_endpoint,
        "sensitive_field": base.sensitive_field,
        "divergence": base.divergence,
        "cap": base.cap,
    }
    values[varied] = values[varied] * multiplier
    return RiskWeights(**values)


def run_sensitivity(
    outcomes: Sequence[ScenarioOutcome],
    multipliers: Sequence[float] = DEFAULT_MULTIPLIERS,
) -> list[SensitivityRow]:
    rows: list[SensitivityRow] = []
    for outcome in outcomes:
        report = outcome.report
        hidden = len(report.hidden_endpoints)
        sensitive = len(report.sensitive_fields_accessed)
        divergence = len(report.divergence_summary)
        for varied in WEIGHT_NAMES:
            for multiplier in multipliers:
                weights = _perturbed_weights(varied, multiplier)
                score = round(
                    calculate_risk_score(hidden, sensitive, divergence, weights=weights),
                    2,
                )
                rows.append(
                    SensitivityRow(
                        scenario_id=outcome.scenario_id,
                        varied_weight=varied,
                        multiplier=multiplier,
                        score=score,
                        band=classify_risk(score),
                    )
                )
    return rows


def derive_sensitivity_summary(rows: Sequence[SensitivityRow]) -> dict[str, Any]:
    by_scenario: dict[str, list[SensitivityRow]] = {}
    for row in rows:
        by_scenario.setdefault(row.scenario_id, []).append(row)

    scenarios: list[dict[str, Any]] = []
    for scenario_id, scenario_rows in by_scenario.items():
        scores = [r.score for r in scenario_rows]
        bands = {r.band for r in scenario_rows}
        at_one = {r.band for r in scenario_rows if r.multiplier == 1.0}
        other = {r.band for r in scenario_rows if r.multiplier != 1.0}
        band_transitions = sorted((other - at_one) | (at_one - other))
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "min_score": min(scores),
                "max_score": max(scores),
                "bands_observed": sorted(bands),
                "band_transitions": band_transitions,
            }
        )
    return {"scenarios": scenarios, "row_count": len(rows)}


def run_sensitivity_pipeline(
    outcomes: list[ScenarioOutcome],
    output_root: Path,
    command: list[str],
    multipliers: list[float] | None = None,
) -> list[SensitivityRow]:
    mults = list(multipliers) if multipliers is not None else list(DEFAULT_MULTIPLIERS)
    rows = run_sensitivity(outcomes, multipliers=mults)
    raw_dir = output_root / "raw" / "sensitivity"
    envelope = ArtifactEnvelope(
        provenance=collect_provenance(command),
        experiment="risk_sensitivity",
        configuration={
            "multipliers": mults,
            "scenario_count": len(outcomes),
            "scenario_ids": [o.scenario_id for o in outcomes],
        },
        payload={"rows": [r.model_dump(mode="json") for r in rows]},
    )
    write_artifact(raw_dir / "sensitivity_rows.json", envelope)

    summary = derive_sensitivity_summary(rows)
    derived = ArtifactEnvelope(
        provenance=collect_provenance(command),
        experiment="risk_sensitivity_summary",
        configuration={"multipliers": mults, "scenario_count": len(outcomes)},
        payload=summary,
    )
    write_artifact(output_root / "derived" / "sensitivity_summary.json", derived)
    return rows


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
    command = ["python", "-m", "ait.experiments.risk_sensitivity", *sys.argv[1:]]

    async def _run() -> list[ScenarioOutcome]:
        scenarios = load_scenarios(scenario_root, suite=suite)
        return [await execute_scenario(scenario) for scenario in scenarios]

    outcomes = asyncio.run(_run())
    rows = run_sensitivity_pipeline(outcomes, output_root, command)
    typer.echo(f"Sensitivity rows: {len(rows)}")


if __name__ == "__main__":
    app()
