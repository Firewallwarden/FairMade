"""Validate the combined migration chain using only disposable FairMade databases."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

import fairmade.main  # noqa: F401 -- load the application's complete model registry.
from fairmade.database import Base, make_engine


def compare(url):
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
            assert differences == [], differences
            return len(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def main():
    root = Path(__file__).resolve().parents[1]
    cache = root / "backend/.pytest_cache"
    cache.mkdir(exist_ok=True)
    config = Config(str(root / "backend/alembic.ini"))
    previous = os.environ.get("FAIRMADE_DATABASE_URL")
    with TemporaryDirectory(prefix="fairmade-migration-", dir=cache) as directory:
        target = Path(directory).resolve()
        assert target.is_relative_to(root.resolve())
        url = "sqlite:///" + (target / "validation.sqlite3").as_posix()
        try:
            os.environ["FAIRMADE_DATABASE_URL"] = url
            command.upgrade(config, "head")
            tables = compare(url)
            command.downgrade(config, "base")
            engine = make_engine(url)
            try:
                assert inspect(engine).get_table_names() == ["alembic_version"]
            finally:
                engine.dispose()
            command.upgrade(config, "head")
            assert compare(url) == tables
            print(f"Migration upgrade/downgrade/re-upgrade passed; {tables} tables match models.")
        finally:
            if previous is None:
                os.environ.pop("FAIRMADE_DATABASE_URL", None)
            else:
                os.environ["FAIRMADE_DATABASE_URL"] = previous


if __name__ == "__main__":
    main()
