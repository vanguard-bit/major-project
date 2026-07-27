from __future__ import annotations

import asyncio
import hashlib
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import typer
import yaml

from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.experiments.metrics import evaluate_categories, micro_average
from ait.experiments.mock_executor import execute_scenario
from ait.experiments.run_scenarios import _outcome_passed, _outcome_payload, _print_outcome
from ait.experiments.scenario_loader import load_scenarios, normalize_path
from ait.experiments.schema import (
    ExchangeSpec,
    ExpectedLabel,
    ScenarioDefinition,
    ScenarioOutcome,
)
from ait.experiments.statistics import wilson_interval
from ait.models import FindingCategory

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SEED = 20260727
DEFAULT_PROTOCOL = Path("configs/evaluation_protocol.yaml")
DEFAULT_SCENARIO_ROOT = Path("configs/scenarios")
HEALTH_COUNTS = (0, 8, 32, 128)


def protocol_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_evaluation_protocol(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"evaluation protocol must be a mapping: {path}")
    required = {
        "schema_version",
        "seed",
        "hypotheses",
        "uncertainty",
        "repetitions",
        "scenario_globs",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError(f"evaluation protocol missing keys: {sorted(missing)}")
    return raw


def _clone(scenario: ScenarioDefinition, **overrides: Any) -> ScenarioDefinition:
    data = scenario.model_dump(mode="python")
    data.update(overrides)
    return ScenarioDefinition.model_validate(data)


def _with_meta(
    scenario: ScenarioDefinition,
    *,
    new_id: str,
    description: str,
    parent_scenario_id: str | None = None,
    labels_invariant: bool = True,
    observable_by_model: bool = True,
    suite: str = "robustness",
) -> ScenarioDefinition:
    return _clone(
        scenario,
        id=new_id,
        suite=suite,
        description=description,
        parent_scenario_id=parent_scenario_id or scenario.id,
        labels_invariant=labels_invariant,
        observable_by_model=observable_by_model,
    )


def inject_health_polls(parent: ScenarioDefinition, count: int) -> ScenarioDefinition:
    if count < 0:
        raise ValueError("health poll count must be non-negative")
    target = parent.target.model_dump(mode="python")
    endpoints = list(target.get("expected_endpoints", []))
    if count > 0 and "/health" not in endpoints:
        endpoints.append("/health")
    target["expected_endpoints"] = endpoints
    target["name"] = f"{parent.id}-health-{count}"

    exchanges = list(parent.exchanges)
    for phase in ("baseline", "mutated"):
        for index in range(count):
            exchanges.append(
                ExchangeSpec(
                    phase=phase,  # type: ignore[arg-type]
                    method="GET",
                    path="/health",
                    sequence=index,
                    response_body={"status": "ok"},
                )
            )
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-health-{count}",
        description=f"Inject {count} benign /health polls into each phase.",
        parent_scenario_id=parent.id,
        labels_invariant=True,
    )


def permute_query_order(parent: ScenarioDefinition) -> ScenarioDefinition:
    exchanges: list[ExchangeSpec] = []
    for exchange in parent.exchanges:
        data = exchange.model_dump(mode="python")
        path = data["path"]
        if "?" in path:
            base, _, query = path.partition("?")
            pairs = query.split("&")
            data["path"] = f"{base}?{'&'.join(reversed(pairs))}"
        exchanges.append(ExchangeSpec.model_validate(data))
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-query-order"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-query-order",
        description="Query parameter order permutation; labels remain invariant.",
        parent_scenario_id=parent.id,
    )


def inject_duplicate_retries(parent: ScenarioDefinition) -> ScenarioDefinition:
    if not parent.exchanges:
        raise ValueError("parent has no exchanges")
    first = parent.exchanges[0]
    retry = ExchangeSpec(
        phase=first.phase,
        method=first.method,
        path=first.path,
        sequence=first.sequence + 1,
        status_code=first.status_code,
        response_body=deepcopy(first.response_body),
    )
    exchanges = [first, retry, *parent.exchanges[1:]]
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-retry"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-retry",
        description="Duplicate retry of the first exchange; labels remain invariant.",
        parent_scenario_id=parent.id,
    )


