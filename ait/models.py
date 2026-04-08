from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class AuthType(str, Enum):
    STATIC_TOKEN = "static_token"
    OAUTH_CLIENT_CREDENTIALS = "oauth_client_credentials"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    HIDDEN_ENDPOINT = "hidden_endpoint"
    SENSITIVE_FIELD_ACCESS = "sensitive_field_access"
    BEHAVIORAL_DIVERGENCE = "behavioral_divergence"
    POLICY_VIOLATION = "policy_violation"
    SCOPE_VIOLATION = "scope_violation"
    ANOMALY = "anomaly"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"


class ComplianceStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    NOT_APPLICABLE = "not_applicable"


class ComplianceStandard(str, Enum):
    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"


class TokenConfig(BaseModel):
    token: str | None = None
    token_url: HttpUrl | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None


class TargetConfig(BaseModel):
    name: str
    environment: str = "demo"
    base_url: HttpUrl
    integration_sync_url: HttpUrl
    audit_base_url: HttpUrl
    auth_type: AuthType = AuthType.STATIC_TOKEN
    token_config: TokenConfig = Field(default_factory=TokenConfig)
    openapi_paths: list[str] = Field(default_factory=list)
    seed_endpoints: list[str] = Field(default_factory=list)
    expected_endpoints: list[str] = Field(default_factory=list)
    expected_scopes: list[str] = Field(default_factory=list)
    sensitive_markers: list[str] = Field(default_factory=list)
    description: str = ""


class TestRunConfig(BaseModel):
    crawl_depth: int = 2
    mutation_budget: int = 10
    taint_fields: list[str] = Field(default_factory=lambda: ["billing_email", "tax_id"])
    replay_count: int = 1
    timeout_seconds: int = 15
    rate_limit_per_minute: int = 60
    safety_mode: bool = True


class CapturedExchange(BaseModel):
    run_id: str
    phase: str
    method: str
    path: str
    status_code: int
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: dict[str, Any] | list[Any] | str | None = None
    response_body: dict[str, Any] | list[Any] | str | None = None
    extracted_fields: list[str] = Field(default_factory=list)
    contains_sensitive_marker: bool = False
    timestamp_ms: int | None = None


class Finding(BaseModel):
    severity: Severity
    category: FindingCategory
    endpoint: str
    title: str
    evidence: str
    expected_behavior: str
    observed_behavior: str
    confidence: float = 1.0
    remediation_note: str


class ComplianceFinding(BaseModel):
    standard: ComplianceStandard
    control_id: str
    control_name: str
    status: ComplianceStatus
    detail: str
    remediation: str = ""


class ComplianceReport(BaseModel):
    run_id: str
    standard: ComplianceStandard
    overall_status: ComplianceStatus
    findings: list[ComplianceFinding]
    passed: int
    failed: int
    warned: int


class PluginResult(BaseModel):
    plugin_name: str
    findings: list[Finding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunReport(BaseModel):
    run_id: str
    target_name: str
    status: str
    reached_endpoints: list[str]
    hidden_endpoints: list[str]
    sensitive_fields_accessed: list[str]
    divergence_summary: list[str]
    risk_score: int
    findings: list[Finding]
    compliance_reports: list[ComplianceReport] = Field(default_factory=list)
    plugin_results: list[PluginResult] = Field(default_factory=list)


class RunRecord(BaseModel):
    run_id: str
    status: str
    target: TargetConfig
    config: TestRunConfig
    findings: list[Finding] = Field(default_factory=list)
    exchanges: list[CapturedExchange] = Field(default_factory=list)
    report: RunReport | None = None
