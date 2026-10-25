"""Sanitize an observed third-party integration trace and evaluate it against a declared policy.

Input: a HAR file (e.g. mitmproxy ``--set hardump=...``) or JSON lines with
``method``, ``url`` and optional ``ts``/``status``/``request_body``/``response_body``.
Output keeps only method, host, path (policy template when matched), query
parameter *names*, status, outcome and canary-hit locations. Headers, bodies,
query values and canary values are never written. See
docs/research-sprint/REAL_INTEGRATION_STUDY.md.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import typer
import yaml
from pydantic import BaseModel, ConfigDict, Field

from ait.analysis import analyze_run, extract_field_paths
from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.baseline import find_canaries, run_baseline, validate_canaries
from ait.models import CapturedExchange, TargetConfig

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

SECRET_PATTERNS = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|xox[abpr]-[\w-]{10,}|ntn_\w{20,}"
    r"|secret_\w{20,}|ya29\.[\w-]+|AKIA[0-9A-Z]{16}|-----BEGIN|Bearer\s+\S"
    r"|eyJ[\w-]{10,}\.[\w-]{10,}",
)


class IntegrationIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    repository: str
    commit: str
    license: str
    authored_by_team: bool = False


class IntegrationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integration: IntegrationIdentity
    allowed_hosts: list[str]
    ignore_hosts: list[str] = Field(default_factory=list)
    expected_endpoints: list[str]  # "[METHOD ]/path/{param}/{rest*}"
    denied_endpoints: list[str] = Field(default_factory=list)
    sensitive_markers: list[str] = Field(default_factory=list)
    canaries: list[str] = Field(default_factory=list)


def _compile(entry: str) -> tuple[str | None, str, re.Pattern[str]]:
    method, _, path = entry.strip().rpartition(" ")
    regex = re.escape(path)
    regex = re.sub(r"\\\{\w+\\\*\\\}", ".+", regex)
    regex = re.sub(r"\\\{\w+\\\}", "[^/]+", regex)
    return (method.upper() or None), path, re.compile(f"^{regex}$")


def _match(entries: list[str], method: str, path: str) -> str | None:
    for entry in entries:
        want_method, template, pattern = _compile(entry)
        if (want_method is None or want_method == method) and pattern.match(path):
            return template
    return None


def _maybe_json(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def load_records(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix.lower() == ".har":
        entries = json.loads(path.read_text(encoding="utf-8"))["log"]["entries"]
        records = []
        for entry in entries:
            request, response = entry.get("request", {}), entry.get("response", {})
            content = response.get("content") or {}
            body = content.get("text")
            if body and content.get("encoding") == "base64":
                body = base64.b64decode(body).decode("utf-8", errors="replace")
            records.append(
                {
                    "ts": entry.get("startedDateTime"),
                    "method": request.get("method"),
                    "url": request.get("url"),
                    "status": response.get("status") or None,
                    "request_body": _maybe_json((request.get("postData") or {}).get("text")),
                    "response_body": _maybe_json(body),
                }
            )
        return records
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _rel_ms(ts: Any, t0: datetime | None) -> float | None:
    if not isinstance(ts, str) or t0 is None:
        return None
    try:
        return (datetime.fromisoformat(ts.replace("Z", "+00:00")) - t0).total_seconds() * 1000
    except ValueError:
        return None


def evaluate(
    policy: IntegrationPolicy,
    phases: dict[str, list[dict[str, Any]]],
    workflow_id: str,
    source: str,
) -> dict[str, Any]:
    canaries = validate_canaries(policy.canaries)
    allowed_hosts = {h.lower() for h in policy.allowed_hosts}
    ignore_hosts = {h.lower() for h in policy.ignore_hosts}
    expected_keys = sorted({_compile(e)[1] for e in policy.expected_endpoints})
    entries: list[dict[str, Any]] = []
    exchanges: list[CapturedExchange] = []
    first_ts = next(
        (r.get("ts") for records in phases.values() for r in records if r.get("ts")), None
    )
    try:
        t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00")) if first_ts else None
    except ValueError:
        t0 = None

    for phase, records in phases.items():
        for record in records:
            method = str(record.get("method") or "").upper()
            parts = urlsplit(str(record.get("url") or ""))
            host, path = (parts.hostname or "").lower(), parts.path or ""
            query = parse_qsl(parts.query, keep_blank_values=True)
            entry: dict[str, Any] = {
                "index": len(entries),
                "phase": phase,
                "t_rel_ms": _rel_ms(record.get("ts"), t0),
                "method": method,
                "host": host,
                "query_param_names": sorted({k for k, _ in query}),
                "status": record.get("status"),
                "workflow_id": workflow_id,
                "source": source,
            }
            if not method or not host or not path.startswith("/"):
                entries.append(
                    {**entry, "endpoint": None, "endpoint_status": "unparseable",
                     "outcome": "incomplete_observation", "canary_hits": []}
                )
                continue
            on_allowed_host = host in allowed_hosts
            denied = on_allowed_host and _match(policy.denied_endpoints, method, path)
            allowed = on_allowed_host and _match(policy.expected_endpoints, method, path)
            if host in ignore_hosts:
                status, key = "ignored_host", f"//{host}"
            elif host not in allowed_hosts:
                status, key = "undeclared_host", f"//{host}{path}"
            elif denied:
                status, key = "denied", denied
            elif allowed:
                status, key = "allowed", allowed
            else:
                status, key = "undeclared_endpoint", path
            raw = CapturedExchange(
                run_id=workflow_id,
                phase=phase,
                method=method,
                path=key + ("?" + parts.query if parts.query else ""),
                status_code=int(record.get("status") or 0),
                request_body=record.get("request_body"),
                response_body=record.get("response_body"),
            )
            hits = [
                {"canary_index": h.canary_index, "location": h.location}
                for h in find_canaries(canaries, [raw])
            ]
            outbound_canary = any(h["location"] != "response_body" for h in hits)
            if status == "ignored_host":
                outcome = "out_of_scope"
            elif status == "denied" or (outbound_canary and status != "allowed"):
                outcome = "confirmed_policy_violation"
            elif status == "allowed":
                outcome = "permitted_behavior"
            else:
                outcome = "uncertain_policy"
            entries.append(
                {**entry, "endpoint": key, "endpoint_status": status, "outcome": outcome,
                 "canary_hits": hits}
            )
            if status != "ignored_host":
                exchanges.append(
                    raw.model_copy(
                        update={
                            "path": key,
                            "extracted_fields": sorted(extract_field_paths(raw.response_body)),
                        }
                    )
                )

    target = TargetConfig.model_validate(
        {
            "name": policy.integration.name,
            "base_url": "http://observed.invalid/",
            "integration_sync_url": "http://observed.invalid/sync",
            "audit_base_url": "http://observed.invalid/",
            "expected_endpoints": expected_keys,
            "sensitive_markers": policy.sensitive_markers,
        }
    )
    report = analyze_run(workflow_id, target, exchanges)
    baseline = run_baseline(expected_keys, canaries, exchanges)
    n = len(entries) or 1
    outcomes: dict[str, int] = {}
    for item in entries:
        outcomes[item["outcome"]] = outcomes.get(item["outcome"], 0) + 1
    return {
        "evidence_kind": "integration_behavior",
        "coverage": {
            "requests": len(entries),
            "with_status": sum(e["status"] is not None for e in entries) / n,
            "with_request_body": sum(r.get("request_body") is not None
                                     for rs in phases.values() for r in rs) / n,
            "with_response_body": sum(r.get("response_body") is not None
                                      for rs in phases.values() for r in rs) / n,
            "phases": sorted(phases),
            "not_observed": [
                "request/response headers (dropped)",
                "query values (dropped)",
                "traffic outside the capture point",
            ],
        },
        "outcome_counts": dict(sorted(outcomes.items())),
        "entries": entries,
        "ait": {
            "categories": sorted({f.category.value for f in report.findings}),
            "hidden_endpoints": report.hidden_endpoints,
            "divergence_summary": report.divergence_summary,
            "risk_score": report.risk_score,
        },
        "baseline": {
            "categories": sorted(baseline.categories),
            "unexpected_endpoints": baseline.unexpected_endpoints,
            "canary_hit_count": len(baseline.canary_hits),
        },
    }


def assert_sanitized(payload: dict[str, Any], canaries: list[str]) -> None:
    text = json.dumps(payload)
    if SECRET_PATTERNS.search(text):
        raise ValueError("refusing to write: secret-like pattern in sanitized trace")
    if any(canary in text for canary in canaries):
        raise ValueError("refusing to write: canary value in sanitized trace")


@app.command()
def main(
    policy: Path = typer.Option(..., "--policy"),
    baseline: Path = typer.Option(..., "--baseline", help="Trace for the baseline workflow"),
    mutated: Path | None = typer.Option(None, "--mutated", help="Optional state-varied trace"),
    workflow_id: str = typer.Option(..., "--workflow-id"),
    source: str = typer.Option(..., "--source", help="e.g. 'mitmproxy hardump'"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    spec = IntegrationPolicy.model_validate(yaml.safe_load(policy.read_text(encoding="utf-8")))
    if spec.integration.authored_by_team:
        typer.echo("NOTE: team-authored integration; report it as a reference integration.")
    phases = {"baseline": load_records(baseline)}
    if mutated is not None:
        phases["mutated"] = load_records(mutated)
    payload = evaluate(spec, phases, workflow_id, source)
    assert_sanitized(payload, spec.canaries)
    inputs = [baseline] + ([mutated] if mutated else [])
    envelope = ArtifactEnvelope(
        provenance=collect_provenance(
            ["python", "-m", "ait.integration_trace", *sys.argv[1:]]
        ),
        experiment="integration_observation",
        configuration={
            "integration": spec.integration.model_dump(),
            "policy_path": policy.as_posix(),
            "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
            "raw_trace_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs
            },
            "canary_count": len(spec.canaries),
        },
        payload=payload,
    )
    write_artifact(output, envelope)
    typer.echo(f"outcomes={payload['outcome_counts']} ait={payload['ait']['categories']} "
               f"baseline={payload['baseline']['categories']}")
    typer.echo(f"WROTE {output}")


if __name__ == "__main__":
    app()
