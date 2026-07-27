from __future__ import annotations

from collections import defaultdict

from ait.models import (
    CapturedExchange,
    Finding,
    FindingCategory,
    RunReport,
    Severity,
    TargetConfig,
)


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
) -> RunReport:
    findings: list[Finding] = []
    reached_endpoints = sorted({exchange.path for exchange in exchanges})
    hidden_endpoints = sorted(
        path for path in reached_endpoints if path not in set(target.expected_endpoints)
    )
    sensitive_fields = sorted(
        {
            field
            for exchange in exchanges
            for field in exchange.extracted_fields
            if field in set(target.sensitive_markers)
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
            field in set(target.sensitive_markers) for field in exchange.extracted_fields
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

    risk_score = min(
        100,
        len(hidden_endpoints) * 25 + len(sensitive_fields) * 20 + len(divergence_summary) * 15,
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
