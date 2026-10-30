"""SQLite connections and request-scoped transactions. Schema changes use Alembic."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def database_url() -> str:
    return os.environ.get("FAIRMADE_DATABASE_URL", "sqlite:///./fairmade.sqlite3")


def make_engine(url: str) -> Engine:
    if not url.startswith("sqlite:///"):
        raise ValueError("This local MVP supports SQLite URLs only")
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def get_db(request: Request) -> Iterator[Session]:
    # Write routes commit before returning a success response. Closing the
    # session rolls back uncommitted work when any part of a request fails.
    with Session(request.app.state.engine, expire_on_commit=False) as session:
        yield session
