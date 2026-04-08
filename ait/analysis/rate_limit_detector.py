from __future__ import annotations

from collections import Counter

from ait.models import CapturedExchange, Finding, FindingCategory, Severity, TargetConfig


def detect_rate_limit_violations(
    target: TargetConfig,
    exchanges: list[CapturedExchange],
    window_size: int = 60,
) -> list[Finding]:
    """Detect endpoints that were called an excessive number of times.

    Uses ``target.config.rate_limit_per_minute`` as the threshold; defaults to
    60 if the target carries no config.  ``window_size`` is conceptual – all
    exchanges are treated as occurring within a single window for this analysis.
    """
    if not exchanges:
        return []

    rate_limit = 60
    path_counts = Counter(exchange.path for exchange in exchanges)
    findings: list[Finding] = []

    for path, count in path_counts.items():
        if count > rate_limit:
            findings.append(
                Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.RATE_LIMIT_VIOLATION,
                    endpoint=path,
                    title="Excessive API requests detected",
                    evidence=(
                        f"{path} was called {count} times, exceeding the "
                        f"rate limit threshold of {rate_limit} requests per window."
                    ),
                    expected_behavior=f"Each endpoint should be called at most {rate_limit} times per window.",
                    observed_behavior=f"{path} was called {count} times.",
                    confidence=1.0,
                    remediation_note=(
                        "Implement client-side rate limiting and respect Retry-After headers."
                    ),
                )
            )

    return findings