def inject_rate_limit_then_success(parent: ScenarioDefinition) -> ScenarioDefinition:
    if not parent.exchanges:
        raise ValueError("parent has no exchanges")
    first = parent.exchanges[0]
    limited = ExchangeSpec(
        phase=first.phase,
        method=first.method,
        path=first.path,
        sequence=first.sequence,
        status_code=429,
        response_body={"error": "rate_limited"},
    )
    success = ExchangeSpec(
        phase=first.phase,
        method=first.method,
        path=first.path,
        sequence=first.sequence + 1,
        status_code=200,
        response_body=deepcopy(first.response_body),
    )
    exchanges = [limited, success, *parent.exchanges[1:]]
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-429"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-429",
        description="HTTP 429 followed by success on the same path.",
        parent_scenario_id=parent.id,
    )


def partial_sensitive_exposure(parent: ScenarioDefinition) -> ScenarioDefinition:
    exchanges: list[ExchangeSpec] = []
    for exchange in parent.exchanges:
        body = exchange.response_body
        if isinstance(body, dict) and "billing_email" in body:
            slim = {k: v for k, v in body.items() if k != "tax_id"}
            exchanges.append(
                ExchangeSpec.model_validate(
                    {**exchange.model_dump(mode="python"), "response_body": slim}
                )
            )
        else:
            exchanges.append(exchange)
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-partial-sensitive"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-partial-sensitive",
        description="Partial sensitive-field exposure; billing_email remains known.",
        parent_scenario_id=parent.id,
    )


def nested_sensitive_fields(parent: ScenarioDefinition) -> ScenarioDefinition:
    exchanges: list[ExchangeSpec] = []
    for exchange in parent.exchanges:
        body = exchange.response_body
        if isinstance(body, dict) and "billing_email" in body:
            nested = {
                "plan": body.get("plan"),
                "profile": {
                    "billing_email": body["billing_email"],
                    "tax_id": body.get("tax_id"),
                },
            }
            exchanges.append(
                ExchangeSpec.model_validate(
                    {**exchange.model_dump(mode="python"), "response_body": nested}
                )
            )
        else:
            exchanges.append(exchange)
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-nested-sensitive"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-nested-sensitive",
        description="Nested sensitive fields under profile.*; leaf markers still match.",
        parent_scenario_id=parent.id,
    )


def reorder_endpoints(parent: ScenarioDefinition) -> ScenarioDefinition:
    by_phase: dict[str, list[ExchangeSpec]] = {"baseline": [], "mutated": []}
    for exchange in parent.exchanges:
        by_phase[exchange.phase].append(exchange)
    exchanges = list(reversed(by_phase["baseline"])) + list(reversed(by_phase["mutated"]))
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-endpoint-order"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-endpoint-order",
        description="Same endpoint set in different order; no divergence.",
        parent_scenario_id=parent.id,
    )


def ambiguous_profile_path(parent: ScenarioDefinition) -> ScenarioDefinition:
    exchanges = list(parent.exchanges) + [
        ExchangeSpec(
            phase="mutated",
            method="GET",
            path="/api/v1/profile",
            sequence=0,
            response_body={"display_name": "ambiguous"},
        )
    ]
    labels = list(parent.expected_labels) + [
        ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT, endpoint="/api/v1/profile")
    ]
    if FindingCategory.BEHAVIORAL_DIVERGENCE not in {label.category for label in labels}:
        labels.append(ExpectedLabel(category=FindingCategory.BEHAVIORAL_DIVERGENCE))
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-ambiguous-profile"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges, expected_labels=labels),
        new_id=f"rob-{parent.id}-ambiguous-profile",
        description="Ambiguous undeclared /api/v1/profile path in mutated phase.",
        parent_scenario_id=parent.id,
        labels_invariant=False,
    )


def empty_response_bodies(parent: ScenarioDefinition) -> ScenarioDefinition:
    exchanges: list[ExchangeSpec] = []
    for index, exchange in enumerate(parent.exchanges):
        if index % 3 == 0:
            body: dict[str, Any] | list[Any] | None = {}
        elif index % 3 == 1:
            body = []
        else:
            body = None
        exchanges.append(
            ExchangeSpec.model_validate(
                {**exchange.model_dump(mode="python"), "response_body": body}
            )
        )
    labels = [
        label
        for label in parent.expected_labels
        if label.category != FindingCategory.SENSITIVE_FIELD_ACCESS
    ]
    target = parent.target.model_dump(mode="python")
    target["name"] = f"{parent.id}-empty-bodies"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges, expected_labels=labels),
        new_id=f"rob-{parent.id}-empty-bodies",
        description="Response bodies with empty dict/list/null.",
        parent_scenario_id=parent.id,
        labels_invariant=False,
    )


