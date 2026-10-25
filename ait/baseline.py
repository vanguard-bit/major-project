"""Simple two-part comparison baseline: endpoint allowlist + exact canary search.

Deliberately independent of ``ait.analysis``: it shares only ``normalize_path``
(query-parameter sorting). Semantics are frozen in
docs/research-sprint/EXPERIMENT_PROTOCOL.md §5.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from pydantic import BaseModel, Field

from ait.experiments.scenario_loader import normalize_path
from ait.models import CapturedExchange

MIN_CANARY_LENGTH = 8


class CanaryHit(BaseModel):
    canary_index: int
    endpoint: str
    phase: str
    location: str  # request_path | request_body | response_body


class BaselineResult(BaseModel):
    unexpected_endpoints: list[str] = Field(default_factory=list)
    ambiguous_endpoints: list[str] = Field(default_factory=list)
    unparseable_endpoints: list[str] = Field(default_factory=list)
    canary_hits: list[CanaryHit] = Field(default_factory=list)

    @property
    def categories(self) -> set[str]:
        out: set[str] = set()
        if self.unexpected_endpoints:
            out.add("hidden_endpoint")
        if self.canary_hits:
            out.add("sensitive_field_access")
        return out


def classify_endpoint(path: str, allowed: set[str]) -> str:
    if not path.startswith("/"):
        return "unparseable"
    normalized = normalize_path(path)
    if normalized in allowed:
        return "allowed"
    base = normalized.partition("?")[0]
    if any(entry.partition("?")[0] == base for entry in allowed):
        return "ambiguous"
    return "unexpected"


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def validate_canaries(canaries: Iterable[str]) -> list[str]:
    out = list(canaries)
    for canary in out:
        if len(canary) < MIN_CANARY_LENGTH:
            raise ValueError(f"canaries must be at least {MIN_CANARY_LENGTH} characters")
    return out


def find_canaries(canaries: list[str], exchanges: Iterable[CapturedExchange]) -> list[CanaryHit]:
    hits: list[CanaryHit] = []
    for exchange in exchanges:
        locations = {
            "request_path": [exchange.path],
            "request_body": list(_strings(exchange.request_body)),
            "response_body": list(_strings(exchange.response_body)),
        }
        for index, canary in enumerate(canaries):
            for location, values in locations.items():
                if any(canary in value for value in values):
                    hits.append(
                        CanaryHit(
                            canary_index=index,
                            endpoint=exchange.path,
                            phase=exchange.phase,
                            location=location,
                        )
                    )
    return hits


def run_baseline(
    expected_endpoints: Iterable[str],
    canaries: Iterable[str],
    exchanges: list[CapturedExchange],
) -> BaselineResult:
    allowed = {normalize_path(path) for path in expected_endpoints}
    buckets: dict[str, set[str]] = {"unexpected": set(), "ambiguous": set(), "unparseable": set()}
    for exchange in exchanges:
        status = classify_endpoint(exchange.path, allowed)
        if status in buckets:
            buckets[status].add(exchange.path)
    return BaselineResult(
        unexpected_endpoints=sorted(buckets["unexpected"]),
        ambiguous_endpoints=sorted(buckets["ambiguous"]),
        unparseable_endpoints=sorted(buckets["unparseable"]),
        canary_hits=find_canaries(validate_canaries(canaries), exchanges),
    )
