from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import typer

from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.experiments.mock_executor import execute_scenario
from ait.experiments.robustness import load_evaluation_protocol, protocol_sha256
from ait.experiments.scenario_loader import load_scenarios
from ait.models import FindingCategory

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SEED = 20260727
DEFAULT_PROTOCOL = Path("configs/evaluation_protocol.yaml")
DEFAULT_SCENARIO_ROOT = Path("configs/scenarios")


def _normalized_snapshot(outcome: Any) -> dict[str, Any]:
    """Comparable payload: categories + risk score (no timestamps)."""
    categories = sorted(
        finding.category.value
        if isinstance(finding.category, FindingCategory)
        else str(finding.category)
        for finding in outcome.report.findings
    )
    category_set = sorted(set(categories))
    return {
        "scenario_id": outcome.scenario_id,
        "finding_categories": category_set,
        "risk_score": outcome.report.risk_score,
    }


async def run_reproducibility(
    scenario_root: Path,
    protocol_path: Path,
    output_root: Path,
    repetitions: int,
    command: list[str],
) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    protocol = load_evaluation_protocol(protocol_path)
    digest = protocol_sha256(protocol_path)
    seed = int(protocol.get("seed", SEED))
    scenarios = load_scenarios(scenario_root, suite="all")
    if not scenarios:
        raise ValueError(f"no primary scenarios under {scenario_root}")

    run_snapshots: list[list[dict[str, Any]]] = []
    crashes = 0
    for _ in range(repetitions):
        snapshots: list[dict[str, Any]] = []
        for scenario in scenarios:
            try:
                outcome = await execute_scenario(scenario)
                snapshots.append(_normalized_snapshot(outcome))
            except Exception as exc:  # noqa: BLE001 — count detector crashes
                crashes += 1
                snapshots.append(
                    {
                        "scenario_id": scenario.id,
                        "finding_categories": [],
                        "risk_score": None,
                        "crash": str(exc),
                    }
                )
        run_snapshots.append(snapshots)

    reference = run_snapshots[0]
    identical_categories = 0
    identical_scores = 0
    mismatches: list[dict[str, Any]] = []

    for run_index, snapshots in enumerate(run_snapshots):
        cat_ok = True
        score_ok = True
        for ref, current in zip(reference, snapshots, strict=True):
            if ref.get("finding_categories") != current.get("finding_categories"):
                cat_ok = False
                mismatches.append(
                    {
                        "run": run_index,
                        "scenario_id": current["scenario_id"],
                        "field": "finding_categories",
                        "expected": ref.get("finding_categories"),
                        "observed": current.get("finding_categories"),
                    }
                )
            if ref.get("risk_score") != current.get("risk_score"):
                score_ok = False
                mismatches.append(
                    {
                        "run": run_index,
                        "scenario_id": current["scenario_id"],
                        "field": "risk_score",
                        "expected": ref.get("risk_score"),
                        "observed": current.get("risk_score"),
                    }
                )
        if cat_ok:
            identical_categories += 1
        if score_ok:
            identical_scores += 1

    accepted = (
        identical_categories == repetitions
        and identical_scores == repetitions
        and crashes == 0
    )
    summary: dict[str, Any] = {
        "protocol_sha256": digest,
        "seed": seed,
        "repetitions": repetitions,
        "scenario_count": len(scenarios),
        "identical_finding_category_sets": identical_categories,
        "identical_risk_scores": identical_scores,
        "detector_crashes": crashes,
        "mismatches": mismatches,
        "accepted": accepted,
        "runs": run_snapshots,
    }
    envelope = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=seed),
        experiment="reproducibility",
        configuration={
            "protocol_sha256": digest,
            "protocol_path": str(protocol_path),
            "scenario_root": str(scenario_root),
            "repetitions": repetitions,
        },
        payload=summary,
    )
    write_artifact(Path(output_root) / "derived" / "reproducibility.json", envelope)
    return summary


@app.command()
def main(
    scenario_root: Path = typer.Option(DEFAULT_SCENARIO_ROOT, "--scenario-root"),
    protocol_path: Path = typer.Option(DEFAULT_PROTOCOL, "--protocol"),
    output_root: Path = typer.Option(Path("results"), "--output-root"),
    repetitions: int = typer.Option(5, "--repetitions"),
) -> None:
    command = ["python", "-m", "ait.experiments.reproducibility", *sys.argv[1:]]
    summary = asyncio.run(
        run_reproducibility(
            scenario_root=scenario_root,
            protocol_path=protocol_path,
            output_root=output_root,
            repetitions=repetitions,
            command=command,
        )
    )
    status = "PASS" if summary["accepted"] else "FAIL"
    typer.echo(
        f"{status} reproducibility repetitions={summary['repetitions']} "
        f"identical_categories={summary['identical_finding_category_sets']} "
        f"identical_scores={summary['identical_risk_scores']} "
        f"crashes={summary['detector_crashes']}"
    )
    raise typer.Exit(0 if summary["accepted"] else 1)


if __name__ == "__main__":
    app()
