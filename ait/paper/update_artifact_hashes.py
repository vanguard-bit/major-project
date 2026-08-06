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
    "reproducibility",
    "tool_comparison",
)
LIVE_KEYS = (
    "github_readonly",
    "github_smoke",
    "notion_readonly",
    "google_readonly",
    "google_smoke",
)

# Default paths filled when a key is null but the offline gate produced the file.
DEFAULT_PATHS = {
    "offline_manifest": "results/derived/offline_manifest.json",
    "scenario_metrics": "results/derived/scenario_metrics.json",
    "sensitivity_summary": "results/derived/sensitivity_summary.json",
    "sensitivity_rows": "results/raw/sensitivity/sensitivity_rows.json",
    "replay_match_table": "results/derived/replay_match_table.json",
    "benchmark_summary": "results/derived/benchmark_summary.json",
    "robustness_metrics": "results/derived/robustness_metrics.json",
    "reproducibility": "results/derived/reproducibility.json",
}

REQUIRED_RELEASE_KEYS = (
    "offline_manifest",
    "scenario_metrics",
    "sensitivity_summary",
    "sensitivity_rows",
    "replay_match_table",
    "benchmark_summary",
    "robustness_metrics",
    "reproducibility",
)


def _update_ref(node: object, root: Path, *, default_path: str | None = None) -> object:
    if node is None:
        if default_path is None:
            return None
        full = root / default_path
        if not full.is_file():
            return None
        return {"path": default_path, "sha256": sha256_file(full)}
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
    require_release_artifacts: bool = True,
) -> dict:
    path = Path(manifest_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("paper_artifacts.yaml must be a mapping")
    for key in ARTIFACT_KEYS:
        if key in data or key in DEFAULT_PATHS:
            data[key] = _update_ref(
                data.get(key),
                root,
                default_path=DEFAULT_PATHS.get(key),
            )
    live = data.get("live_runs")
    if isinstance(live, dict):
        for key in LIVE_KEYS:
            if key in live:
                live[key] = _update_ref(live[key], root)
        data["live_runs"] = live
    if require_release_artifacts:
        missing = [k for k in REQUIRED_RELEASE_KEYS if not data.get(k)]
        if missing:
            raise FileNotFoundError(
                "release artifacts missing (run offline Phase 5 gate first): "
                + ", ".join(missing)
            )
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return data


@app.command()
def main(
    manifest: Path = typer.Option(Path("configs/paper_artifacts.yaml"), "--manifest"),
    root: Path = typer.Option(Path("."), "--root"),
    require_release: bool = typer.Option(
        True,
        "--require-release/--allow-partial",
        help="Fail if robustness/reproducibility (and other release) artifacts are missing",
    ),
) -> None:
    data = update_paper_artifacts_yaml(
        manifest, root=root, require_release_artifacts=require_release
    )
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
