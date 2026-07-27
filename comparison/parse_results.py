#!/usr/bin/env python3
"""Parse comparison tool outputs without overclaiming.

Parser fixtures under tests/comparison/fixtures/ are committed minimal native-
output samples for unit tests only. They are NOT experimental runs and must not
be cited as tool-comparison results.

Run selection is explicit: pass --run tool=path (or a YAML/JSON config). This
module never auto-picks the newest directory under results/raw/tool-comparison/.
"""

from __future__ import annotations

import argparse
import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class DetectionStatus(StrEnum):
    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"
    NOT_RUN = "NOT_RUN"


GROUND_TRUTH_COLUMNS = (
    "client_policy_hidden_endpoint",
    "sensitive_field",
    "server_500",
    "openapi_violation",
)
KNOWN_TOOLS = ("ait", "restler", "evomaster")


def _status_from_meta(run_dir: Path) -> DetectionStatus:
    status_path = run_dir / "status.txt"
    if not status_path.exists():
        if not run_dir.exists() or not any(run_dir.iterdir()):
            return DetectionStatus.NOT_RUN
        return DetectionStatus.NOT_RUN
    text = status_path.read_text(encoding="utf-8")
    if "NOT_RUN" in text:
        return DetectionStatus.NOT_RUN
    if "ERROR" in text:
        return DetectionStatus.ERROR
    return DetectionStatus.DETECTED  # placeholder; refined per tool


def parse_ait(run_dir: Path) -> dict[str, str]:
    status_path = run_dir / "status.txt"
    if status_path.exists() and "NOT_RUN" in status_path.read_text(encoding="utf-8"):
        return {col: DetectionStatus.NOT_RUN.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.NOT_RUN.value
        }
    if status_path.exists() and "ERROR" in status_path.read_text(encoding="utf-8"):
        return {col: DetectionStatus.ERROR.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.ERROR.value
        }
    findings_path = run_dir / "findings.json"
    if not findings_path.exists():
        return {col: DetectionStatus.NOT_RUN.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.NOT_RUN.value
        }
    try:
        report = json.loads(findings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {col: DetectionStatus.ERROR.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.ERROR.value
        }
    categories = {
        finding.get("category")
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
    }
    hidden = (
        DetectionStatus.DETECTED
        if "hidden_endpoint" in categories
        else DetectionStatus.NOT_DETECTED
    )
    sensitive = (
        DetectionStatus.DETECTED
        if "sensitive_field_access" in categories
        else DetectionStatus.NOT_DETECTED
    )
    return {
        "client_policy_hidden_endpoint": hidden.value,
        "sensitive_field": sensitive.value,
        # AIT does not target server faults / OpenAPI schema fuzzing.
        "server_500": DetectionStatus.NOT_APPLICABLE.value,
        "openapi_violation": DetectionStatus.NOT_APPLICABLE.value,
        "run_status": DetectionStatus.DETECTED.value
        if findings_path.exists()
        else DetectionStatus.NOT_RUN.value,
    }


def parse_restler(run_dir: Path) -> dict[str, str]:
    status_path = run_dir / "status.txt"
    if not run_dir.exists() or (
        status_path.exists() and "NOT_RUN" in status_path.read_text(encoding="utf-8")
    ):
        return {col: DetectionStatus.NOT_RUN.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.NOT_RUN.value
        }
    if status_path.exists() and "ERROR" in status_path.read_text(encoding="utf-8"):
        return {col: DetectionStatus.ERROR.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.ERROR.value
        }
    # RESTler observes server faults / coverage; client-policy rows are N/A.
    bug_buckets = list(run_dir.rglob("*bug_buckets*")) + list(run_dir.rglob("*.json"))
    text_blobs = []
    for path in bug_buckets:
        if path.is_file() and path.stat().st_size < 1_000_000:
            text_blobs.append(path.read_text(encoding="utf-8", errors="replace"))
    joined = "\n".join(text_blobs).lower()
    server_500 = (
        DetectionStatus.DETECTED
        if ("500" in joined or "internal server error" in joined)
        else DetectionStatus.NOT_DETECTED
    )
    schema = (
        DetectionStatus.DETECTED
        if ("schema" in joined or "response_parser" in joined)
        else DetectionStatus.NOT_DETECTED
    )
    return {
        "client_policy_hidden_endpoint": DetectionStatus.NOT_APPLICABLE.value,
        "sensitive_field": DetectionStatus.NOT_APPLICABLE.value,
        "server_500": server_500.value,
        "openapi_violation": schema.value,
        "run_status": DetectionStatus.DETECTED.value,
    }


def parse_evomaster(run_dir: Path) -> dict[str, str]:
    status_path = run_dir / "status.txt"
    if not run_dir.exists() or (
        status_path.exists() and "NOT_RUN" in status_path.read_text(encoding="utf-8")
    ):
        return {col: DetectionStatus.NOT_RUN.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.NOT_RUN.value
        }
    if status_path.exists() and "ERROR" in status_path.read_text(encoding="utf-8"):
        return {col: DetectionStatus.ERROR.value for col in GROUND_TRUTH_COLUMNS} | {
            "run_status": DetectionStatus.ERROR.value
        }
    stats = list(run_dir.rglob("statistics.csv")) + list(run_dir.rglob("*.log"))
    joined = ""
    for path in stats:
        if path.is_file() and path.stat().st_size < 1_000_000:
            joined += path.read_text(encoding="utf-8", errors="replace").lower()
    server_500 = (
        DetectionStatus.DETECTED
        if ("500" in joined or "faults" in joined)
        else DetectionStatus.NOT_DETECTED
    )
    return {
        "client_policy_hidden_endpoint": DetectionStatus.NOT_APPLICABLE.value,
        "sensitive_field": DetectionStatus.NOT_APPLICABLE.value,
        "server_500": server_500.value,
        "openapi_violation": DetectionStatus.NOT_DETECTED.value,
        "run_status": DetectionStatus.DETECTED.value,
    }


def load_run_selection(
    *,
    run_args: list[str] | None,
    config_path: Path | None,
) -> dict[str, Path]:
    """Load explicit tool→run-dir mapping from --run flags and/or a config file."""
    selected: dict[str, Path] = {}
    if config_path is not None:
        raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"run config must be a mapping: {config_path}")
        runs = raw.get("runs", raw)
        if not isinstance(runs, dict):
            raise ValueError(f"run config 'runs' must be a mapping: {config_path}")
        for tool, value in runs.items():
            tool_key = str(tool).lower()
            if tool_key not in KNOWN_TOOLS:
                raise ValueError(f"unknown tool in config: {tool}")
            if value is None:
                continue
            if isinstance(value, dict):
                path_value = value.get("path")
                if path_value is None:
                    continue
                selected[tool_key] = Path(str(path_value))
            else:
                selected[tool_key] = Path(str(value))
    for item in run_args or []:
        if "=" not in item:
            raise ValueError(f"--run must be tool=path, got {item!r}")
        tool, _, path_text = item.partition("=")
        tool_key = tool.strip().lower()
        if tool_key not in KNOWN_TOOLS:
            raise ValueError(f"unknown tool in --run: {tool}")
        selected[tool_key] = Path(path_text.strip())
    return selected