def path_normalization_edges(parent: ScenarioDefinition) -> ScenarioDefinition:
    exchanges: list[ExchangeSpec] = []
    for exchange in parent.exchanges:
        data = exchange.model_dump(mode="python")
        path = data["path"]
        if "?" not in path and path.rstrip("/") == path:
            # Store normalized query order so mock executor path matching agrees
            # with httpx/_request_path normalization.
            data["path"] = normalize_path(f"{path}?z=9&a=1")
        exchanges.append(ExchangeSpec.model_validate(data))
    expected = list(parent.target.expected_endpoints)
    extended = list(expected)
    for exchange in exchanges:
        normalized = normalize_path(exchange.path)
        base = normalized.split("?", 1)[0]
        if base in expected and normalized not in extended:
            extended.append(normalized)
    target = parent.target.model_dump(mode="python")
    target["expected_endpoints"] = extended
    target["name"] = f"{parent.id}-path-normalize"
    return _with_meta(
        _clone(parent, target=target, exchanges=exchanges),
        new_id=f"rob-{parent.id}-path-normalize",
        description="Path/query normalization edge cases; labels remain invariant.",
        parent_scenario_id=parent.id,
    )


def build_robustness_corpus(scenario_root: Path) -> list[ScenarioDefinition]:
    parents = {s.id: s for s in load_scenarios(scenario_root, suite="crm")}
    if not parents:
        parents = {s.id: s for s in load_scenarios(scenario_root, suite="all")}
    if not parents:
        raise ValueError(f"no parent scenarios under {scenario_root}")

    hidden_id = next((sid for sid in parents if "hidden" in sid), next(iter(parents)))
    sensitive_id = next((sid for sid in parents if "sensitive" in sid), next(iter(parents)))
    compliant_id = next(
        (sid for sid in parents if "compliant" in sid or "c1" in sid),
        next(iter(parents)),
    )
    hidden = parents[hidden_id]
    sensitive = parents[sensitive_id]
    compliant = parents[compliant_id]

    corpus: list[ScenarioDefinition] = []
    for count in HEALTH_COUNTS:
        corpus.append(inject_health_polls(hidden, count))
    corpus.append(permute_query_order(compliant))
    corpus.append(inject_duplicate_retries(compliant))
    corpus.append(inject_rate_limit_then_success(compliant))
    corpus.append(partial_sensitive_exposure(sensitive))
    corpus.append(nested_sensitive_fields(sensitive))
    corpus.append(reorder_endpoints(compliant))
    corpus.append(ambiguous_profile_path(compliant))
    corpus.append(empty_response_bodies(compliant))
    corpus.append(path_normalization_edges(compliant))
    return corpus


def _base_target(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "base_url": "http://mock.invalid/",
        "integration_sync_url": "http://integration.invalid/sync",
        "audit_base_url": "http://mock.invalid/",
        "expected_endpoints": ["/api/v1/customers"],
        "sensitive_markers": ["billing_email", "tax_id"],
    }


