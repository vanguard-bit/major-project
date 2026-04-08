from __future__ import annotations

from typing import Iterable

from ait.models import RunRecord, TargetConfig


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


store = InMemoryStore()
