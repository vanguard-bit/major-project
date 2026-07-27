from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from ait.experiments.schema import ScenarioOutcome
from ait.models import FindingCategory


class CategoryMetrics(BaseModel):
    category: FindingCategory | Literal["micro"]
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    recall: float | None
    f1: float | None


def _precision_recall_f1(
    tp: int, fp: int, fn: int
) -> tuple[float | None, float | None, float | None]:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def evaluate_categories(outcomes: Sequence[ScenarioOutcome]) -> list[CategoryMetrics]:
    results: list[CategoryMetrics] = []
    for category in FindingCategory:
        tp = fp = fn = tn = 0
        for outcome in outcomes:
            expected = category in outcome.expected_categories
            observed = category in outcome.observed_categories
            if expected and observed:
                tp += 1
            elif not expected and observed:
                fp += 1
            elif expected and not observed:
                fn += 1
            else:
                tn += 1
        precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
        results.append(
            CategoryMetrics(
                category=category,
                tp=tp,
                fp=fp,
                fn=fn,
                tn=tn,
                precision=precision,
                recall=recall,
                f1=f1,
            )
        )
    return results


def micro_average(metrics: Sequence[CategoryMetrics]) -> CategoryMetrics:
    tp = sum(item.tp for item in metrics)
    fp = sum(item.fp for item in metrics)
    fn = sum(item.fn for item in metrics)
    tn = sum(item.tn for item in metrics)
    precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
    return CategoryMetrics(
        category="micro",
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        recall=recall,
        f1=f1,
    )