def build_evasion_corpus(scenario_root: Path) -> list[ScenarioDefinition]:
    parents = {s.id: s for s in load_scenarios(scenario_root, suite="all")}
    parent_id = next(iter(parents), "crm-c1-compliant")
    parent = parents.get(parent_id)

    def _boundary(
        scenario_id: str,
        description: str,
        exchanges: list[dict[str, Any]],
        expected_labels: list[dict[str, Any]],
    ) -> ScenarioDefinition:
        return ScenarioDefinition.model_validate(
            {
                "schema_version": "1.0.0",
                "id": scenario_id,
                "suite": "evasion",
                "platform_style": "generic-crm",
                "description": description,
                "parent_scenario_id": parent.id if parent else parent_id,
                "labels_invariant": False,
                "observable_by_model": False,
                "target": _base_target(scenario_id),
                "exchanges": exchanges,
                "expected_labels": expected_labels,
            }
        )

    compliant_exchanges = [
        {
            "phase": "baseline",
            "method": "GET",
            "path": "/api/v1/customers",
            "response_body": [{"customer_id": "c1"}],
        },
        {
            "phase": "mutated",
            "method": "GET",
            "path": "/api/v1/customers",
            "response_body": [{"customer_id": "c1"}],
        },
    ]
    return [
        _boundary(
            "eva-fn1-out-of-band",
            "FN1: out-of-band exfiltration with no observable violating exchange.",
            compliant_exchanges,
            [{"category": "hidden_endpoint", "endpoint": "/api/v1/exfil"}],
        ),
        _boundary(
            "eva-fn2-shared-token",
            "FN2: shared-token misuse attributed to another run ID (not in capture).",
            compliant_exchanges,
            [{"category": "sensitive_field_access", "endpoint": "/api/v1/customers"}],
        ),
        _boundary(
            "eva-fn3-delayed",
            "FN3: delayed activation outside the capture window.",
            compliant_exchanges,
            [{"category": "hidden_endpoint", "endpoint": "/api/v1/customers/c1/billing"}],
        ),
        _boundary(
            "eva-fn4-field-alias",
            "FN4: secret value under an unconfigured alias (known false negative).",
            [
                {
                    "phase": "baseline",
                    "method": "GET",
                    "path": "/api/v1/customers",
                    "response_body": [{"customer_id": "c1"}],
                },
                {
                    "phase": "mutated",
                    "method": "GET",
                    "path": "/api/v1/customers",
                    "response_body": [
                        {"customer_id": "c1", "secret_email": "alias@x.test"}
                    ],
                },
            ],
            [{"category": "sensitive_field_access", "endpoint": "/api/v1/customers"}],
        ),
    ]


