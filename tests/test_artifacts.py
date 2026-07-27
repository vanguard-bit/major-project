from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ait.artifacts import (
    ArtifactEnvelope,
    Provenance,
    canonical_json_bytes,
    collect_provenance,
    read_artifact,
    redact_secrets,
    write_artifact,
)


def _envelope(payload: dict | list, configuration: dict | None = None) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        provenance=Provenance(
            generated_at_utc=datetime(2026, 7, 27, 0, 0, 0, tzinfo=UTC),
            command=["pytest"],
            seed=20260727,
            git_commit=None,
            python_version="3.12.0",
            platform="test",
        ),
        experiment="unit",
        configuration=configuration or {},
        payload=payload,
    )


def test_canonical_json_stable_for_different_insertion_order():
    left = _envelope({"b": 1, "a": 2})
    right = _envelope({"a": 2, "b": 1})
    assert canonical_json_bytes(left) == canonical_json_bytes(right)


def test_redact_secrets_nested_authorization_token_and_secret():
    value = {
        "Authorization": "Bearer secret",
        "nested": {
            "access_token": "abc",
            "refresh_token": "def",
            "token": "ghi",
            "client_secret": "jkl",
            "secret": "mno",
            "api_key": "pqr",
            "apikey": "stu",
            "cookie": "vwx",
            "oauth_token": "yz",
            "app_secret": "123",
        },
        "safe": "keep",
    }
    redacted = redact_secrets(value)
    assert redacted["Authorization"] == "[REDACTED]"
    nested = redacted["nested"]
    for key in (
        "access_token",
        "refresh_token",
        "token",
        "client_secret",
        "secret",
        "api_key",
        "apikey",
        "cookie",
        "oauth_token",
        "app_secret",
    ):
        assert nested[key] == "[REDACTED]"
    assert redacted["safe"] == "keep"


def test_token_count_is_not_redacted():
    assert redact_secrets({"token_count": 7}) == {"token_count": 7}


def test_write_artifact_creates_parent_directories(tmp_path: Path):
    path = tmp_path / "nested" / "out" / "artifact.json"
    write_artifact(path, _envelope({"ok": True}))
    assert path.is_file()


def test_write_artifact_ends_with_exactly_one_newline(tmp_path: Path):
    path = tmp_path / "artifact.json"
    write_artifact(path, _envelope({"ok": True}))
    data = path.read_bytes()
    assert data.endswith(b"\n")
    assert not data.endswith(b"\n\n")


def test_write_artifact_redacts_before_persist(tmp_path: Path):
    path = tmp_path / "artifact.json"
    write_artifact(path, _envelope({"token": "super-secret", "ok": 1}))
    text = path.read_text()
    assert "super-secret" not in text
    assert "[REDACTED]" in text
    loaded = read_artifact(path)
    assert loaded.payload["token"] == "[REDACTED]"
    assert loaded.payload["ok"] == 1


def test_read_artifact_rejects_malformed_json(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not-json")
    with pytest.raises(ValidationError):
        read_artifact(path)


def test_read_artifact_rejects_wrong_schema_version(tmp_path: Path):
    path = tmp_path / "bad-schema.json"
    path.write_text(
        """{
  "provenance": {
    "schema_version": "9.9.9",
    "generated_at_utc": "2026-07-27T00:00:00Z",
    "command": ["pytest"],
    "seed": 20260727,
    "git_commit": null,
    "python_version": "3.12.0",
    "platform": "test"
  },
  "experiment": "unit",
  "configuration": {},
  "payload": {}
}
"""
    )
    with pytest.raises(ValidationError):
        read_artifact(path)


def test_collect_provenance_includes_command_and_seed():
    provenance = collect_provenance(["python", "-m", "ait.artifacts"], seed=20260727)
    assert provenance.command == ["python", "-m", "ait.artifacts"]
    assert provenance.seed == 20260727
    assert provenance.schema_version == "1.0.0"
    assert provenance.python_version
    assert provenance.platform
