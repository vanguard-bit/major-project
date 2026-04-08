from __future__ import annotations

from collections import Counter

from ait.models import CapturedExchange, Finding, FindingCategory, Severity


def detect_anomalies(exchanges: list[CapturedExchange]) -> list[Finding]:
    """ML-based anomaly detection using Isolation Forest on API access patterns.

    Extracts numeric features per exchange and flags statistical outliers.
    Falls back gracefully when scikit-learn is unavailable or there is
    insufficient data (fewer than 5 samples).
    """
    if len(exchanges) < 5:
        return []

    try:
        from sklearn.ensemble import IsolationForest  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return []

    path_counts = Counter(e.path for e in exchanges)
    method_counts = Counter(e.method for e in exchanges)

    features = []
    for exchange in exchanges:
        path_freq = path_counts[exchange.path]
        method_freq = method_counts[exchange.method]
        field_count = len(exchange.extracted_fields)
        is_sensitive = int(exchange.contains_sensitive_marker)
        status_5xx = int(exchange.status_code >= 500)
        features.append([path_freq, method_freq, field_count, is_sensitive, status_5xx])

    X = np.array(features, dtype=float)
    contamination = min(0.1, max(0.01, 1.0 / len(exchanges)))
    clf = IsolationForest(contamination=contamination, random_state=42)
    labels = clf.fit_predict(X)

    findings: list[Finding] = []
    for idx, label in enumerate(labels):
        if label == -1:
            exchange = exchanges[idx]
            findings.append(
                Finding(
                    severity=Severity.MEDIUM,
                    category=FindingCategory.ANOMALY,
                    endpoint=exchange.path,
                    title="Anomalous API access pattern detected",
                    evidence=(
                        f"Isolation Forest flagged {exchange.method} {exchange.path} "
                        f"(phase={exchange.phase}, fields={exchange.extracted_fields}) "
                        "as a statistical outlier among observed exchanges."
                    ),
                    expected_behavior="API access patterns should be consistent with baseline behavior.",
                    observed_behavior=f"Anomalous request: {exchange.method} {exchange.path} → {exchange.status_code}",
                    confidence=0.75,
                    remediation_note="Investigate whether the flagged access is intentional; if not, restrict it.",
                )
            )

    return findings
