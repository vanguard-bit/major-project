from __future__ import annotations

import os
from typing import Iterable

from ait.models import RunRecord, TargetConfig
from ait.storage import SQLAlchemyStore


class InMemoryStore:
    def __init__(self) -> None:
        self.targets: dict[str, TargetConfig] = {}
        self.runs: dict[str, RunRecord] = {}

    def save_target(self, target: TargetConfig) -> TargetConfig:
        self.targets[target.name] = target
        return target

    def get_target(self, name: str) -> TargetConfig:
        return self.targets[name]

    def list_targets(self) -> Iterable[TargetConfig]:
        return self.targets.values()

    def save_run(self, run: RunRecord) -> RunRecord:
        self.runs[run.run_id] = run
        return run

    def get_run(self, run_id: str) -> RunRecord:
        return self.runs[run_id]

    def list_runs(self, target_name: str | None = None) -> list[RunRecord]:
        runs = list(self.runs.values())
        if target_name:
            runs = [r for r in runs if r.target.name == target_name]
        return runs


def _make_default_store() -> SQLAlchemyStore | InMemoryStore:
    if os.environ.get("AIT_USE_MEMORY_STORE", "").lower() in ("1", "true", "yes"):
        return InMemoryStore()
    return SQLAlchemyStore()


store: SQLAlchemyStore | InMemoryStore = _make_default_store()
