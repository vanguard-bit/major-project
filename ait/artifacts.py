from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ValidationError, field_validator

REDACTED = "[REDACTED]"
EXACT_SECRET_KEYS = frozenset(
    {
        "authorization",
        "access_token",
        "refresh_token",
        "token",
        "client_secret",
        "secret",
        "api_key",
        "apikey",
        "cookie",
    }
)


class Provenance(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    generated_at_utc: AwareDatetime
    command: list[str]
    seed: int = 20260727
    git_commit: str | None
    python_version: str
    platform: str

    @field_validator("generated_at_utc")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value.astimezone(UTC)


class ArtifactEnvelope(BaseModel):
    provenance: Provenance
    experiment: str
    configuration: dict[str, Any]
    payload: dict[str, Any] | list[Any]


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_count"):
        return False
    if lowered in EXACT_SECRET_KEYS:
        return True
    return lowered.endswith("_token") or lowered.endswith("_secret")


def _reject_nonfinite(value: Any, path: tuple[Any, ...]) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite float at {'.'.join(str(p) for p in path)}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_nonfinite(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nonfinite(item, (*path, index))


def _assert_secrets_redacted(value: Any, path: tuple[Any, ...]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _is_secret_key(str(key)) and item != REDACTED:
                joined = ".".join(str(p) for p in (*path, key))
                raise ValueError(f"unredacted secret at {joined}")
            _assert_secrets_redacted(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_secrets_redacted(item, (*path, index))


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_secret_key(str(key)) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    commit = completed.stdout.strip()
    return commit or None


def collect_provenance(command: list[str], seed: int = 20260727) -> Provenance:
    return Provenance(
        generated_at_utc=datetime.now(tz=UTC),
        command=list(command),
        seed=seed,
        git_commit=_git_commit(),
        python_version=platform.python_version(),
        platform=platform.platform(),
    )


def _redacted_envelope(envelope: ArtifactEnvelope) -> ArtifactEnvelope:
    data = envelope.model_dump(mode="python")
    return ArtifactEnvelope.model_validate(redact_secrets(data))


def canonical_json_bytes(envelope: ArtifactEnvelope) -> bytes:
    _reject_nonfinite(envelope.configuration, ("configuration",))
    _reject_nonfinite(envelope.payload, ("payload",))
    redacted = _redacted_envelope(envelope)
    payload = redacted.model_dump(mode="json")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def write_artifact(path: Path, envelope: ArtifactEnvelope) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_json_bytes(envelope) + b"\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def assert_persisted_artifact_safe(envelope: ArtifactEnvelope) -> None:
    _reject_nonfinite(envelope.configuration, ("configuration",))
    _reject_nonfinite(envelope.payload, ("payload",))
    _assert_secrets_redacted(envelope.configuration, ("configuration",))
    _assert_secrets_redacted(envelope.payload, ("payload",))


def read_artifact(path: Path) -> ArtifactEnvelope:
    path = Path(path)
    envelope = ArtifactEnvelope.model_validate_json(path.read_bytes())
    assert_persisted_artifact_safe(envelope)
    return envelope


def validate_artifact_tree(root: Path) -> int:
    root = Path(root)
    if not root.exists():
        print("Validated 0 artifact(s)")
        return 0
    paths = sorted(root.rglob("*.json"))
    for path in paths:
        read_artifact(path)
        print(f"VALID {path}")
    print(f"Validated {len(paths)} artifact(s)")
    return len(paths)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python -m ait.artifacts <directory>", file=sys.stderr)
        return 2
    try:
        validate_artifact_tree(Path(args[0]))
    except (ValidationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
