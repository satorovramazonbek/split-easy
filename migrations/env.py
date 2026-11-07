"""Alembic environment.

The database URL comes from, in order:
1. ``config.attributes["connection"]`` - an open connection (used by tests);
2. ``sqlalchemy.url`` in alembic.ini (empty by default);
3. ``SPLITEASY_DATABASE_URL`` / the default in ``app.infrastructure.config``.
"""

from logging.config import fileConfig

from alembic import context

from app.infrastructure.config import settings
from app.infrastructure.database import Base, make_engine
from app.repositories.sqlalchemy import orm_models  # noqa: F401  (registers tables)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        # SQLite cannot ALTER most constraints; batch mode recreates the table.
        render_as_batch=True,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (``alembic upgrade --sql``)."""
    _configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    # make_engine turns on PRAGMA foreign_keys for every SQLite connection.
    engine = make_engine(_url())
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
