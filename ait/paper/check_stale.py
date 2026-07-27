"""Detect stale experiment inputs relative to the offline manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import typer

from ait.paper.models import load_paper_artifacts_manifest, sha256_file

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

INPUT_GLOBS = (
    "configs/scenarios/**/*.yaml",
    "configs/incidents/**/*.yaml",
    "configs/incidents/SOURCES.md",
    "configs/evaluation_protocol.yaml",
    "ait/analysis.py",
    "ait/experiments/*.py",
)


@dataclass
class StaleResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def collect_input_hashes(repo_root: Path) -> dict[str, str]:
    root = Path(repo_root)
    paths: set[Path] = set()
    for pattern in INPUT_GLOBS:
        if "*" in pattern or "?" in pattern:
            paths.update(root.glob(pattern))
        else:
            candidate = root / pattern
            if candidate.is_file():
                paths.add(candidate)
    hashes: dict[str, str] = {}
    for path in sorted(paths):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        hashes[rel] = sha256_file(path)
    return hashes


def check_stale(
    *,
    repo_root: Path,
    manifest_path: Path,
) -> StaleResult:
    errors: list[str] = []
    repo_root = Path(repo_root)
    manifest = load_paper_artifacts_manifest(manifest_path, root=repo_root, verify=True)
    offline_ref = manifest.offline_manifest
    if offline_ref is None:
        errors.append("offline_manifest is null; cannot check staleness")
        return StaleResult(ok=False, errors=errors)

    offline_path = Path(offline_ref.path)
    if not offline_path.is_absolute():
        offline_path = repo_root / offline_path
    offline = json.loads(offline_path.read_text(encoding="utf-8"))
    recorded_inputs = offline.get("payload", {}).get("input_hashes")
    if not isinstance(recorded_inputs, dict) or not recorded_inputs:
        errors.append("offline_manifest.payload.input_hashes missing or empty")
        return StaleResult(ok=False, errors=errors)

    current_inputs = collect_input_hashes(repo_root)
    for rel, expected in sorted(recorded_inputs.items()):
        actual = current_inputs.get(rel)
        if actual is None:
            errors.append(f"stale: recorded input missing: {rel}")
        elif actual != expected:
            errors.append(f"stale: input hash mismatch for {rel}")

    # Extra files present now but not recorded are treated as stale inputs.
    for rel in sorted(set(current_inputs) - set(recorded_inputs)):
        errors.append(f"stale: new input not recorded in offline_manifest: {rel}")

    # Selected raw/derived artifacts listed in offline manifest must still match.
    for entry in offline.get("payload", {}).get("artifacts", []):
        rel = entry["path"]
        expected = entry["sha256"]
        # Paths in offline manifest are relative to results/
        path = repo_root / "results" / rel
        if not path.is_file():
            errors.append(f"stale: artifact missing: results/{rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(f"stale: artifact hash mismatch for results/{rel}")

    return StaleResult(ok=not errors, errors=errors)


@app.command()
def main(
    manifest: Path = typer.Option(Path("configs/paper_artifacts.yaml"), "--manifest"),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    result = check_stale(repo_root=root, manifest_path=manifest)
    for error in result.errors:
        typer.echo(f"ERROR {error}", err=True)
    if result.ok:
        typer.echo("Staleness check passed")
        raise typer.Exit(0)
    typer.echo("Staleness check failed", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
