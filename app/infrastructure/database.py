"""SQLAlchemy engine and session factory."""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.infrastructure.config import settings

# Deterministic constraint names: Alembic migrations, docs/schema.sql and the
# ORM must produce the same schema, so nothing may be named at random.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(url: str, **kwargs) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_connection, _record) -> None:
            # The sqlite3 driver delays BEGIN until the first INSERT/UPDATE. If a
            # transaction starts with SAVEPOINT (session.begin_nested()), SQLite
            # then treats the savepoint as the whole transaction and RELEASE
            # commits it - a later rollback() can no longer undo it. Turn the
            # driver's own BEGIN off and emit it ourselves (SQLAlchemy recipe
            # "Serializable isolation / Savepoints / Transactional DDL").
            dbapi_connection.isolation_level = None
            # SQLite ignores foreign keys unless this pragma is set per connection.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        @event.listens_for(engine, "begin")
        def _on_begin(connection) -> None:
            connection.exec_driver_sql("BEGIN")

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """One session per request: commit on success, roll back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
