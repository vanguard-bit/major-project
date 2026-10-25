"""AIT vs. two-part baseline on identical traces (EXPERIMENT_PROTOCOL.md §5–§8)."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any

import typer

from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.baseline import MIN_CANARY_LENGTH, run_baseline
from ait.experiments.metrics import _precision_recall_f1
from ait.experiments.mock_executor import execute_scenario
from ait.experiments.scenario_loader import SCHEMA_EXAMPLE_NAME, load_scenario
from ait.experiments.schema import ScenarioDefinition
from ait.experiments.statistics import wilson_interval

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SEED = 20260727
CATEGORIES = ("hidden_endpoint", "sensitive_field_access", "behavioral_divergence")
BASELINE_CATEGORIES = ("hidden_endpoint", "sensitive_field_access")
SCORED_OUTCOMES = ("confirmed_policy_violation", "permitted_behavior")


def discover(root: Path) -> list[Path]:
    return sorted(
        path
        for path in Path(root).rglob("*.yaml")
        if path.name != SCHEMA_EXAMPLE_NAME and "invalid" not in path.parts
    )


def derived_canaries(scenario: ScenarioDefinition) -> list[str]:
    """Protocol §6 development-corpus rule: seeded values in marker-named response fields."""
    markers = set(scenario.target.sensitive_markers)
    values: set[str] = set()

    def walk(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if (
                    isinstance(item, str)
                    and len(item) >= MIN_CANARY_LENGTH
                    and (path in markers or path.rsplit(".", 1)[-1] in markers)
                ):
                    values.add(item)
                walk(item, path)
        elif isinstance(value, list):
            for item in value:
                walk(item, prefix)

    for exchange in scenario.exchanges:
        walk(exchange.response_body)
    return sorted(values)


def outcome_of(scenario: ScenarioDefinition) -> str:
    if scenario.ground_truth_outcome:
        return scenario.ground_truth_outcome
    return "confirmed_policy_violation" if scenario.expected_labels else "permitted_behavior"


async def predict(scenario: ScenarioDefinition) -> dict[str, Any]:
    outcome = await execute_scenario(scenario)
    canaries = list(scenario.canaries) or derived_canaries(scenario)
    baseline = run_baseline(scenario.target.expected_endpoints, canaries, outcome.exchanges)
    return {
        "scenario_id": scenario.id,
        "suite": scenario.suite,
        "outcome": outcome_of(scenario),
        "observable_by_model": scenario.observable_by_model,
        "canary_source": "declared" if scenario.canaries else "derived",
        "canary_count": len(canaries),
        "expected": sorted({label.category.value for label in scenario.expected_labels}),
        "ait": sorted(
            {f.category.value for f in outcome.report.findings} & set(CATEGORIES)
        ),
        "ait_hidden_endpoints": outcome.report.hidden_endpoints,
        "baseline": sorted(baseline.categories),
        "baseline_detail": baseline.model_dump(mode="json"),
    }


def _counts(rows: list[dict[str, Any]], method: str, category: str) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    for row in rows:
        expected = category in row["expected"]
        observed = category in row[method]
        tp += expected and observed
        fp += (not expected) and observed
        fn += expected and not observed
        tn += (not expected) and not observed
    return _metric_block(tp, fp, fn, tn)


def _metric_block(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "precision_interval": wilson_interval(tp, tp + fp).model_dump(),
        "recall_interval": wilson_interval(tp, tp + fn).model_dump(),
    }


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["outcome"] in SCORED_OUTCOMES]
    per_method: dict[str, Any] = {}
    for method, categories in (("ait", CATEGORIES), ("baseline", BASELINE_CATEGORIES)):
        blocks = {category: _counts(scored, method, category) for category in categories}
        micro = [sum(blocks[c][k] for c in categories) for k in ("tp", "fp", "fn", "tn")]
        tp = fp = fn = tn = 0
        for row in scored:
            positive = row["outcome"] == "confirmed_policy_violation"
            flagged = bool(row[method])
            tp += positive and flagged
            fp += (not positive) and flagged
            fn += positive and not flagged
            tn += (not positive) and not flagged
        per_method[method] = {
            "categories": blocks,
            "micro": _metric_block(*micro),
            "scenario_level": _metric_block(tp, fp, fn, tn),
        }
    per_method["baseline"]["categories"]["behavioral_divergence"] = "n/a"
    disagreements = [
        {"scenario_id": r["scenario_id"], "expected": r["expected"], "ait": r["ait"],
         "baseline": r["baseline"]}
        for r in rows
        if set(r["ait"]) & set(BASELINE_CATEGORIES) != set(r["baseline"])
    ]
    return {
        "unit": "scenario x category (category presence); scenario-level: any flag",
        "scenario_count": len(rows),
        "scored_count": len(scored),
        "unscored": [
            {"scenario_id": r["scenario_id"], "outcome": r["outcome"], "ait": r["ait"],
             "baseline": r["baseline"]}
            for r in rows
            if r["outcome"] not in SCORED_OUTCOMES
        ],
        "methods": per_method,
        "disagreements_on_shared_categories": disagreements,
        "baseline_ambiguous_cases": [
            r["scenario_id"] for r in rows if r["baseline_detail"]["ambiguous_endpoints"]
        ],
    }


def run_comparison(
    scenario_root: Path, output_root: Path, corpus: str, command: list[str]
) -> tuple[Path, Path, dict[str, Any]]:
    paths = discover(scenario_root)
    if not paths:
        raise ValueError(f"no scenarios under {scenario_root}")

    async def _all() -> list[dict[str, Any]]:
        return [await predict(load_scenario(path)) for path in paths]

    rows = asyncio.run(_all())
    configuration = {
        "corpus": corpus,
        "scenario_root": Path(scenario_root).as_posix(),
        "input_sha256": {p.as_posix(): _sha256(p) for p in paths},
        "protocol": "docs/research-sprint/EXPERIMENT_PROTOCOL.md",
    }
    raw = write_artifact(
        Path(output_root) / "raw" / "baseline-comparison" / corpus / "predictions.json",
        ArtifactEnvelope(
            provenance=collect_provenance(command, seed=SEED),
            experiment="baseline_comparison_predictions",
            configuration=configuration,
            payload={"rows": rows},
        ),
    )
    metrics = compute_metrics(rows)
    derived = write_artifact(
        Path(output_root) / "derived" / f"baseline_comparison_{corpus}.json",
        ArtifactEnvelope(
            provenance=collect_provenance(command, seed=SEED),
            experiment="baseline_comparison",
            configuration=configuration,
            payload=metrics,
        ),
    )
    return raw, derived, metrics


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@app.command("run")
def run_cmd(
    scenario_root: Path = typer.Option(Path("configs/scenarios"), "--scenario-root"),
    corpus: str = typer.Option("dev", "--corpus"),
    output_root: Path = typer.Option(Path("results"), "--output-root"),
) -> None:
    command = ["python", "-m", "ait.experiments.compare_baseline", *sys.argv[1:]]
    raw, derived, metrics = run_comparison(scenario_root, output_root, corpus, command)
    for method, block in metrics["methods"].items():
        s = block["scenario_level"]
        typer.echo(f"{method}: scenario TP={s['tp']} FP={s['fp']} FN={s['fn']} TN={s['tn']}")
    typer.echo(f"WROTE {raw}\nWROTE {derived}")


@app.command("hash")
def hash_cmd(root: Path) -> None:
    """Print sha256sum-style lines for a frozen scenario directory."""
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        typer.echo(f"{_sha256(path)}  {path.relative_to(root).as_posix()}")


if __name__ == "__main__":
    app()
