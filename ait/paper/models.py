"""Pydantic models for paper artifact selection and claim registry."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "1.0.0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer must start with '/': {pointer}")
    if pointer == "/":
        return document
    current: Any = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(f"JSON pointer miss at '{token}' in {pointer}")
            current = current[token]
        elif isinstance(current, list):
            index = int(token)
            current = current[index]
        else:
            raise KeyError(f"JSON pointer cannot traverse {type(current)} at {pointer}")
    return current


class ArtifactRef(BaseModel):
    path: str
    sha256: str

    @field_validator("sha256")
    @classmethod
    def _hex_digest(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("sha256 must be a 64-char lowercase hex digest")
        return value


class LiveRunsRefs(BaseModel):
    github_readonly: ArtifactRef | None = None
    github_smoke: ArtifactRef | None = None
    notion_readonly: ArtifactRef | None = None


class PaperArtifactsManifest(BaseModel):
    schema_version: Literal["1.0.0"]
    offline_manifest: ArtifactRef | None = None
    scenario_metrics: ArtifactRef | None = None
    sensitivity_summary: ArtifactRef | None = None
    sensitivity_rows: ArtifactRef | None = None
    replay_match_table: ArtifactRef | None = None
    benchmark_summary: ArtifactRef | None = None
    robustness_metrics: ArtifactRef | None = None
    live_runs: LiveRunsRefs = Field(default_factory=LiveRunsRefs)
    tool_comparison: ArtifactRef | None = None

    def ref_for(self, name: str) -> ArtifactRef | None:
        if name in {"github_readonly", "github_smoke", "notion_readonly"}:
            return getattr(self.live_runs, name)
        return getattr(self, name, None)

    def is_available(self, name: str) -> bool:
        return self.ref_for(name) is not None

    def selected_refs(self) -> dict[str, ArtifactRef]:
        out: dict[str, ArtifactRef] = {}
        for key in (
            "offline_manifest",
            "scenario_metrics",
            "sensitivity_summary",
            "sensitivity_rows",
            "replay_match_table",
            "benchmark_summary",
            "robustness_metrics",
            "tool_comparison",
        ):
            ref = getattr(self, key)
            if ref is not None:
                out[key] = ref
        for key in ("github_readonly", "github_smoke", "notion_readonly"):
            ref = getattr(self.live_runs, key)
            if ref is not None:
                out[key] = ref
        return out


class ClaimEvidence(BaseModel):
    artifact: str
    json_pointer: str


class Claim(BaseModel):
    id: str
    text_pattern: str
    documents: list[str]
    evidence: ClaimEvidence
    required: bool = False


class ClaimsRegistry(BaseModel):
    schema_version: Literal["1.0.0"]
    claims: list[Claim]


def verify_artifact_ref(path: Path, expected_sha256: str) -> None:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"missing artifact file: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"hash mismatch for {path}: expected {expected_sha256}, got {actual}"
        )


def load_paper_artifacts_manifest(
    path: Path,
    *,
    root: Path | None = None,
    verify: bool = True,
) -> PaperArtifactsManifest:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("paper_artifacts.yaml must be a mapping")
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported paper_artifacts schema_version: {version!r} "
            f"(expected {SCHEMA_VERSION!r})"
        )
    try:
        manifest = PaperArtifactsManifest.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"invalid paper_artifacts.yaml: {exc}") from exc

    if verify:
        base = Path(root) if root is not None else path.parent.parent
        for name, ref in manifest.selected_refs().items():
            target = Path(ref.path)
            if not target.is_absolute():
                target = base / target
            try:
                verify_artifact_ref(target, ref.sha256)
            except ValueError as exc:
                raise ValueError(f"{name}: {exc}") from exc
    return manifest


def load_claims_registry(path: Path) -> ClaimsRegistry:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("claims.yaml must be a mapping")
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported claims schema_version: {version!r} "
            f"(expected {SCHEMA_VERSION!r})"
        )
    return ClaimsRegistry.model_validate(raw)
