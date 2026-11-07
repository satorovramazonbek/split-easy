"""Measure the main queries without and with indexes (spec section 10.3).

    poetry run python scripts/seed.py            # once: builds spliteasy-seed.db
    poetry run python scripts/benchmark.py       # writes docs/benchmark.md

For each state the schema is moved with Alembic - ``0003`` has no query
indexes, ``head`` has them (migration 0004) - then ``ANALYZE`` refreshes the
planner statistics. Every query runs once to warm the cache and then ``--runs``
times (default 7); the table shows the average. ``EXPLAIN QUERY PLAN`` is saved
for every query in both states. The database is left at ``head``.
"""

import argparse
import platform
import sqlite3
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories.sqlalchemy import report_queries as reports
from scripts.common import ROOT, migrate

STATES = {"Indekssiz": "0003", "Indeks bilan": "head"}


@dataclass(frozen=True)
class Query:
    title: str
    sql: str
    params: dict = field(default_factory=dict)


def _pick_params(connection: sqlite3.Connection) -> dict:
    """Busiest group and the user in most groups: realistic, deterministic."""
    group_id = connection.execute(
        "SELECT group_id FROM expenses GROUP BY group_id "
        "ORDER BY count(*) DESC, group_id LIMIT 1"
    ).fetchone()[0]
    user_id = connection.execute(
        "SELECT user_id FROM group_members GROUP BY user_id "
        "ORDER BY count(*) DESC, user_id LIMIT 1"
    ).fetchone()[0]
    total = connection.execute("SELECT count(*) FROM expenses").fetchone()[0]
    # A page deep in the list: 90% of the way down (row 90 000 of 100 000).
    offset = max(0, total * 9 // 10 - 1)
    deep_id = connection.execute(
        "SELECT id FROM expenses ORDER BY id DESC LIMIT 1 OFFSET :offset",
        {"offset": offset},
    ).fetchone()[0]
    return {
        "group_id": group_id,
        "user_id": user_id,
        "offset": offset + 1,
        "after_id": deep_id,
    }


def queries(p: dict) -> list[Query]:
    group = {"group_id": p["group_id"]}
    user = {"user_id": p["user_id"]}
    return [
        Query(
            "Guruh xarajatlari, 1-sahifa (FR-13)",
            "SELECT id, description, amount, expense_date FROM expenses "
            "WHERE group_id = :group_id "
            "ORDER BY expense_date DESC, id DESC LIMIT 20",
            group,
        ),
        Query(
            "Kategoriya bo'yicha filtr (FR-14)",
            "SELECT id, description, amount, expense_date FROM expenses "
            "WHERE group_id = :group_id AND category = :category "
            "ORDER BY expense_date DESC, id DESC LIMIT 20",
            {**group, "category": "food"},
        ),
        Query("A'zolar balansi (1-so'rov)", reports.MEMBER_BALANCES, group),
        Query("Foydalanuvchi umumiy holati (8-so'rov)", reports.USER_OVERVIEW, user),
        Query(
            "Mening guruhlarim",
            "SELECT g.id, g.name FROM group_members AS gm "
            "JOIN groups AS g ON g.id = gm.group_id "
            "WHERE gm.user_id = :user_id AND g.is_deleted = 0",
            user,
        ),
        Query(
            "O'qilmagan bildirishnomalar",
            "SELECT id, message FROM notifications "
            "WHERE user_id = :user_id AND is_read = 0 "
            "ORDER BY created_at DESC LIMIT 20",
            user,
        ),
        Query("Kategoriyalar jami (2-so'rov)", reports.CATEGORY_TOTALS, group),
        Query(
            "Eng ko'p to'laganlar (4-so'rov)", reports.TOP_PAYERS, {**group, "limit": 3}
        ),
        # Bonus (10.6): the same deep page with OFFSET and with a keyset.
        Query(
            "Bonus: chuqur sahifa, OFFSET",
            "SELECT id, amount FROM expenses ORDER BY id DESC LIMIT 20 OFFSET :offset",
            {"offset": p["offset"]},
        ),
        Query(
            "Bonus: chuqur sahifa, keyset",
            "SELECT id, amount FROM expenses WHERE id < :after_id "
            "ORDER BY id DESC LIMIT 20",
            {"after_id": p["after_id"]},
        ),
    ]


def plan(connection: sqlite3.Connection, query: Query) -> list[str]:
    rows = connection.execute(f"EXPLAIN QUERY PLAN {query.sql}", query.params)
    return [row[3] for row in rows]


def measure(connection: sqlite3.Connection, query: Query, runs: int) -> float:
    connection.execute(query.sql, query.params).fetchall()  # warm-up
    timings = []
    for _ in range(runs):
        started = time.perf_counter()
        connection.execute(query.sql, query.params).fetchall()
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.mean(timings)


def run(db_path: Path, runs: int = 7) -> dict:
    results: dict = {"runs": runs, "states": {}}
    for label, revision in STATES.items():
        migrate(db_path, revision)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("ANALYZE")
            params = _pick_params(connection)
            results["params"] = params
            results["states"][label] = [
                (q.title, measure(connection, q, runs), plan(connection, q))
                for q in queries(params)
            ]
        finally:
            connection.close()
    return results


def _short_plan(lines: list[str]) -> str:
    """The first line that touches a table, e.g. SCAN expenses / SEARCH ..."""
    for line in lines:
        if line.startswith(("SCAN", "SEARCH")):
            return line.split(" (")[0].replace("USING ", "")
    return lines[0] if lines else ""


def to_markdown(results: dict, db_path: Path) -> str:
    before, after = results["states"].values()
    with sqlite3.connect(db_path) as connection:
        counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("users", "groups", "expenses", "expense_shares")
        }
    lines = [
        "# Benchmark: indekssiz va indeks bilan",
        "",
        "`scripts/benchmark.py` tomonidan yaratilgan — qo'lda tahrirlamang.",
        "",
        "- Ma'lumot: `scripts/seed.py` — "
        + ", ".join(f"{t} {c:,}" for t, c in counts.items()),
        f"- Har bir so'rov: 1 ta qizdirish + {results['runs']} ta o'lchov, o'rtacha",
        f"- Parametrlar: `{results['params']}`",
        (
            f"- Muhit: Python {platform.python_version()}, SQLite "
            f"{sqlite3.sqlite_version}, {platform.system()} {platform.machine()}"
        ),
        "",
        (
            "| So'rov | Indekssiz (ms) | Indeks bilan (ms) | Tezlashish | "
            "Reja (oldin → keyin) |"
        ),
        "|---|---:|---:|---:|---|",
    ]
    for (title, slow, plan_before), (_t, fast, plan_after) in zip(
        before, after, strict=True
    ):
        speedup = slow / fast if fast else float("inf")
        lines.append(
            f"| {title} | {slow:.2f} | {fast:.2f} | {speedup:.1f}× | "
            f"`{_short_plan(plan_before)}` → `{_short_plan(plan_after)}` |"
        )
    lines += ["", "## EXPLAIN QUERY PLAN", ""]
    for (title, _s, plan_before), (_t, _f, plan_after) in zip(
        before, after, strict=True
    ):
        lines += [
            f"### {title}",
            "",
            "Indekssiz:",
            "",
            "```text",
            *plan_before,
            "```",
            "",
            "Indeks bilan:",
            "",
            "```text",
            *plan_after,
            "```",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=ROOT / "spliteasy-seed.db")
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "benchmark.md")
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"{args.db} not found: run scripts/seed.py first")
    if args.runs < 5:
        raise SystemExit("--runs must be at least 5 (spec section 10.3)")

    results = run(args.db, args.runs)
    args.out.write_text(to_markdown(results, args.db), encoding="utf-8")
    for (title, slow, _), (_t, fast, _p) in zip(
        *results["states"].values(), strict=True
    ):
        print(f"{title:<45} {slow:>9.2f} ms -> {fast:>8.2f} ms")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
