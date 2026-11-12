import sqlite3
from pathlib import Path

import pytest

from app.infrastructure.security import Argon2PasswordHasher
from scripts.seed import PASSWORD, Size, generate, seed

SMALL = Size(users=40, groups=6, expenses=300, settlements=20, notifications=30)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory) -> tuple[Path, dict[str, int]]:
    db_path = tmp_path_factory.mktemp("seed") / "seed.db"
    return db_path, seed(db_path, SMALL)


def query(db_path: Path, sql: str):
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def test_counts(seeded) -> None:
    db_path, counts = seeded

    assert counts["users"] == 40
    assert counts["groups"] == 6
    assert counts["expenses"] == 300
    assert 2 * 300 <= counts["expense_shares"] <= 4 * 300
    for table, count in counts.items():
        assert query(db_path, f"SELECT count(*) FROM {table}") == [(count,)]


def test_generation_is_deterministic() -> None:
    first = [rows for _table, _cols, rows in generate(SMALL, seed=7)]
    second = [rows for _table, _cols, rows in generate(SMALL, seed=7)]
    other = [rows for _table, _cols, rows in generate(SMALL, seed=8)]

    assert first == second
    assert first != other


def test_data_respects_foreign_keys(seeded) -> None:
    assert query(seeded[0], "PRAGMA foreign_key_check") == []


def test_shares_add_up_to_expense_amount(seeded) -> None:
    mismatches = query(
        seeded[0],
        """
        SELECT e.id
        FROM expenses AS e
        JOIN expense_shares AS es ON es.expense_id = e.id
        GROUP BY e.id
        HAVING SUM(es.share_amount) <> e.amount
        """,
    )

    assert mismatches == []


def test_schema_is_at_head(seeded) -> None:
    assert query(seeded[0], "SELECT version_num FROM alembic_version") == [("0006",)]


def test_refuses_to_overwrite(seeded) -> None:
    with pytest.raises(FileExistsError):
        seed(seeded[0], SMALL)


def test_seeded_users_can_log_in(seeded) -> None:
    [(password_hash,)] = query(seeded[0], "SELECT password_hash FROM users LIMIT 1")

    assert Argon2PasswordHasher().verify(PASSWORD, password_hash)
