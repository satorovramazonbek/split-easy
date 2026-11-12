"""The benchmark script runs end to end on a small seeded database."""

import sqlite3

from scripts.benchmark import run, to_markdown
from scripts.seed import Size, seed


def test_benchmark_compares_plans_without_and_with_indexes(tmp_path) -> None:
    db_path = tmp_path / "bench.db"
    seed(
        db_path,
        Size(users=30, groups=4, expenses=400, settlements=10, notifications=20),
    )

    results = run(db_path, runs=5)

    before, after = results["states"]["Indekssiz"], results["states"]["Indeks bilan"]
    assert [title for title, *_ in before] == [title for title, *_ in after]
    first_page_before, first_page_after = before[0][2], after[0][2]
    assert any(line.startswith("SCAN expenses") for line in first_page_before)
    assert any(
        "ix_expenses_group_id_expense_date_id" in line for line in first_page_after
    )
    with sqlite3.connect(db_path) as connection:  # left at head
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[
            0
        ] == ("0006")

    report = to_markdown(results, db_path)
    assert "| So'rov | Indekssiz (ms) | Indeks bilan (ms)" in report
    assert "EXPLAIN QUERY PLAN" in report
