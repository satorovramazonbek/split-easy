"""Read-only reports. Services depend on this interface only (ISP, DIP)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class MemberBalance:
    user_id: int
    username: str
    paid: int
    owed: int
    sent: int
    received: int
    balance: int


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    expense_count: int
    total: int


@dataclass(frozen=True)
class MonthlyTotal:
    month: str  # "YYYY-MM"
    expense_count: int
    total: int


@dataclass(frozen=True)
class TopPayer:
    user_id: int
    username: str
    expense_count: int
    total_paid: int


@dataclass(frozen=True)
class InactiveMember:
    user_id: int
    username: str
    joined_at: datetime


@dataclass(frozen=True)
class ExpenseAboveAverage:
    id: int
    description: str
    amount: int
    paid_by: int
    expense_date: date
    group_average: float


@dataclass(frozen=True)
class RunningTotalRow:
    id: int
    expense_date: date
    amount: int
    running_total: int


@dataclass(frozen=True)
class GroupPosition:
    group_id: int
    group_name: str
    currency: str
    balance: int


@dataclass(frozen=True)
class CurrencyTotals:
    currency: str
    you_owe: int  # sum of negative balances, as a positive number
    owed_to_you: int  # sum of positive balances


@dataclass(frozen=True)
class UserOverview:
    groups: list[GroupPosition]
    totals: list[CurrencyTotals]


class BalanceReader(Protocol):
    """Only the balances (ISP): settlement and group services need nothing else."""

    def member_balances(self, group_id: int) -> list[MemberBalance]:
        """Net balance of every active member; the values add up to 0."""


class ReportRepository(BalanceReader, Protocol):
    """All reports, for the report pages and API."""

    def category_totals(self, group_id: int) -> list[CategoryTotal]: ...

    def monthly_totals(self, group_id: int) -> list[MonthlyTotal]: ...

    def top_payers(self, group_id: int, limit: int = 3) -> list[TopPayer]: ...

    def inactive_members(self, group_id: int) -> list[InactiveMember]: ...

    def above_average_expenses(self, group_id: int) -> list[ExpenseAboveAverage]: ...

    def running_total(self, group_id: int) -> list[RunningTotalRow]: ...

    def user_overview(self, user_id: int) -> UserOverview: ...
