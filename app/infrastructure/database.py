"""SQLAlchemy engine and session factory."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.infrastructure.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def make_engine(url: str, **kwargs) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:
            # SQLite ignores foreign keys unless this pragma is set per connection.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

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


def create_tables() -> None:
    """Create missing tables. Will be replaced by Alembic migrations."""
    # Import ORM models so they are registered on ``Base.metadata``.
    from app.repositories.sqlalchemy import orm_models  # noqa: F401

    Base.metadata.create_all(engine)
