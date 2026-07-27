from __future__ import annotations

import math
from statistics import NormalDist

from pydantic import BaseModel


class ProportionInterval(BaseModel):
    successes: int
    trials: int
    estimate: float | None
    lower: float | None
    upper: float | None
    confidence_level: float


def wilson_interval(
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> ProportionInterval:
    if successes < 0 or trials < 0:
        raise ValueError("negative counts are not allowed")
    if successes > trials:
        raise ValueError("successes cannot exceed trials")
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be strictly between 0 and 1")

    if trials == 0:
        return ProportionInterval(
            successes=successes,
            trials=trials,
            estimate=None,
            lower=None,
            upper=None,
            confidence_level=confidence_level,
        )

    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    p = successes / trials
    z2 = z * z
    n = float(trials)
    denominator = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denominator
    return ProportionInterval(
        successes=successes,
        trials=trials,
        estimate=p,
        lower=centre - margin,
        upper=centre + margin,
        confidence_level=confidence_level,
    )
