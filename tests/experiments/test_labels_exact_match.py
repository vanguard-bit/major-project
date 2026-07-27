from __future__ import annotations

from ait.experiments.schema import ExpectedLabel, labels_exact_match
from ait.models import Finding, FindingCategory, Severity


def _finding(category: FindingCategory, endpoint: str) -> Finding:
    return Finding(
        severity=Severity.MEDIUM,
        category=category,
        endpoint=endpoint,
        title="test",
        evidence="evidence",
        expected_behavior="expected",
        observed_behavior="observed",
        remediation_note="note",
    )


def test_unexpected_same_category_endpoint_fails() -> None:
    expected = [
        ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT, endpoint="/a"),
        ExpectedLabel(category=FindingCategory.BEHAVIORAL_DIVERGENCE),
    ]
    findings = [
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/a"),
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/b"),
        _finding(FindingCategory.BEHAVIORAL_DIVERGENCE, "/a"),
    ]
    assert labels_exact_match(expected, findings) is False


def test_reordered_query_params_pass_after_normalization() -> None:
    expected = [
        ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT, endpoint="/x?b=2&a=1"),
    ]
    findings = [
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/x?a=1&b=2"),
    ]
    assert ExpectedLabel.model_validate(
        {"category": "hidden_endpoint", "endpoint": "/x?b=2&a=1"}
    ).endpoint == "/x?a=1&b=2"
    assert labels_exact_match(expected, findings) is True


def test_wrong_endpoint_fails() -> None:
    expected = [
        ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT, endpoint="/correct"),
    ]
    findings = [
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/wrong"),
    ]
    assert labels_exact_match(expected, findings) is False


def test_category_only_allows_any_endpoints_for_category() -> None:
    expected = [ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT)]
    findings = [
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/a"),
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/b"),
    ]
    assert labels_exact_match(expected, findings) is True


def test_exact_endpoint_set_match_passes() -> None:
    expected = [
        ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT, endpoint="/a"),
        ExpectedLabel(category=FindingCategory.HIDDEN_ENDPOINT, endpoint="/b"),
    ]
    findings = [
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/b"),
        _finding(FindingCategory.HIDDEN_ENDPOINT, "/a"),
    ]
    assert labels_exact_match(expected, findings) is True
