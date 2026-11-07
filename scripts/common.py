"""Helpers shared by the seed and benchmark scripts."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config


def alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(db_path).as_posix()}")
    return config


def migrate(db_path: Path, revision: str = "head") -> None:
    """Move the database schema to ``revision`` (upgrade or downgrade)."""
    config = alembic_config(db_path)
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{Path(db_path).as_posix()}")
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    engine.dispose()
    if revision == "head" or current is None or revision > current:
        command.upgrade(config, revision)
    else:
        command.downgrade(config, revision)
