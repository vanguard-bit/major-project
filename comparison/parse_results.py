#!/usr/bin/env python3
"""Parse comparison tool outputs without overclaiming.

Parser fixtures under tests/comparison/fixtures/ are committed minimal native-
output samples for unit tests only. They are NOT experimental runs and must not
be cited as tool-comparison results.
"""

from __future__ import annotations

import argparse
import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any


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


def latest_run(tool_root: Path) -> Path | None:
    if not tool_root.exists():
        return None
    runs = sorted([p for p in tool_root.iterdir() if p.is_dir()])
    return runs[-1] if runs else None


def parse_all(results_root: Path) -> list[dict[str, Any]]:
    base = Path(results_root) / "raw" / "tool-comparison"
    rows: list[dict[str, Any]] = []
    parsers = {
        "ait": parse_ait,
        "restler": parse_restler,
        "evomaster": parse_evomaster,
    }
    for tool, parser in parsers.items():
        run_dir = latest_run(base / tool)
        if run_dir is None:
            row = {col: DetectionStatus.NOT_RUN.value for col in GROUND_TRUTH_COLUMNS}
            row.update({"tool": tool, "run_status": DetectionStatus.NOT_RUN.value})
        else:
            row = parser(run_dir)
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
        help="Repository results root containing raw/tool-comparison/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path",
    )
    args = parser.parse_args(argv)
    rows = parse_all(args.results_root)
    text = json.dumps(rows, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
