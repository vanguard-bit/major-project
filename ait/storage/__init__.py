from __future__ import annotations

import json
import os
from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ait.models import RunRecord, TargetConfig
from ait.storage.orm import Base, RunRecordORM, TargetConfigORM


def _get_database_url() -> str:
    return os.environ.get("AIT_DATABASE_URL", "sqlite:///ait.db")


def _make_engine():
    url = _get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


class SQLAlchemyStore:
    """Persistent store backed by SQLAlchemy (SQLite by default, PostgreSQL via env var)."""

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or _get_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self._engine = create_engine(url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)

    def save_target(self, target: TargetConfig) -> TargetConfig:
        with Session(self._engine) as session:
            existing = session.get(TargetConfigORM, target.name)
            if existing:
                existing.data = target.model_dump_json()
            else:
                session.add(TargetConfigORM(name=target.name, data=target.model_dump_json()))
            session.commit()
        return target

    def get_target(self, name: str) -> TargetConfig:
        with Session(self._engine) as session:
            row = session.get(TargetConfigORM, name)
            if row is None:
                raise KeyError(name)
            return TargetConfig.model_validate_json(row.data)

    def list_targets(self) -> Iterable[TargetConfig]:
        with Session(self._engine) as session:
            rows = session.query(TargetConfigORM).all()
            return [TargetConfig.model_validate_json(r.data) for r in rows]

    def save_run(self, run: RunRecord) -> RunRecord:
        with Session(self._engine) as session:
            existing = session.get(RunRecordORM, run.run_id)
            if existing:
                existing.status = run.status
                existing.target_name = run.target.name
                existing.data = run.model_dump_json()
            else:
                session.add(
                    RunRecordORM(
                        run_id=run.run_id,
                        status=run.status,
                        target_name=run.target.name,
                        data=run.model_dump_json(),
                    )
                )
            session.commit()
        return run

    def get_run(self, run_id: str) -> RunRecord:
        with Session(self._engine) as session:
            row = session.get(RunRecordORM, run_id)
            if row is None:
                raise KeyError(run_id)
            return RunRecord.model_validate_json(row.data)

    def list_runs(self, target_name: str | None = None) -> list[RunRecord]:
        with Session(self._engine) as session:
            query = session.query(RunRecordORM)
            if target_name:
                query = query.filter(RunRecordORM.target_name == target_name)
            rows = query.order_by(RunRecordORM.run_id.desc()).all()
            return [RunRecord.model_validate_json(r.data) for r in rows]
