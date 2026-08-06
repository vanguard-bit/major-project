from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ait.models import (
    CapturedExchange,
    Finding,
    FindingCategory,
    RunReport,
    Severity,
    TargetConfig,
)


class RiskWeights(BaseModel):
    """Immutable risk-score weights. Cap must be strictly positive and finite."""

    model_config = ConfigDict(frozen=True)

    hidden_endpoint: float = Field(default=25.0, ge=0.0)
    sensitive_field: float = Field(default=20.0, ge=0.0)
    divergence: float = Field(default=15.0, ge=0.0)
    cap: float = Field(default=100.0, gt=0.0)

    @field_validator("hidden_endpoint", "sensitive_field", "divergence", "cap")
    @classmethod
    def require_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("weights must be finite")
        return value


DEFAULT_RISK_WEIGHTS = RiskWeights()


def calculate_risk_score(
    hidden_endpoint_count: int,
    sensitive_field_count: int,
    divergence_count: int,
    weights: RiskWeights | None = None,
) -> float:
    if hidden_endpoint_count < 0 or sensitive_field_count < 0 or divergence_count < 0:
        raise ValueError("negative counts are not allowed")
    effective = weights if weights is not None else DEFAULT_RISK_WEIGHTS
    raw = (
        hidden_endpoint_count * effective.hidden_endpoint
        + sensitive_field_count * effective.sensitive_field
        + divergence_count * effective.divergence
    )
    return min(effective.cap, raw)


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
    from ait.experiments.scenario_loader import normalize_path

    effective_weights = weights if weights is not None else DEFAULT_RISK_WEIGHTS
    findings: list[Finding] = []
    markers = set(target.sensitive_markers)
    expected_endpoints = {normalize_path(path) for path in target.expected_endpoints}
    normalized_exchanges = [
        (exchange, normalize_path(exchange.path)) for exchange in exchanges
    ]
    reached_endpoints = sorted({path for _, path in normalized_exchanges})
    hidden_endpoints = sorted(
        path for path in reached_endpoints if path not in expected_endpoints
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
    for exchange, path in normalized_exchanges:
        by_phase[exchange.phase].add(path)

    # Divergence is only meaningful when both phases were executed.
    both_phases_present = bool(by_phase.get("baseline")) and bool(by_phase.get("mutated"))
    baseline_only = (
        sorted(by_phase.get("baseline", set()) - by_phase.get("mutated", set()))
        if both_phases_present
        else []
    )
    mutated_only = (
        sorted(by_phase.get("mutated", set()) - by_phase.get("baseline", set()))
        if both_phases_present
        else []
    )
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

    for exchange, path in normalized_exchanges:
        sensitive_hit = exchange.contains_sensitive_marker or any(
            field_matches_sensitive_marker(field, markers) for field in exchange.extracted_fields
        )
        if sensitive_hit:
            observed = ", ".join(exchange.extracted_fields) or "unknown"
            findings.append(
                Finding(
                    severity=_severity_for_endpoint(path, True),
                    category=FindingCategory.SENSITIVE_FIELD_ACCESS,
                    endpoint=path,
                    title="Sensitive marker accessed",
                    evidence=(
                        f"Response from {path} contained a configured sensitive marker."
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
