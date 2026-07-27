"""Audit empirical paper claims against the selected artifact manifest."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import typer

from ait.paper.models import (
    ClaimsRegistry,
    load_claims_registry,
    load_paper_artifacts_manifest,
    resolve_json_pointer,
)

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

CLAIM_MARKER = re.compile(r"%\s*CLAIM:([A-Za-z0-9_.:-]+)")

# Unmarked phrases that always require a CLAIM marker or protocol_constant/example registry entry.
BANNED_UNMARKED = (
    (re.compile(r"under\s+200\s*(?:\\,)?\s*ms", re.IGNORECASE), "under 200 ms timing"),
    (re.compile(r"CVSS[- ]calibrated", re.IGNORECASE), "CVSS-calibrated"),
    (re.compile(r"real[- ]data", re.IGNORECASE), "real-data"),
    (re.compile(r"\bDM4\b"), "DM4"),
    (re.compile(r"POLICY\\?_VIOLATION|POLICY_VIOLATION", re.IGNORECASE), "POLICY_VIOLATION"),
    (
        re.compile(
            r"(?:\+30|\$\+30\$).{0,40}risk|risk.{0,40}(?:\+30|\$\+30\$)",
            re.IGNORECASE,
        ),
        "+30 risk",
    ),
)

# Numeric empirical shapes. Allowed only with CLAIM marker or
# protocol_constant/example registry coverage.
NUMERIC_EMPIRICAL = (
    re.compile(
        r"(?<![A-Za-z])(?:F1|precision|recall)\s*(?:=|:|of|is)?\s*0?\.\d{2,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:completes?|finished|latency|took|runs?)\s+(?:in\s+)?(?:under\s+)?"
        r"\d{2,4}\s*(?:\\,)?\s*ms",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brisk\s+score\s+(?:of\s+)?\d+(?:\.\d+)?\b",
        re.IGNORECASE,
    ),
)


@dataclass
class AuditResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _document_text(repo_root: Path, relative: str) -> str:
    path = repo_root / relative
    if not path.is_file():
        raise FileNotFoundError(f"document missing: {relative}")
    return path.read_text(encoding="utf-8")


def _markers(text: str) -> set[str]:
    return set(CLAIM_MARKER.findall(text))


def _line_has_claim_marker(line: str) -> bool:
    return bool(CLAIM_MARKER.search(line))


def _allowed_by_protocol_or_example(registry: ClaimsRegistry, snippet: str) -> bool:
    for claim in registry.claims:
        if claim.kind not in {"protocol_constant", "example"}:
            continue
        if re.search(claim.text_pattern, snippet, flags=re.IGNORECASE | re.DOTALL):
            return True
    return False


def _scan_unmarked_empirical(
    *,
    doc: str,
    text: str,
    registry: ClaimsRegistry,
) -> list[str]:
    """Reject unmarked measured-looking assertions."""
    errors: list[str] = []
    lines = text.splitlines()
    recent_markers: list[str] = []
    for index, line in enumerate(lines, start=1):
        if _line_has_claim_marker(line):
            recent_markers = CLAIM_MARKER.findall(line)
            continue
        if not line.strip():
            recent_markers = []

        design_exempt = bool(
            re.search(
                r"\b(?:future work|out of scope|not (?:measured|claimed|implemented)|"
                r"design (?:constant|choice)|heuristic|example sequence|"
                r"not yet implemented)\b",
                line,
                re.IGNORECASE,
            )
        )

        for pattern, label in BANNED_UNMARKED:
            if pattern.search(line):
                if recent_markers or design_exempt:
                    continue
                if _allowed_by_protocol_or_example(registry, line):
                    continue
                errors.append(
                    f"{doc}:{index}: unmarked empirical assertion ({label}): "
                    f"{line.strip()[:120]}"
                )

        for pattern in NUMERIC_EMPIRICAL:
            if not pattern.search(line):
                continue
            if recent_markers or design_exempt:
                continue
            if _allowed_by_protocol_or_example(registry, line):
                continue
            if r"\input{" in line or "results/generated/" in line:
                continue
            errors.append(
                f"{doc}:{index}: unmarked numeric empirical assertion: "
                f"{line.strip()[:120]}"
            )
    return errors


def audit_claims(
    *,
    claims_path: Path,
    manifest_path: Path,
    repo_root: Path,
) -> AuditResult:
    errors: list[str] = []
    warnings: list[str] = []
    registry = load_claims_registry(claims_path)
    manifest = load_paper_artifacts_manifest(manifest_path, root=repo_root, verify=True)
    known_ids = {claim.id for claim in registry.claims}

    docs_to_scan = {"main.tex", "report.tex"}
    for claim in registry.claims:
        docs_to_scan.update(claim.documents)

    markers_by_doc: dict[str, set[str]] = {}
    texts_by_doc: dict[str, str] = {}
    for doc in sorted(docs_to_scan):
        path = repo_root / doc
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        texts_by_doc[doc] = text
        markers_by_doc[doc] = _markers(text)

    for doc, markers in markers_by_doc.items():
        for marker in sorted(markers):
            if marker not in known_ids:
                errors.append(
                    f"{doc}: claim marker % CLAIM:{marker} is not registered in claims.yaml"
                )

    for doc, text in texts_by_doc.items():
        errors.extend(
            _scan_unmarked_empirical(doc=doc, text=text, registry=registry)
        )

    for claim in registry.claims:
        for doc in claim.documents:
            path = repo_root / doc
            if not path.is_file():
                errors.append(f"{claim.id}: document missing: {doc}")
                continue
            text = texts_by_doc.get(doc) or path.read_text(encoding="utf-8")
            marked = claim.id in markers_by_doc.get(doc, set())
            pattern_hit = re.search(claim.text_pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if claim.kind in {"protocol_constant", "example"}:
                # Protocol/example entries document allowed unmarked constants; no marker required.
                continue
            if marked and not pattern_hit:
                errors.append(
                    f"{claim.id}: text_pattern did not match in {doc} near CLAIM marker"
                )
            if claim.required and not pattern_hit:
                errors.append(
                    f"{claim.id}: required claim text_pattern not found in {doc}"
                )
            if claim.required and not marked:
                errors.append(
                    f"{claim.id}: required claim lacks % CLAIM:{claim.id} in {doc}"
                )

        if claim.kind in {"protocol_constant", "example"}:
            continue

        ref = manifest.ref_for(claim.evidence.artifact)
        if ref is None:
            if claim.required:
                errors.append(
                    f"{claim.id}: required evidence artifact "
                    f"'{claim.evidence.artifact}' is null/unavailable"
                )
            elif any(claim.id in markers_by_doc.get(d, set()) for d in claim.documents):
                errors.append(
                    f"{claim.id}: claim is marked in a document but artifact "
                    f"'{claim.evidence.artifact}' is null"
                )
            continue

        artifact_path = Path(ref.path)
        if not artifact_path.is_absolute():
            artifact_path = repo_root / artifact_path
        try:
            document = json.loads(artifact_path.read_text(encoding="utf-8"))
            value = resolve_json_pointer(document, claim.evidence.json_pointer)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(
                f"{claim.id}: cannot resolve {claim.evidence.json_pointer} "
                f"in {ref.path}: {exc}"
            )
            continue
        if value is None and claim.required:
            errors.append(
                f"{claim.id}: JSON pointer {claim.evidence.json_pointer} resolved to null"
            )

    return AuditResult(ok=not errors, errors=errors, warnings=warnings)


@app.command()
def main(
    claims: Path = typer.Option(Path("configs/claims.yaml"), "--claims"),
    manifest: Path = typer.Option(Path("configs/paper_artifacts.yaml"), "--manifest"),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    result = audit_claims(claims_path=claims, manifest_path=manifest, repo_root=root)
    for warning in result.warnings:
        typer.echo(f"WARN {warning}", err=True)
    for error in result.errors:
        typer.echo(f"ERROR {error}", err=True)
    if result.ok:
        typer.echo("Claim audit passed")
        raise typer.Exit(0)
    typer.echo("Claim audit failed", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
