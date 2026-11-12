"""``ReportRepository`` backed by the raw SQL in ``report_queries.py``."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.repositories.interfaces.report_repository import (
    CategoryTotal,
    CurrencyTotals,
    ExpenseAboveAverage,
    GroupPosition,
    InactiveMember,
    MemberBalance,
    MonthlyTotal,
    RunningTotalRow,
    TopPayer,
    UserOverview,
)
from app.repositories.sqlalchemy import report_queries as q
from app.repositories.sqlalchemy.user_repository import as_utc


def _date(value: date | str) -> date:
    # Raw SQL returns SQLite's stored text, not Python objects.
    return value if isinstance(value, date) else date.fromisoformat(value)


def _datetime(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return as_utc(value)


class SqlAlchemyReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _rows(self, sql: str, **params: object) -> Sequence[RowMapping]:
        return self._session.execute(text(sql), params).mappings().all()

    def member_balances(self, group_id: int) -> list[MemberBalance]:
        return [
            MemberBalance(**row)
            for row in self._rows(q.MEMBER_BALANCES, group_id=group_id)
        ]

    def category_totals(self, group_id: int) -> list[CategoryTotal]:
        return [
            CategoryTotal(**row)
            for row in self._rows(q.CATEGORY_TOTALS, group_id=group_id)
        ]

    def monthly_totals(self, group_id: int) -> list[MonthlyTotal]:
        return [
            MonthlyTotal(**row)
            for row in self._rows(q.MONTHLY_TOTALS, group_id=group_id)
        ]

    def top_payers(self, group_id: int, limit: int = 3) -> list[TopPayer]:
        return [
            TopPayer(**row)
            for row in self._rows(q.TOP_PAYERS, group_id=group_id, limit=limit)
        ]

    def inactive_members(self, group_id: int) -> list[InactiveMember]:
        return [
            InactiveMember(
                user_id=row["user_id"],
                username=row["username"],
                joined_at=_datetime(row["joined_at"]),
            )
            for row in self._rows(q.INACTIVE_MEMBERS, group_id=group_id)
        ]

    def above_average_expenses(self, group_id: int) -> list[ExpenseAboveAverage]:
        return [
            ExpenseAboveAverage(**{**row, "expense_date": _date(row["expense_date"])})
            for row in self._rows(q.ABOVE_AVERAGE_EXPENSES, group_id=group_id)
        ]

    def running_total(self, group_id: int) -> list[RunningTotalRow]:
        return [
            RunningTotalRow(**{**row, "expense_date": _date(row["expense_date"])})
            for row in self._rows(q.RUNNING_TOTAL, group_id=group_id)
        ]

    def user_overview(self, user_id: int) -> UserOverview:
        groups = [
            GroupPosition(**row) for row in self._rows(q.USER_OVERVIEW, user_id=user_id)
        ]
        owe: dict[str, int] = defaultdict(int)
        owed: dict[str, int] = defaultdict(int)
        for position in groups:
            owe[position.currency] += max(-position.balance, 0)
            owed[position.currency] += max(position.balance, 0)
        totals = [
            CurrencyTotals(currency=c, you_owe=owe[c], owed_to_you=owed[c])
            for c in sorted({g.currency for g in groups})
        ]
        return UserOverview(groups=groups, totals=totals)
