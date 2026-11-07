"""Group and user reports.

The service knows only the ``ReportRepository`` interface; the SQL lives in
``app/repositories/sqlalchemy/report_queries.py``. Group reports are visible to
group members only (same rule as ``GroupService``).
"""

from app.domain.models import User
from app.repositories.interfaces.group_repository import GroupRepository
from app.repositories.interfaces.report_repository import (
    CategoryTotal,
    ExpenseAboveAverage,
    InactiveMember,
    MemberBalance,
    MonthlyTotal,
    ReportRepository,
    RunningTotalRow,
    TopPayer,
    UserOverview,
)
from app.services.group_service import require_member_group

MAX_TOP_PAYERS = 50


class ReportService:
    def __init__(self, reports: ReportRepository, groups: GroupRepository) -> None:
        self._reports = reports
        self._groups = groups

    def _check(self, user: User, group_id: int) -> None:
        require_member_group(self._groups, user, group_id)

    def member_balances(self, user: User, group_id: int) -> list[MemberBalance]:
        self._check(user, group_id)
        return self._reports.member_balances(group_id)

    def category_totals(self, user: User, group_id: int) -> list[CategoryTotal]:
        self._check(user, group_id)
        return self._reports.category_totals(group_id)

    def monthly_totals(self, user: User, group_id: int) -> list[MonthlyTotal]:
        self._check(user, group_id)
        return self._reports.monthly_totals(group_id)

    def top_payers(self, user: User, group_id: int, limit: int = 3) -> list[TopPayer]:
        self._check(user, group_id)
        return self._reports.top_payers(group_id, max(1, min(limit, MAX_TOP_PAYERS)))

    def inactive_members(self, user: User, group_id: int) -> list[InactiveMember]:
        self._check(user, group_id)
        return self._reports.inactive_members(group_id)

    def above_average_expenses(
        self, user: User, group_id: int
    ) -> list[ExpenseAboveAverage]:
        self._check(user, group_id)
        return self._reports.above_average_expenses(group_id)

    def running_total(self, user: User, group_id: int) -> list[RunningTotalRow]:
        self._check(user, group_id)
        return self._reports.running_total(group_id)

    def user_overview(self, user: User) -> UserOverview:
        """FR-19: the user's position in all groups; no group check needed."""
        return self._reports.user_overview(user.id)
