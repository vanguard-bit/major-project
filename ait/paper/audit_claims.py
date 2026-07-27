"""Audit empirical paper claims against the selected artifact manifest."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import typer

from ait.paper.models import (
    load_claims_registry,
    load_paper_artifacts_manifest,
    resolve_json_pointer,
)

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

CLAIM_MARKER = re.compile(r"%\s*CLAIM:([A-Za-z0-9_.:-]+)")


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

    # Collect CLAIM markers across documents referenced by claims + common papers
    docs_to_scan = {"main.tex", "report.tex"}
    for claim in registry.claims:
        docs_to_scan.update(claim.documents)

    markers_by_doc: dict[str, set[str]] = {}
    for doc in sorted(docs_to_scan):
        path = repo_root / doc
        if not path.is_file():
            continue
        markers_by_doc[doc] = _markers(path.read_text(encoding="utf-8"))

    for doc, markers in markers_by_doc.items():
        for marker in sorted(markers):
            if marker not in known_ids:
                errors.append(
                    f"{doc}: claim marker % CLAIM:{marker} is not registered in claims.yaml"
                )

    for claim in registry.claims:
        # Pattern must appear in each declared document when the claim is marked
        # or when required.
        for doc in claim.documents:
            path = repo_root / doc
            if not path.is_file():
                errors.append(f"{claim.id}: document missing: {doc}")
                continue
            text = path.read_text(encoding="utf-8")
            marked = claim.id in markers_by_doc.get(doc, set())
            pattern_hit = re.search(claim.text_pattern, text, flags=re.IGNORECASE | re.DOTALL)
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
