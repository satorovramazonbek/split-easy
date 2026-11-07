"""Fill a fresh SQLite database with a large, reproducible dataset.

    poetry run python scripts/seed.py                      # spliteasy-seed.db
    poetry run python scripts/seed.py --db big.db --force  # overwrite
    poetry run python scripts/seed.py --scale 0.01         # 1% size, for a quick try

Default size (spec section 10.3): 1 000 users, 200 groups, 100 000 expenses,
~300 000 expense shares, plus 10 000 settlements and 50 000 notifications.
``random.seed`` makes every run produce exactly the same rows.

The schema is created with Alembic (``upgrade head``), so the data lives in the
real schema with all constraints and foreign keys switched on. Every seeded user
can log in with the password ``secret123``.
"""

import argparse
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.common import ROOT, migrate

PASSWORD = "secret123"
CATEGORIES = ["food", "transport", "accommodation", "other"]
FIRST_DAY = date(2024, 1, 1)
DAYS = (date(2026, 10, 31) - FIRST_DAY).days
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"  # what SQLAlchemy stores for DateTime


@dataclass(frozen=True)
class Size:
    users: int = 1_000
    groups: int = 200
    expenses: int = 100_000
    settlements: int = 10_000
    notifications: int = 50_000

    def scaled(self, factor: float) -> "Size":
        return Size(
            users=max(20, round(self.users * factor)),
            groups=max(2, round(self.groups * factor)),
            expenses=max(10, round(self.expenses * factor)),
            settlements=max(2, round(self.settlements * factor)),
            notifications=max(10, round(self.notifications * factor)),
        )


def _stamp(day: date, rng: random.Random) -> str:
    moment = datetime(day.year, day.month, day.day) + timedelta(
        seconds=rng.randrange(86_400)
    )
    return moment.strftime(DATETIME_FORMAT)


def _equal_split(amount: int, count: int) -> list[int]:
    """Same rule as the domain: the first participants get the remainder."""
    base, remainder = divmod(amount, count)
    return [base + 1 if i < remainder else base for i in range(count)]


def _password_hash() -> str:
    from app.infrastructure.security import Argon2PasswordHasher

    return Argon2PasswordHasher().hash(PASSWORD)  # one hash shared by all users


def generate(size: Size, seed: int = 42, password_hash: str = "x"):
    """Yield (table, columns, rows) in foreign-key order."""
    rng = random.Random(seed)

    users = [
        (
            i,
            f"user{i:05d}",
            f"user{i:05d}@example.com",
            password_hash,
            _stamp(FIRST_DAY, rng),
        )
        for i in range(1, size.users + 1)
    ]
    yield "users", ("id", "username", "email", "password_hash", "created_at"), users

    groups, members = [], []
    group_members: dict[int, list[int]] = {}
    for group_id in range(1, size.groups + 1):
        owner = rng.randint(1, size.users)
        others = rng.sample(
            [u for u in range(1, size.users + 1) if u != owner],
            k=min(rng.randint(4, 14), size.users - 1),
        )
        ids = [owner, *others]
        group_members[group_id] = ids
        created = _stamp(FIRST_DAY, rng)
        groups.append((group_id, f"Guruh {group_id}", "UZS", owner, 0, created))
        members.extend((group_id, user_id, created) for user_id in ids)
    yield "groups", (
        "id",
        "name",
        "currency",
        "owner_id",
        "is_deleted",
        "created_at",
    ), groups
    yield "group_members", ("group_id", "user_id", "joined_at"), members

    expenses, shares = [], []
    for expense_id in range(1, size.expenses + 1):
        group_id = rng.randint(1, size.groups)
        ids = group_members[group_id]
        payer = rng.choice(ids)
        participants = rng.sample(ids, k=rng.randint(2, min(4, len(ids))))
        amount = rng.randint(1, 1_000) * 1_000
        day = FIRST_DAY + timedelta(days=rng.randrange(DAYS))
        expenses.append(
            (
                expense_id,
                group_id,
                f"Xarajat {expense_id}",
                amount,
                payer,
                rng.choice(CATEGORIES),
                "equal",
                day.isoformat(),
                payer,
                _stamp(day, rng),
            )
        )
        for user_id, share in zip(
            participants, _equal_split(amount, len(participants)), strict=True
        ):
            shares.append((expense_id, user_id, share))
    yield "expenses", (
        "id",
        "group_id",
        "description",
        "amount",
        "paid_by",
        "category",
        "split_type",
        "expense_date",
        "created_by",
        "created_at",
    ), expenses
    yield "expense_shares", ("expense_id", "user_id", "share_amount"), shares

    settlements = []
    for settlement_id in range(1, size.settlements + 1):
        group_id = rng.randint(1, size.groups)
        sender, receiver = rng.sample(group_members[group_id], k=2)
        day = FIRST_DAY + timedelta(days=rng.randrange(DAYS))
        settlements.append(
            (
                settlement_id,
                group_id,
                sender,
                receiver,
                rng.randint(1, 500) * 1_000,
                _stamp(day, rng),
            )
        )
    yield "settlements", (
        "id",
        "group_id",
        "from_user_id",
        "to_user_id",
        "amount",
        "created_at",
    ), settlements

    notifications = []
    for notification_id in range(1, size.notifications + 1):
        day = FIRST_DAY + timedelta(days=rng.randrange(DAYS))
        notifications.append(
            (
                notification_id,
                rng.randint(1, size.users),
                f"Yangi xarajat #{notification_id}",
                int(rng.random() < 0.7),
                _stamp(day, rng),
            )
        )
    yield "notifications", (
        "id",
        "user_id",
        "message",
        "is_read",
        "created_at",
    ), notifications


def seed(
    db_path: Path,
    size: Size | None = None,
    seed_value: int = 42,
    password_hash: str | None = None,
) -> dict[str, int]:
    """Create the schema in a new database and insert the generated rows."""
    db_path = Path(db_path)
    size = size or Size()
    if db_path.exists():
        raise FileExistsError(f"{db_path} already exists (use --force to replace)")
    migrate(db_path, "head")

    counts = {}
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:  # one transaction: all rows or nothing
            for table, columns, rows in generate(
                size, seed_value, password_hash or _password_hash()
            ):
                placeholders = ", ".join("?" for _ in columns)
                connection.executemany(
                    f"INSERT INTO {table} ({', '.join(columns)}) "
                    f"VALUES ({placeholders})",
                    rows,
                )
                counts[table] = len(rows)
        connection.execute("ANALYZE")  # statistics for the query planner
    finally:
        connection.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=ROOT / "spliteasy-seed.db")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="replace the file")
    args = parser.parse_args()

    if args.force:
        args.db.unlink(missing_ok=True)
    started = time.perf_counter()
    counts = seed(args.db, Size().scaled(args.scale), args.seed)
    elapsed = time.perf_counter() - started
    for table, count in counts.items():
        print(f"{table:>15}: {count:>8,}")
    print(f"Saved {args.db} in {elapsed:.1f} s")


if __name__ == "__main__":
    main()
