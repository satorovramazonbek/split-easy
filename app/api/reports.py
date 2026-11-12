"""Report API: read-only statistics for a group and for the current user."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, ReportServiceDep
from app.repositories.interfaces.report_repository import (
    CategoryTotal,
    ExpenseAboveAverage,
    InactiveMember,
    MemberBalance,
    MonthlyTotal,
    RunningTotalRow,
    TopPayer,
    UserOverview,
)
from app.services.group_service import GroupNotFoundError, GroupPermissionError

router = APIRouter(prefix="/api", tags=["reports"])


def _guarded[T](call: Callable[[], T]) -> T:
    try:
        return call()
    except GroupNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except GroupPermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/reports/overview", response_model=UserOverview)
def overview(user: CurrentUser, reports: ReportServiceDep) -> UserOverview:
    """FR-19: "you owe X, you are owed Y" across all groups."""
    return reports.user_overview(user)


@router.get("/groups/{group_id}/reports/balances", response_model=list[MemberBalance])
def balances(
    group_id: int, user: CurrentUser, reports: ReportServiceDep
) -> list[MemberBalance]:
    return _guarded(lambda: reports.member_balances(user, group_id))


@router.get("/groups/{group_id}/reports/categories", response_model=list[CategoryTotal])
def categories(
    group_id: int, user: CurrentUser, reports: ReportServiceDep
) -> list[CategoryTotal]:
    return _guarded(lambda: reports.category_totals(user, group_id))


@router.get("/groups/{group_id}/reports/monthly", response_model=list[MonthlyTotal])
def monthly(
    group_id: int, user: CurrentUser, reports: ReportServiceDep
) -> list[MonthlyTotal]:
    return _guarded(lambda: reports.monthly_totals(user, group_id))


@router.get("/groups/{group_id}/reports/top-payers", response_model=list[TopPayer])
def top_payers(
    group_id: int,
    user: CurrentUser,
    reports: ReportServiceDep,
    limit: int = Query(default=3, ge=1, le=50),
) -> list[TopPayer]:
    return _guarded(lambda: reports.top_payers(user, group_id, limit))


@router.get(
    "/groups/{group_id}/reports/inactive-members",
    response_model=list[InactiveMember],
)
def inactive_members(
    group_id: int, user: CurrentUser, reports: ReportServiceDep
) -> list[InactiveMember]:
    return _guarded(lambda: reports.inactive_members(user, group_id))


@router.get(
    "/groups/{group_id}/reports/above-average",
    response_model=list[ExpenseAboveAverage],
)
def above_average(
    group_id: int, user: CurrentUser, reports: ReportServiceDep
) -> list[ExpenseAboveAverage]:
    return _guarded(lambda: reports.above_average_expenses(user, group_id))


@router.get(
    "/groups/{group_id}/reports/running-total",
    response_model=list[RunningTotalRow],
)
def running_total(
    group_id: int, user: CurrentUser, reports: ReportServiceDep
) -> list[RunningTotalRow]:
    return _guarded(lambda: reports.running_total(user, group_id))
