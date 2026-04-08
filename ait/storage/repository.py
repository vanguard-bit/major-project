from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from ait.models import RunRecord, TargetConfig
from ait.storage.orm import RunRecordORM, TargetConfigORM


class TargetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, target: TargetConfig) -> TargetConfig:
        existing = self._session.get(TargetConfigORM, target.name)
        if existing:
            existing.data = target.model_dump_json()
        else:
            self._session.add(TargetConfigORM(name=target.name, data=target.model_dump_json()))
        self._session.commit()
        return target

    def get(self, name: str) -> TargetConfig:
        row = self._session.get(TargetConfigORM, name)
        if row is None:
            raise KeyError(name)
        return TargetConfig.model_validate_json(row.data)

    def list_all(self) -> list[TargetConfig]:
        rows = self._session.query(TargetConfigORM).all()
        return [TargetConfig.model_validate_json(r.data) for r in rows]


class RunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, run: RunRecord) -> RunRecord:
        existing = self._session.get(RunRecordORM, run.run_id)
        if existing:
            existing.status = run.status
            existing.target_name = run.target.name
            existing.data = run.model_dump_json()
        else:
            self._session.add(
                RunRecordORM(
                    run_id=run.run_id,
                    status=run.status,
                    target_name=run.target.name,
                    data=run.model_dump_json(),
                )
            )
        self._session.commit()
        return run

    def get(self, run_id: str) -> RunRecord:
        row = self._session.get(RunRecordORM, run_id)
        if row is None:
            raise KeyError(run_id)
        return RunRecord.model_validate_json(row.data)

    def list_by_target(self, target_name: str) -> list[RunRecord]:
        rows = (
            self._session.query(RunRecordORM)
            .filter(RunRecordORM.target_name == target_name)
            .order_by(RunRecordORM.created_at.desc())
            .all()
        )
        return [RunRecord.model_validate_json(r.data) for r in rows]

    def list_all(self) -> list[RunRecord]:
        rows = self._session.query(RunRecordORM).order_by(RunRecordORM.created_at.desc()).all()
        return [RunRecord.model_validate_json(r.data) for r in rows]
