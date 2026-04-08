from __future__ import annotations

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session

from ait.storage.orm import Base


def get_database_url() -> str:
    return os.environ.get("AIT_DATABASE_URL", "sqlite:///ait.db")


def make_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine: Engine) -> Session:
    return Session(engine)
