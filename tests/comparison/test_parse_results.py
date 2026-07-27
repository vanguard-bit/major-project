"""Parse-results unit tests.

Fixtures under tests/comparison/fixtures/ are parser fixtures only — they are
NOT experimental tool-comparison runs and must not be cited as such.
"""

from __future__ import annotations

import json
from pathlib import Path

from comparison.parse_results import (
    DetectionStatus,
    parse_ait,
    parse_all,
    parse_evomaster,
    parse_restler,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_ait_detects_client_policy_rows_from_fixture():
    # PARSER FIXTURE — not an experimental run
    row = parse_ait(FIXTURES / "ait_sample")
    assert row["client_policy_hidden_endpoint"] == DetectionStatus.DETECTED.value
    assert row["sensitive_field"] == DetectionStatus.DETECTED.value
    assert row["server_500"] == DetectionStatus.NOT_APPLICABLE.value
    assert row["openapi_violation"] == DetectionStatus.NOT_APPLICABLE.value


def test_parse_restler_not_run_and_server_fault_fixture():
    missing = parse_restler(FIXTURES / "does_not_exist")
    assert missing["run_status"] == DetectionStatus.NOT_RUN.value
    assert missing["client_policy_hidden_endpoint"] == DetectionStatus.NOT_RUN.value

    # PARSER FIXTURE — not an experimental run
    row = parse_restler(FIXTURES / "restler_sample")
    assert row["server_500"] == DetectionStatus.DETECTED.value
    assert row["client_policy_hidden_endpoint"] == DetectionStatus.NOT_APPLICABLE.value
    assert row["sensitive_field"] == DetectionStatus.NOT_APPLICABLE.value


def test_parse_evomaster_not_run_fixture():
    # PARSER FIXTURE — not an experimental run
    row = parse_evomaster(FIXTURES / "evomaster_not_run")
    assert row["run_status"] == DetectionStatus.NOT_RUN.value
    assert all(
        row[col] == DetectionStatus.NOT_RUN.value
        for col in (
            "client_policy_hidden_endpoint",
            "sensitive_field",
            "server_500",
            "openapi_violation",
        )
    )


def test_parse_all_marks_missing_tools_not_run(tmp_path: Path):
    rows = parse_all(tmp_path)
    by_tool = {row["tool"]: row for row in rows}
    assert by_tool["restler"]["run_status"] == DetectionStatus.NOT_RUN.value
    assert by_tool["evomaster"]["run_status"] == DetectionStatus.NOT_RUN.value


def test_not_applicable_never_equals_not_detected_semantics():
    # Guarding the scientific rule: N/A is a distinct status string.
    assert DetectionStatus.NOT_APPLICABLE.value != DetectionStatus.NOT_DETECTED.value
    sample = json.loads((FIXTURES / "ait_sample" / "findings.json").read_text())
    assert "findings" in sample
