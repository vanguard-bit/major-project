from __future__ import annotations

import pytest
from pydantic import ValidationError

from ait.experiments.statistics import ProportionInterval, wilson_interval


def test_wilson_interval_known_95_percent_values():
    result = wilson_interval(81, 100, confidence_level=0.95)
    assert result.successes == 81
    assert result.trials == 100
    assert result.estimate == pytest.approx(0.81)
    assert result.lower == pytest.approx(0.7222115462, abs=1e-6)
    assert result.upper == pytest.approx(0.8748524849, abs=1e-6)
    assert result.confidence_level == 0.95


def test_wilson_interval_zero_trials_serializes_as_null():
    result = wilson_interval(0, 0, confidence_level=0.95)
    assert result.estimate is None
    assert result.lower is None
    assert result.upper is None
    dumped = result.model_dump(mode="json")
    assert dumped["estimate"] is None
    assert dumped["lower"] is None
    assert dumped["upper"] is None


def test_wilson_interval_rejects_negative_counts():
    with pytest.raises(ValueError, match="negative"):
        wilson_interval(-1, 10)
    with pytest.raises(ValueError, match="negative"):
        wilson_interval(1, -1)


def test_wilson_interval_rejects_successes_greater_than_trials():
    with pytest.raises(ValueError, match="successes"):
        wilson_interval(11, 10)


def test_wilson_interval_rejects_invalid_confidence_level():
    with pytest.raises(ValueError, match="confidence"):
        wilson_interval(5, 10, confidence_level=0.0)
    with pytest.raises(ValueError, match="confidence"):
        wilson_interval(5, 10, confidence_level=1.0)
    with pytest.raises(ValueError, match="confidence"):
        wilson_interval(5, 10, confidence_level=1.5)


def test_proportion_interval_is_pydantic_model():
    interval = ProportionInterval(
        successes=1,
        trials=2,
        estimate=0.5,
        lower=0.1,
        upper=0.9,
        confidence_level=0.95,
    )
    assert interval.trials == 2
    with pytest.raises(ValidationError):
        ProportionInterval(
            successes=1,
            trials=2,
            estimate=0.5,
            lower=0.1,
            upper=0.9,
            confidence_level="nope",  # type: ignore[arg-type]
        )
