from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import typer
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ait.analysis import analyze_run, extract_field_paths, field_matches_sensitive_marker
from ait.artifacts import ArtifactEnvelope, collect_provenance, write_artifact
from ait.experiments.schema import ExchangeSpec, ExpectedLabel
from ait.models import CapturedExchange, FindingCategory, RunReport, TargetConfig

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


class IncidentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"]
    id: str
    incident_name: str
    reconstruction: Literal[True]
    source_urls: list[str] = Field(min_length=1)
    source_accessed_utc: datetime
    documented_behavior: list[str] = Field(min_length=1)
    mapping_assumptions: list[str] = Field(min_length=1)
    target: TargetConfig
    exchanges: list[ExchangeSpec] = Field(min_length=1)
    expected_labels: list[ExpectedLabel]

    @field_validator("source_accessed_utc")
    @classmethod
    def require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("source_accessed_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_reconstruction(self) -> IncidentDefinition:
        if self.reconstruction is not True:
            raise ValueError("reconstruction must be true for incident fixtures")
        return self


class ReplayOutcome(BaseModel):
    incident_id: str
    reconstruction: Literal[True]
    expected_categories: set[FindingCategory]
    observed_categories: set[FindingCategory]
    exact_match: bool
    report: RunReport


def load_incident(path: Path) -> IncidentDefinition:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"incident root must be a mapping: {path}")
    if raw.get("reconstruction") is not True:
        raise ValueError(f"reconstruction must be true: {path}")
    return IncidentDefinition.model_validate(raw)


def _exchanges_to_captured(incident: IncidentDefinition) -> list[CapturedExchange]:
    markers = set(incident.target.sensitive_markers)
    captured: list[CapturedExchange] = []
    for spec in incident.exchanges:
        extracted = sorted(extract_field_paths(spec.response_body))
        contains_sensitive = any(
            field_matches_sensitive_marker(field, markers) for field in extracted
        )
        captured.append(
            CapturedExchange(
                run_id=incident.id,
                phase=spec.phase,
                method=spec.method,
                path=spec.path,
                status_code=spec.status_code,
                request_headers={},
                request_body=spec.request_body,
                response_body=spec.response_body,
                extracted_fields=extracted,
                contains_sensitive_marker=contains_sensitive,
            )
        )
    return captured


def run_replay(path: Path) -> ReplayOutcome:
    incident = load_incident(path)
    exchanges = _exchanges_to_captured(incident)
    report = analyze_run(incident.id, incident.target, exchanges)
    expected = {label.category for label in incident.expected_labels}
    observed = {finding.category for finding in report.findings}
    return ReplayOutcome(
        incident_id=incident.id,
        reconstruction=True,
        expected_categories=expected,
        observed_categories=observed,
        exact_match=expected == observed,
        report=report,
    )


def discover_incident_paths(root: Path) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.yaml") if p.is_file())


def run_replay_pipeline(
    incident_root: Path,
    output_root: Path,
    command: list[str],
) -> list[ReplayOutcome]:
    outcomes: list[ReplayOutcome] = []
    raw_dir = output_root / "raw" / "replay"
    match_rows: list[dict[str, Any]] = []
    for path in discover_incident_paths(incident_root):
        outcome = run_replay(path)
        outcomes.append(outcome)
        status = "PASS" if outcome.exact_match else "FAIL"
        typer.echo(
            f"{status} {outcome.incident_id} "
            f"expected={sorted(c.value for c in outcome.expected_categories)} "
            f"observed={sorted(c.value for c in outcome.observed_categories)}"
        )
        envelope = ArtifactEnvelope(
            provenance=collect_provenance(command),
            experiment="incident_replay",
            configuration={
                "incident_id": outcome.incident_id,
                "source_path": str(path),
                "reconstruction": True,
            },
            payload={
                "incident_id": outcome.incident_id,
                "reconstruction": True,
                "exact_match": outcome.exact_match,
                "expected_categories": sorted(c.value for c in outcome.expected_categories),
                "observed_categories": sorted(c.value for c in outcome.observed_categories),
                "report": outcome.report.model_dump(mode="json"),
            },
        )
        write_artifact(raw_dir / f"{outcome.incident_id}.json", envelope)
        match_rows.append(
            {
                "incident_id": outcome.incident_id,
                "exact_match": outcome.exact_match,
                "expected_categories": sorted(c.value for c in outcome.expected_categories),
                "observed_categories": sorted(c.value for c in outcome.observed_categories),
            }
        )

    derived = ArtifactEnvelope(
        provenance=collect_provenance(command),
        experiment="replay_match_table",
        configuration={"incident_count": len(outcomes)},
        payload={"matches": match_rows},
    )
    write_artifact(output_root / "derived" / "replay_match_table.json", derived)
    return outcomes


@app.command()
def main(
    incident_root: Path = typer.Option(
        Path("configs/incidents"),
        "--incident-root",
        help="Directory containing reconstructed incident YAML fixtures",
    ),
    output_root: Path = typer.Option(
        Path("results"),
        "--output-root",
        help="Root directory for raw and derived artifacts",
    ),
) -> None:
    command = ["python", "-m", "ait.experiments.replay_incidents", *sys.argv[1:]]
    outcomes = run_replay_pipeline(incident_root, output_root, command)
    failures = sum(1 for o in outcomes if not o.exact_match)
    typer.echo(f"Replay: {len(outcomes)} PASS={len(outcomes) - failures} FAIL={failures}")
    raise typer.Exit(1 if failures else 0)


if __name__ == "__main__":
    app()
