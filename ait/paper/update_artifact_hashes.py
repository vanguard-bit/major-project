"""Refresh SHA-256 digests in configs/paper_artifacts.yaml from on-disk files."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from ait.paper.models import sha256_file

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)

ARTIFACT_KEYS = (
    "offline_manifest",
    "scenario_metrics",
    "sensitivity_summary",
    "sensitivity_rows",
    "replay_match_table",
    "benchmark_summary",
    "robustness_metrics",
    "tool_comparison",
)
LIVE_KEYS = ("github_readonly", "github_smoke", "notion_readonly")


def _update_ref(node: object, root: Path) -> object:
    if node is None:
        return None
    if not isinstance(node, dict) or "path" not in node:
        return node
    path = Path(str(node["path"]))
    full = path if path.is_absolute() else root / path
    if not full.is_file():
        raise FileNotFoundError(f"cannot hash missing file: {full}")
    return {"path": node["path"], "sha256": sha256_file(full)}


def update_paper_artifacts_yaml(
    manifest_path: Path,
    *,
    root: Path,
) -> dict:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("paper_artifacts.yaml must be a mapping")
    for key in ARTIFACT_KEYS:
        if key in data:
            data[key] = _update_ref(data[key], root)
    live = data.get("live_runs")
    if isinstance(live, dict):
        for key in LIVE_KEYS:
            if key in live:
                live[key] = _update_ref(live[key], root)
        data["live_runs"] = live
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return data


@app.command()
def main(
    manifest: Path = typer.Option(Path("configs/paper_artifacts.yaml"), "--manifest"),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    data = update_paper_artifacts_yaml(manifest, root=root)
    for key in ARTIFACT_KEYS:
        ref = data.get(key)
        if ref is None:
            typer.echo(f"{key}: null")
        elif isinstance(ref, dict):
            typer.echo(f"{key}: {ref['sha256'][:12]}… ({ref['path']})")
    live = data.get("live_runs") or {}
    for key in LIVE_KEYS:
        ref = live.get(key)
        if ref is None:
            typer.echo(f"live_runs.{key}: null")
        elif isinstance(ref, dict):
            typer.echo(f"live_runs.{key}: {ref['sha256'][:12]}… ({ref['path']})")
    typer.echo(f"Updated {manifest}")


if __name__ == "__main__":
    app()