def materialize_corpus_yaml(
    scenario_root: Path,
    *,
    robustness: list[ScenarioDefinition] | None = None,
    evasion: list[ScenarioDefinition] | None = None,
) -> None:
    rob = robustness if robustness is not None else build_robustness_corpus(scenario_root)
    eva = evasion if evasion is not None else build_evasion_corpus(scenario_root)
    for suite_name, scenarios in (("robustness", rob), ("evasion", eva)):
        out_dir = Path(scenario_root) / suite_name
        out_dir.mkdir(parents=True, exist_ok=True)
        for scenario in scenarios:
            path = out_dir / f"{scenario.id}.yaml"
            path.write_text(
                yaml.safe_dump(
                    scenario.model_dump(mode="json"),
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
    invalid_dir = Path(scenario_root) / "evasion" / "invalid"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "eva-malformed.yaml").write_text(
        "# Intentionally invalid: must fail ScenarioDefinition validation.\n"
        "schema_version: '1.0.0'\n"
        "id: eva-malformed\n"
        "suite: evasion\n",
        encoding="utf-8",
    )


def _metrics_with_wilson(outcomes: list[ScenarioOutcome], confidence: float) -> dict[str, Any]:
    category_metrics = evaluate_categories(outcomes)
    micro = micro_average(category_metrics)
    categories: list[dict[str, Any]] = []
    for metric in category_metrics:
        precision_trials = metric.tp + metric.fp
        recall_trials = metric.tp + metric.fn
        row = metric.model_dump(mode="json")
        row["precision_interval"] = wilson_interval(
            metric.tp, precision_trials, confidence_level=confidence
        ).model_dump(mode="json")
        row["recall_interval"] = wilson_interval(
            metric.tp, recall_trials, confidence_level=confidence
        ).model_dump(mode="json")
        categories.append(row)
    micro_row = micro.model_dump(mode="json")
    micro_row["precision_interval"] = wilson_interval(
        micro.tp, micro.tp + micro.fp, confidence_level=confidence
    ).model_dump(mode="json")
    micro_row["recall_interval"] = wilson_interval(
        micro.tp, micro.tp + micro.fn, confidence_level=confidence
    ).model_dump(mode="json")
    return {"categories": categories, "micro": micro_row}


async def run_robustness_suite(
    scenario_root: Path,
    protocol_path: Path,
    output_root: Path,
    command: list[str],
) -> dict[str, Any]:
    protocol = load_evaluation_protocol(protocol_path)
    digest = protocol_sha256(protocol_path)
    confidence = float(protocol["uncertainty"]["confidence_level"])
    seed = int(protocol.get("seed", SEED))

    robustness_scenarios = load_scenarios(scenario_root, suite="robustness")
    evasion_scenarios = load_scenarios(scenario_root, suite="evasion")
    if not robustness_scenarios:
        robustness_scenarios = build_robustness_corpus(scenario_root)
    if not evasion_scenarios:
        evasion_scenarios = build_evasion_corpus(scenario_root)

    in_scope_outcomes: list[ScenarioOutcome] = []
    boundary_outcomes: list[ScenarioOutcome] = []
    raw_dir = Path(output_root) / "raw" / "robustness"

    for scenario in [*robustness_scenarios, *evasion_scenarios]:
        outcome = await execute_scenario(scenario)
        _print_outcome(outcome)
        bucket = boundary_outcomes if not scenario.observable_by_model else in_scope_outcomes
        bucket.append(outcome)
        envelope = ArtifactEnvelope(
            provenance=collect_provenance(command, seed=seed),
            experiment="robustness",
            configuration={
                "protocol_sha256": digest,
                "scenario_id": scenario.id,
                "suite": scenario.suite,
                "parent_scenario_id": scenario.parent_scenario_id,
                "labels_invariant": scenario.labels_invariant,
                "observable_by_model": scenario.observable_by_model,
            },
            payload=_outcome_payload(outcome),
        )
        write_artifact(raw_dir / f"{scenario.id}.json", envelope)

    in_scope_results = [
        {
            "scenario_id": o.scenario_id,
            "passed": _outcome_passed(o),
            "expected_categories": sorted(c.value for c in o.expected_categories),
            "observed_categories": sorted(c.value for c in o.observed_categories),
        }
        for o in in_scope_outcomes
    ]
    in_scope_passed = bool(in_scope_results) and all(r["passed"] for r in in_scope_results)
    summary: dict[str, Any] = {
        "protocol_sha256": digest,
        "seed": seed,
        "hypotheses": protocol["hypotheses"],
        "in_scope_passed": in_scope_passed,
        "in_scope": {
            **_metrics_with_wilson(in_scope_outcomes, confidence),
            "scenario_count": len(in_scope_outcomes),
            "passed": in_scope_passed,
            "scenario_results": in_scope_results,
        },
        "model_boundary": {
            **_metrics_with_wilson(boundary_outcomes, confidence),
            "scenario_count": len(boundary_outcomes),
            "scenario_results": [
                {
                    "scenario_id": o.scenario_id,
                    "passed": _outcome_passed(o),
                    "expected_categories": sorted(c.value for c in o.expected_categories),
                    "observed_categories": sorted(c.value for c in o.observed_categories),
                    "note": "Excluded from primary in-scope recall; declared model boundary.",
                }
                for o in boundary_outcomes
            ],
        },
    }
    derived = ArtifactEnvelope(
        provenance=collect_provenance(command, seed=seed),
        experiment="robustness_metrics",
        configuration={
            "protocol_sha256": digest,
            "protocol_path": str(protocol_path),
            "scenario_root": str(scenario_root),
            "confidence_level": confidence,
        },
        payload=summary,
    )
    path = write_artifact(Path(output_root) / "derived" / "robustness_metrics.json", derived)
    summary["_artifact_path"] = str(path)
    return summary


@app.command()
def main(
    scenario_root: Path = typer.Option(DEFAULT_SCENARIO_ROOT, "--scenario-root"),
    protocol_path: Path = typer.Option(DEFAULT_PROTOCOL, "--protocol"),
    output_root: Path = typer.Option(Path("results"), "--output-root"),
    materialize: bool = typer.Option(
        False,
        "--materialize",
        help="Write generated robustness/evasion YAML under scenario-root",
    ),
) -> None:
    """Run robustness and evasion suites; separate in-scope from model-boundary."""
    command = ["python", "-m", "ait.experiments.robustness", *sys.argv[1:]]
    if materialize:
        materialize_corpus_yaml(scenario_root)
        typer.echo(f"Materialized robustness/evasion YAML under {scenario_root}")
    summary = asyncio.run(
        run_robustness_suite(scenario_root, protocol_path, output_root, command)
    )
    in_scope = summary["in_scope"]["scenario_count"]
    boundary = summary["model_boundary"]["scenario_count"]
    status = "PASS" if summary["in_scope_passed"] else "FAIL"
    typer.echo(
        f"{status} robustness: in_scope={in_scope} model_boundary={boundary} "
        f"protocol_sha256={summary['protocol_sha256'][:12]}..."
    )
    raise typer.Exit(0 if summary["in_scope_passed"] else 1)


if __name__ == "__main__":
    app()