def parse_all(
    results_root: Path,
    *,
    runs: dict[str, Path] | None = None,
) -> list[dict[str, Any]]:
    """Parse explicitly selected runs. Missing tools are NOT_RUN (no latest-dir pick)."""
    del results_root  # retained for CLI compatibility; selection is explicit only
    parsers = {
        "ait": parse_ait,
        "restler": parse_restler,
        "evomaster": parse_evomaster,
    }
    selected = runs or {}
    rows: list[dict[str, Any]] = []
    for tool, parser in parsers.items():
        run_dir = selected.get(tool)
        if run_dir is None:
            row = {col: DetectionStatus.NOT_RUN.value for col in GROUND_TRUTH_COLUMNS}
            row.update({"tool": tool, "run_status": DetectionStatus.NOT_RUN.value})
        else:
            row = parser(Path(run_dir))
            row["tool"] = tool
            row["run_dir"] = str(run_dir)
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-root",
        type=Path,
        default=Path("results"),
        help="Repository results root (unused for auto-selection; kept for compatibility)",
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        metavar="TOOL=PATH",
        help="Explicit run directory (repeatable), e.g. --run restler=results/raw/tool-comparison/restler/ID",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML/JSON mapping of tool → path (or {runs: {tool: {path, sha256}}})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path",
    )
    args = parser.parse_args(argv)
    try:
        selected = load_run_selection(run_args=args.run, config_path=args.config)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rows = parse_all(args.results_root, runs=selected)
    text = json.dumps(rows, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
