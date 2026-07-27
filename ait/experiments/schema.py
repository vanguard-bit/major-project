from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from ait.models import (
    AuthType,
    CapturedExchange,
    Finding,
    FindingCategory,
    RunReport,
    TargetConfig,
)


class ScenarioTokenConfig(BaseModel):
    """Strict token config for scenario YAML (unknown keys rejected)."""

    model_config = ConfigDict(extra="forbid")

    token: str | None = None
    token_url: HttpUrl | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None


class ScenarioTargetConfig(BaseModel):
    """Strict target config for scenario YAML without relaxing live TargetConfig."""

    model_config = ConfigDict(extra="forbid")

    name: str
    environment: str = "demo"
    base_url: HttpUrl
    integration_sync_url: HttpUrl
    audit_base_url: HttpUrl
    auth_type: AuthType = AuthType.STATIC_TOKEN
    token_config: ScenarioTokenConfig = Field(default_factory=ScenarioTokenConfig)
    openapi_paths: list[str] = Field(default_factory=list)
    seed_endpoints: list[str] = Field(default_factory=list)
    expected_endpoints: list[str] = Field(default_factory=list)
    expected_scopes: list[str] = Field(default_factory=list)
    sensitive_markers: list[str] = Field(default_factory=list)
    description: str = ""

    def to_target_config(self) -> TargetConfig:
        return TargetConfig.model_validate(self.model_dump(mode="python"))


class ExchangeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["baseline", "mutated"]
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    status_code: int = 200
    request_body: dict[str, Any] | list[Any] | str | None = None
    response_body: dict[str, Any] | list[Any] | str | None = None

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("path must start with '/'")
        return value


class ExpectedLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FindingCategory
    endpoint: str | None = None


def labels_exact_match(
    expected_labels: Sequence[ExpectedLabel],
    findings: Sequence[Finding],
) -> bool:
    """Match expected labels to findings with optional endpoint qualification.

    When a label supplies an endpoint, a finding with the same category and
    endpoint must exist. Labels without an endpoint match by category only.
    Overall category sets must still be equal (no missing or extra categories).
    """
    for label in expected_labels:
        if label.endpoint is not None:
            if not any(
                finding.category == label.category and finding.endpoint == label.endpoint
                for finding in findings
            ):
                return False
        elif not any(finding.category == label.category for finding in findings):
            return False
    expected_categories = {label.category for label in expected_labels}
    observed_categories = {finding.category for finding in findings}
    return expected_categories == observed_categories


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"]
    id: str
    suite: Literal["crm", "platform"]
    platform_style: str
    description: str
    target: ScenarioTargetConfig
    exchanges: list[ExchangeSpec] = Field(min_length=1)
    expected_labels: list[ExpectedLabel]

    @model_validator(mode="after")
    def reject_duplicate_exchanges(self) -> ScenarioDefinition:
        seen: set[tuple[str, str, str]] = set()
        for exchange in self.exchanges:
            key = (exchange.phase, exchange.method, exchange.path)
            if key in seen:
                raise ValueError(
                    f"duplicate exchange record: {exchange.phase} {exchange.method} {exchange.path}"
                )
            seen.add(key)
        return self


class ScenarioOutcome(BaseModel):
    scenario_id: str
    expected_categories: set[FindingCategory]
    observed_categories: set[FindingCategory]
    report: RunReport
    exchanges: list[CapturedExchange] = Field(default_factory=list)
    expected_labels: list[ExpectedLabel] = Field(default_factory=list)
    target: ScenarioTargetConfig | None = None
