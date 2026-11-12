"""Group pages: my groups, create, the group page, members, delete (FR-5 - FR-9)."""

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, Response

from app.api.dependencies import (
    ExpenseServiceDep,
    GroupServiceDep,
    ReportServiceDep,
    SettlementServiceDep,
)
from app.domain.models import Category, User
from app.domain.settlement import Transfer
from app.services.expense_service import ExpenseService, InvalidExpenseError
from app.services.group_service import (
    AlreadyMemberError,
    GroupError,
    GroupNotFoundError,
    GroupPermissionError,
    GroupService,
    InvalidGroupError,
    MemberHasDebtError,
    MemberNotFoundError,
    OwnerCannotLeaveError,
    UserNotFoundError,
)
from app.services.report_service import ReportService
from app.services.settlement_service import SettlementService
from app.web.common import DEFAULT_PAGE, PageUser, redirect, render

router = APIRouter(include_in_schema=False)

EXPENSES_PER_PAGE = 20

SPLIT_TYPES = [
    ("equal", "Teng"),
    ("exact", "Aniq summalar"),
    ("percentage", "Foiz bo'yicha"),
    ("shares", "Ulushlar bo'yicha"),
]

# Group errors that are shown on the group page as a flash message.
GROUP_ERROR_FLASH: dict[type[GroupError], str] = {
    UserNotFoundError: "user_not_found",
    AlreadyMemberError: "already_member",
    MemberNotFoundError: "member_not_found",
    OwnerCannotLeaveError: "owner_cannot_leave",
    MemberHasDebtError: "member_has_debt",
    GroupPermissionError: "owner_only",
}


# --- my groups -----------------------------------------------------------------


def _groups_page(
    request: Request,
    user: User,
    groups: GroupService,
    reports: ReportService,
    status_code: int = 200,
    **extra: Any,
) -> Response:
    return render(
        request,
        "groups/list.html",
        status_code=status_code,
        user=user,
        groups=groups.list_groups(user),
        overview=reports.user_overview(user),
        **extra,
    )


@router.get("/groups", response_class=HTMLResponse)
def groups_page(
    request: Request, user: PageUser, groups: GroupServiceDep, reports: ReportServiceDep
) -> Response:
    return _groups_page(request, user, groups, reports)


@router.post("/groups", response_class=HTMLResponse)
def create_group(
    request: Request,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
    name: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "UZS",
) -> Response:
    try:
        details = groups.create_group(user, name, currency)
    except InvalidGroupError as error:
        return _groups_page(
            request,
            user,
            groups,
            reports,
            status_code=status.HTTP_400_BAD_REQUEST,
            error=str(error),
            form={"name": name, "currency": currency},
        )
    return redirect(f"/groups/{details.group.id}", "group_created")


# --- the group page ----------------------------------------------------------------


def group_page_response(
    request: Request,
    user: User,
    group_id: int,
    groups: GroupService,
    reports: ReportService,
    expenses: ExpenseService,
    settlements: SettlementService,
    *,
    page: int = 1,
    category: str | None = None,
    status_code: int = 200,
    **extra: Any,
) -> Response:
    """Everything the group page shows; also used to re-show it with an error."""
    details = groups.get_group(user, group_id)  # 404 / 403 -> error page
    balances = settlements.balances(user, group_id)
    transfers = settlements.settle_plan(user, group_id)  # FR-17
    try:
        expense_page = expenses.list_expenses(
            user, group_id, page=page, page_size=EXPENSES_PER_PAGE, category=category
        )
    except InvalidExpenseError:  # unknown ?category= -> show everything
        category = None
        expense_page = expenses.list_expenses(
            user, group_id, page=page, page_size=EXPENSES_PER_PAGE
        )
    history = settlements.list_settlements(user, group_id)
    # Names also for members who already left (their history stays visible).
    ids = {e.paid_by for e in expense_page.items}
    ids |= {s.user_id for e in expense_page.items for s in e.shares}
    ids |= {s.from_user_id for s in history} | {s.to_user_id for s in history}
    names = groups.usernames(ids)
    names.update({m.user_id: m.username for m in details.members})
    is_owner = details.group.owner_id == user.id

    def can_settle(transfer: Transfer) -> bool:
        """A party of the transfer or the owner may mark it as paid."""
        return is_owner or user.id in (transfer.from_user_id, transfer.to_user_id)

    categories = reports.category_totals(user, group_id)
    monthly = reports.monthly_totals(user, group_id)
    extra.setdefault("expense_form", {})
    return render(
        request,
        "groups/detail.html",
        status_code=status_code,
        user=user,
        group=details.group,
        members=details.members,
        is_owner=is_owner,
        balances=balances,
        balance_max=max((abs(b.balance) for b in balances), default=0),
        my_balance=next((b.balance for b in balances if b.user_id == user.id), 0),
        total_spent=sum(b.paid for b in balances),
        transfers=transfers,
        names=names,
        expenses=expense_page.items,
        expense_total=expense_page.total,
        page=expense_page.page,
        pages=expense_page.pages,
        category=category,
        settlements=list(reversed(history))[:20],
        can_settle=can_settle,
        split_types=SPLIT_TYPES,
        categories_choice=[c.value for c in Category],
        today=date.today().isoformat(),
        categories=categories,
        category_max=max((c.total for c in categories), default=0),
        monthly=monthly,
        monthly_max=max((m.total for m in monthly), default=0),
        top_payers=reports.top_payers(user, group_id),
        inactive=reports.inactive_members(user, group_id),
        above_average=reports.above_average_expenses(user, group_id),
        running=reports.running_total(user, group_id),
        **extra,
    )


@router.get("/groups/{group_id}", response_class=HTMLResponse)
def group_page(
    request: Request,
    group_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
    expenses: ExpenseServiceDep,
    settlements: SettlementServiceDep,
    page: int = 1,
    category: str | None = None,
) -> Response:
    return group_page_response(
        request,
        user,
        group_id,
        groups,
        reports,
        expenses,
        settlements,
        page=page,
        category=category or None,
    )


# --- members and delete ----------------------------------------------------------


def _group_action(
    group_id: int,
    action: Callable[[], object],
    success_msg: str,
    success_path: str | None = None,
) -> Response:
    try:
        action()
    except (GroupNotFoundError, InvalidGroupError):
        raise
    except GroupError as error:
        key = GROUP_ERROR_FLASH.get(type(error))
        if key is None:
            raise
        return redirect(f"/groups/{group_id}", key)
    return redirect(success_path or f"/groups/{group_id}", success_msg)


@router.post("/groups/{group_id}/members")
def add_member(
    group_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    login: Annotated[str, Form()] = "",
) -> Response:
    return _group_action(
        group_id, lambda: groups.add_member(user, group_id, login), "member_added"
    )


@router.post("/groups/{group_id}/members/{member_id}/remove")
def remove_member(
    group_id: int, member_id: int, user: PageUser, groups: GroupServiceDep
) -> Response:
    return _group_action(
        group_id,
        lambda: groups.remove_member(user, group_id, member_id),
        "member_removed",
    )


@router.post("/groups/{group_id}/delete")
def delete_group(group_id: int, user: PageUser, groups: GroupServiceDep) -> Response:
    return _group_action(
        group_id,
        lambda: groups.delete_group(user, group_id),
        "group_deleted",
        success_path=DEFAULT_PAGE,
    )
