"""Use the same SQLite URL as the app; never create schemas on startup."""

from alembic import context

from fairmade import models  # noqa: F401
from fairmade.database import Base, database_url, make_engine


def run_migrations():
    if context.is_offline_mode():
        context.configure(
            url=database_url(),
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(database_url())
        try:
            with engine.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=Base.metadata,
                    render_as_batch=True,
                )
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
