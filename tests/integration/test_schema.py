"""Alembic migrations, docs/schema.sql and the ORM must give the same schema.

The comparison reads SQLite's own catalog (PRAGMA table_info, foreign_key_list,
index_list) plus the CHECK clauses, so formatting differences do not matter.
"""

import re
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.infrastructure.database import Base, make_engine

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = ROOT / "docs" / "schema.sql"
IGNORED_TABLES = {"alembic_version"}


def alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def _check_clauses(create_sql: str) -> list[str]:
    """Bodies of all CHECK (...) clauses, with balanced parentheses."""
    clauses = []
    for match in re.finditer(r"\bCHECK\s*\(", create_sql, re.IGNORECASE):
        depth, start = 1, match.end()
        position = start
        while depth:
            depth += {"(": 1, ")": -1}.get(create_sql[position], 0)
            position += 1
        body = create_sql[start : position - 1]
        clauses.append(re.sub(r"\s+", " ", body).strip().lower())
    return sorted(clauses)


def _default(value: str | None) -> str | None:
    return None if value is None else value.strip("()'\"")


def describe(db_path: Path) -> dict:
    """A comparable description of every table in the database."""
    connection = sqlite3.connect(db_path)
    try:
        tables = {
            name: sql
            for name, sql in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
            if name not in IGNORED_TABLES
        }
        schema = {}
        for table, create_sql in sorted(tables.items()):
            columns = [
                (name, col_type.upper(), bool(notnull), _default(default), pk)
                for _cid, name, col_type, notnull, default, pk in connection.execute(
                    f"PRAGMA table_info('{table}')"
                )
            ]
            foreign_keys: dict[int, list] = {}
            for row in connection.execute(f"PRAGMA foreign_key_list('{table}')"):
                fk_id, _seq, ref_table, from_col, to_col, _upd, on_delete = row[:7]
                entry = foreign_keys.setdefault(fk_id, [ref_table, [], [], on_delete])
                entry[1].append(from_col)
                entry[2].append(to_col)
            indexes = []
            for _seq, name, unique, origin, _partial in connection.execute(
                f"PRAGMA index_list('{table}')"
            ):
                columns_of_index = [
                    row[2] for row in connection.execute(f"PRAGMA index_info('{name}')")
                ]
                label = name if origin == "c" else origin
                indexes.append((label, bool(unique), tuple(columns_of_index)))
            schema[table] = {
                "columns": columns,
                "foreign_keys": sorted(
                    (ref, tuple(src), tuple(dst), rule)
                    for ref, src, dst, rule in foreign_keys.values()
                ),
                "indexes": sorted(indexes),
                "checks": _check_clauses(create_sql),
            }
        return schema
    finally:
        connection.close()


@pytest.fixture
def alembic_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "alembic.db"
    command.upgrade(alembic_config(db_path), "head")
    return db_path


@pytest.fixture
def schema_sql_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "schema_sql.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    connection.close()
    return db_path


@pytest.fixture
def orm_db(tmp_path: Path) -> Path:
    from app.repositories.sqlalchemy import orm_models  # noqa: F401

    db_path = tmp_path / "orm.db"
    engine = make_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return db_path


def test_all_tables_exist(alembic_db: Path) -> None:
    assert set(describe(alembic_db)) == {
        "users",
        "groups",
        "group_members",
        "expenses",
        "expense_shares",
        "settlements",
        "notifications",
        "quick_split_drafts",
    }


def test_alembic_matches_schema_sql(alembic_db: Path, schema_sql_db: Path) -> None:
    assert describe(alembic_db) == describe(schema_sql_db)


def test_alembic_matches_orm_models(alembic_db: Path, orm_db: Path) -> None:
    assert describe(alembic_db) == describe(orm_db)


def test_downgrade_to_base_removes_everything(alembic_db: Path) -> None:
    command.downgrade(alembic_config(alembic_db), "base")

    assert describe(alembic_db) == {}


def test_index_migration_is_reversible(alembic_db: Path) -> None:
    config = alembic_config(alembic_db)

    command.downgrade(config, "0003")
    without = describe(alembic_db)
    command.upgrade(config, "head")

    named = [
        i for t in without.values() for i in t["indexes"] if i[0].startswith("ix_")
    ]
    assert named == []
    assert describe(alembic_db) != without


def test_at_least_four_indexes_one_composite(alembic_db: Path) -> None:
    indexes = [
        columns
        for table in describe(alembic_db).values()
        for name, _unique, columns in table["indexes"]
        if name.startswith("ix_")
    ]

    assert len(indexes) >= 4
    assert any(len(columns) > 1 for columns in indexes)
