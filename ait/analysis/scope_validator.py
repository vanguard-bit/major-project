from __future__ import annotations

from ait.models import CapturedExchange, Finding, FindingCategory, Severity, TargetConfig


def detect_scope_violations(
    target: TargetConfig,
    exchanges: list[CapturedExchange],
) -> list[Finding]:
    """Validate that accessed OAuth scopes match the declared expected_scopes."""
    findings: list[Finding] = []
    if not target.expected_scopes:
        return findings

    granted_scope_str = target.token_config.scope or ""
    granted_scopes = set(granted_scope_str.split()) if granted_scope_str else set()
    expected_scopes = set(target.expected_scopes)
    excess_scopes = granted_scopes - expected_scopes

    if excess_scopes:
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category=FindingCategory.SCOPE_VIOLATION,
                endpoint="oauth/token",
                title="Excess OAuth scopes granted",
                evidence=f"Token includes scopes not required by the integration: {', '.join(sorted(excess_scopes))}",
                expected_behavior=f"Integration should only request scopes: {', '.join(sorted(expected_scopes))}",
                observed_behavior=f"Granted scopes: {', '.join(sorted(granted_scopes))}",
                confidence=1.0,
                remediation_note="Apply the principle of least privilege: remove excess OAuth scopes.",
            )
        )

    sensitive_paths = {
        exchange.path
        for exchange in exchanges
        if exchange.contains_sensitive_marker or any(
            f in set(target.sensitive_markers) for f in exchange.extracted_fields
        )
    }
    billing_scopes = {"billing.read", "billing.write", "finance.read"}
    has_billing_scope = bool(granted_scopes & billing_scopes)

    for path in sensitive_paths:
        if not has_billing_scope and ("billing" in path or "payment" in path or "finance" in path):
            findings.append(
                Finding(
                    severity=Severity.HIGH,
                    category=FindingCategory.SCOPE_VIOLATION,
                    endpoint=path,
                    title="Sensitive endpoint accessed without matching scope",
                    evidence=f"Endpoint {path} was accessed but no billing/finance scope was declared.",
                    expected_behavior="Billing endpoints require explicit billing scope authorization.",
                    observed_behavior=f"Endpoint accessed with scopes: {', '.join(sorted(granted_scopes)) or 'none'}",
                    confidence=0.9,
                    remediation_note="Declare the required scope or remove access to this endpoint.",
                )
            )

    return findings
