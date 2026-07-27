from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from ait.models import (
    CapturedExchange,
    Finding,
    FindingCategory,
    RunReport,
    Severity,
    TargetConfig,
)


class RiskWeights(BaseModel):
    hidden_endpoint: float = 25.0
    sensitive_field: float = 20.0
    divergence: float = 15.0
    cap: float = 100.0


DEFAULT_RISK_WEIGHTS = RiskWeights()


def calculate_risk_score(
    hidden_endpoint_count: int,
    sensitive_field_count: int,
    divergence_count: int,
    weights: RiskWeights = DEFAULT_RISK_WEIGHTS,
) -> float:
    if hidden_endpoint_count < 0 or sensitive_field_count < 0 or divergence_count < 0:
        raise ValueError("negative counts are not allowed")
    raw = (
        hidden_endpoint_count * weights.hidden_endpoint
        + sensitive_field_count * weights.sensitive_field
        + divergence_count * weights.divergence
    )
    return min(weights.cap, raw)


def extract_field_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(extract_field_paths(item, path))
    elif isinstance(value, list):
        for item in value:
            paths.update(extract_field_paths(item, prefix))
    return paths


def field_matches_sensitive_marker(field: str, markers: set[str]) -> bool:
    if field in markers:
        return True
    leaf = field.rsplit(".", 1)[-1]
    return leaf in markers


def _severity_for_endpoint(path: str, sensitive_hit: bool) -> Severity:
    if sensitive_hit:
        return Severity.CRITICAL
    if "billing" in path or "hidden" in path:
        return Severity.HIGH
    return Severity.MEDIUM


def analyze_run(
    run_id: str,
    target: TargetConfig,
    exchanges: list[CapturedExchange],
    weights: RiskWeights | None = None,
) -> RunReport:
    effective_weights = weights if weights is not None else DEFAULT_RISK_WEIGHTS
    findings: list[Finding] = []
    markers = set(target.sensitive_markers)
    reached_endpoints = sorted({exchange.path for exchange in exchanges})
    hidden_endpoints = sorted(
        path for path in reached_endpoints if path not in set(target.expected_endpoints)
    )
    sensitive_fields = sorted(
        {
            field
            for exchange in exchanges
            for field in exchange.extracted_fields
            if field_matches_sensitive_marker(field, markers)
        }
    )
    by_phase: dict[str, set[str]] = defaultdict(set)
    for exchange in exchanges:
        by_phase[exchange.phase].add(exchange.path)

    baseline_only = sorted(by_phase.get("baseline", set()) - by_phase.get("mutated", set()))
    mutated_only = sorted(by_phase.get("mutated", set()) - by_phase.get("baseline", set()))
    divergence_summary: list[str] = []
    if baseline_only:
        divergence_summary.append(f"Baseline-only endpoints: {', '.join(baseline_only)}")
    if mutated_only:
        divergence_summary.append(f"Mutated-only endpoints: {', '.join(mutated_only)}")

    for path in hidden_endpoints:
        evidence = f"Observed endpoint {path} but it was not declared as expected."
        findings.append(
            Finding(
                severity=_severity_for_endpoint(path, False),
                category=FindingCategory.HIDDEN_ENDPOINT,
                endpoint=path,
                title="Hidden endpoint access detected",
                evidence=evidence,
                expected_behavior="Integration should stay within the declared endpoint allowlist.",
                observed_behavior=evidence,
                remediation_note="Reduce granted scopes and remove undeclared endpoint calls.",
            )
        )

    if mutated_only:
        findings.append(
            Finding(
                severity=Severity.HIGH,
                category=FindingCategory.BEHAVIORAL_DIVERGENCE,
                endpoint=", ".join(mutated_only),
                title="Mutated execution exposed additional behavior",
                evidence="Additional endpoints were reached during the mutated run.",
                expected_behavior="State changes should not unlock extra undeclared data access.",
                observed_behavior=f"Mutated phase reached: {', '.join(mutated_only)}",
                remediation_note=(
                    "Inspect state-dependent branches and scope checks in the integration."
                ),
            )
        )

    for exchange in exchanges:
        sensitive_hit = exchange.contains_sensitive_marker or any(
            field_matches_sensitive_marker(field, markers) for field in exchange.extracted_fields
        )
        if sensitive_hit:
            observed = ", ".join(exchange.extracted_fields) or "unknown"
            findings.append(
                Finding(
                    severity=_severity_for_endpoint(exchange.path, True),
                    category=FindingCategory.SENSITIVE_FIELD_ACCESS,
                    endpoint=exchange.path,
                    title="Sensitive marker accessed",
                    evidence=(
                        f"Response from {exchange.path} contained a configured sensitive marker."
                    ),
                    expected_behavior=(
                        "Sensitive marker fields should not be retrieved unless "
                        "explicitly approved."
                    ),
                    observed_behavior=f"Observed fields: {observed}",
                    remediation_note=(
                        "Restrict the integration to minimum necessary fields "
                        "and revalidate scopes."
                    ),
                )
            )

    risk_score = round(
        calculate_risk_score(
            len(hidden_endpoints),
            len(sensitive_fields),
            len(divergence_summary),
            weights=effective_weights,
        ),
        2,
    )

    return RunReport(
        run_id=run_id,
        target_name=target.name,
        status="completed",
        reached_endpoints=reached_endpoints,
        hidden_endpoints=hidden_endpoints,
        sensitive_fields_accessed=sensitive_fields,
        divergence_summary=divergence_summary,
        risk_score=risk_score,
        findings=findings,
    )
