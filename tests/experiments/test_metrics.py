from __future__ import annotations

from ait.experiments.metrics import CategoryMetrics, evaluate_categories, micro_average
from ait.experiments.schema import ScenarioOutcome
from ait.models import FindingCategory, RunReport


def _outcome(
    scenario_id: str,
    expected: set[FindingCategory],
    observed: set[FindingCategory],
) -> ScenarioOutcome:
    return ScenarioOutcome(
        scenario_id=scenario_id,
        expected_categories=expected,
        observed_categories=observed,
        report=RunReport(
            run_id=scenario_id,
            target_name=scenario_id,
            status="completed",
            reached_endpoints=[],
            hidden_endpoints=[],
            sensitive_fields_accessed=[],
            divergence_summary=[],
            risk_score=0,
            findings=[],
        ),
    )


def test_evaluate_categories_tp_fp_fn_tn_and_undefined_metrics():
    outcomes = [
        _outcome(
            "pos",
            {FindingCategory.HIDDEN_ENDPOINT},
            {FindingCategory.HIDDEN_ENDPOINT},
        ),
        _outcome(
            "fp",
            set(),
            {FindingCategory.HIDDEN_ENDPOINT},
        ),
        _outcome(
            "fn",
            {FindingCategory.HIDDEN_ENDPOINT},
            set(),
        ),
        _outcome(
            "tn",
            set(),
            set(),
        ),
    ]
    metrics = {m.category: m for m in evaluate_categories(outcomes)}
    hidden = metrics[FindingCategory.HIDDEN_ENDPOINT]
    assert hidden.tp == 1
    assert hidden.fp == 1
    assert hidden.fn == 1
    assert hidden.tn == 1
    assert hidden.precision == 0.5
    assert hidden.recall == 0.5
    assert hidden.f1 == 0.5


def test_evaluate_categories_duplicate_findings_count_once_per_scenario():
    outcomes = [
        _outcome(
            "dup",
            {FindingCategory.SENSITIVE_FIELD_ACCESS},
            {FindingCategory.SENSITIVE_FIELD_ACCESS},
        )
    ]
    # observed_categories is already a set; ensure category presence is binary
    metrics = {m.category: m for m in evaluate_categories(outcomes)}
    sensitive = metrics[FindingCategory.SENSITIVE_FIELD_ACCESS]
    assert sensitive.tp == 1
    assert sensitive.fp == 0
    assert sensitive.fn == 0


def test_evaluate_categories_empty_expected_all_true_negatives_for_absent_cats():
    outcomes = [_outcome("clean", set(), set())]
    metrics = evaluate_categories(outcomes)
    by_cat = {m.category: m for m in metrics}
    for category in FindingCategory:
        assert by_cat[category].tn == 1
        assert by_cat[category].tp == 0
        assert by_cat[category].fp == 0
        assert by_cat[category].fn == 0
        assert by_cat[category].precision is None
        assert by_cat[category].recall is None
        assert by_cat[category].f1 is None


def test_undefined_metrics_serialize_as_null():
    metrics = CategoryMetrics(
        category=FindingCategory.BEHAVIORAL_DIVERGENCE,
        tp=0,
        fp=0,
        fn=0,
        tn=1,
        precision=None,
        recall=None,
        f1=None,
    )
    payload = metrics.model_dump(mode="json")
    assert payload["precision"] is None
    assert payload["recall"] is None
    assert payload["f1"] is None


def test_micro_average_aggregates_counts():
    metrics = [
        CategoryMetrics(
            category=FindingCategory.HIDDEN_ENDPOINT,
            tp=1,
            fp=1,
            fn=0,
            tn=1,
            precision=0.5,
            recall=1.0,
            f1=2 / 3,
        ),
        CategoryMetrics(
            category=FindingCategory.SENSITIVE_FIELD_ACCESS,
            tp=1,
            fp=0,
            fn=1,
            tn=1,
            precision=1.0,
            recall=0.5,
            f1=2 / 3,
        ),
    ]
    micro = micro_average(metrics)
    assert micro.tp == 2
    assert micro.fp == 1
    assert micro.fn == 1
    assert micro.tn == 2
    assert micro.precision == 2 / 3
    assert micro.recall == 2 / 3
