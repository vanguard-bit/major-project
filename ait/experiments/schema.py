from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ait.models import FindingCategory, RunReport, TargetConfig


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


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"]
    id: str
    suite: Literal["crm", "platform"]
    platform_style: str
    description: str
    target: TargetConfig
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
