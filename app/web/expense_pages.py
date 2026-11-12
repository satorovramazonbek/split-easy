"""Expense, settlement and export actions of the group page (FR-10 - FR-18, FR-24)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response
from starlette.datastructures import FormData

from app.api.dependencies import (
    ExpenseServiceDep,
    ExportServiceDep,
    GroupServiceDep,
    ReportServiceDep,
    SettlementServiceDep,
)
from app.domain.models import Category, Expense, SplitType
from app.domain.split_strategies import Participant
from app.exporters.factory import UnknownExportFormatError
from app.services.expense_service import (
    ExpenseData,
    ExpenseError,
    ExpenseNotFoundError,
    ExpensePermissionError,
)
from app.services.settlement_service import (
    SettlementError,
    SettlementPermissionError,
)
from app.web.common import PageUser, redirect, render
from app.web.group_pages import SPLIT_TYPES, group_page_response

router = APIRouter(include_in_schema=False)


# --- reading the expense form ------------------------------------------------------


def _int_or_none(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _decimal_or_none(value: object) -> Decimal | None:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


class FormError(Exception):
    """The form cannot even be turned into ``ExpenseData``."""


@dataclass
class ExpenseForm:
    """The raw form, kept to fill the fields again after an error."""

    description: str = ""
    amount: str = ""
    paid_by: int | None = None
    split_type: str = SplitType.EQUAL.value
    category: str = Category.OTHER.value
    expense_date: str = ""
    participants: set[int] = field(default_factory=set)
    share_values: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_form(cls, form: FormData) -> "ExpenseForm":
        chosen = [_int_or_none(v) for v in form.getlist("participants")]
        ids = [c for c in dict.fromkeys(chosen) if c is not None]
        return cls(
            description=str(form.get("description", "")),
            amount=str(form.get("amount", "")),
            paid_by=_int_or_none(form.get("paid_by")),
            split_type=str(form.get("split_type", SplitType.EQUAL.value)),
            category=str(form.get("category", Category.OTHER.value)),
            expense_date=str(form.get("expense_date", "")),
            participants=set(ids),
            share_values={i: str(form.get(f"value_{i}", "")).strip() for i in ids},
        )

    @classmethod
    def from_expense(cls, expense: Expense) -> "ExpenseForm":
        """Pre-filled edit form. Values are the stored shares as exact amounts."""
        return cls(
            description=expense.description,
            amount=str(expense.amount),
            paid_by=expense.paid_by,
            split_type=SplitType.EXACT.value,
            category=expense.category.value,
            expense_date=expense.expense_date.isoformat(),
            participants=set(expense.participant_ids),
            share_values={s.user_id: str(s.share_amount) for s in expense.shares},
        )

    def to_data(self) -> ExpenseData:
        amount = _int_or_none(self.amount)
        if amount is None or amount <= 0:
            raise FormError("Summani musbat butun son ko'rinishida kiriting")
        if self.paid_by is None:
            raise FormError("Kim to'laganini tanlang")
        try:
            expense_date = (
                date.fromisoformat(self.expense_date) if self.expense_date else None
            )
        except ValueError:
            raise FormError("Sana noto'g'ri") from None
        participants = []
        for user_id in sorted(self.participants):
            value = None
            if self.split_type != SplitType.EQUAL.value:
                value = _decimal_or_none(self.share_values.get(user_id))
                if value is None:
                    raise FormError(
                        "Har bir tanlangan ishtirokchi uchun qiymat kiriting"
                    )
            participants.append(Participant(user_id, value))
        return ExpenseData(
            description=self.description,
            amount=amount,
            paid_by=self.paid_by,
            split_type=self.split_type,
            category=self.category,
            expense_date=expense_date,
            participants=participants,
        )

    def as_context(self) -> dict[str, Any]:
        return self.__dict__


# --- add, edit, delete ----------------------------------------------------------------


@router.post("/groups/{group_id}/expenses", response_class=HTMLResponse)
async def add_expense(
    request: Request,
    group_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    reports: ReportServiceDep,
    expenses: ExpenseServiceDep,
    settlements: SettlementServiceDep,
) -> Response:
    form = ExpenseForm.from_form(await request.form())
    try:
        expenses.add_expense(user, group_id, form.to_data())
    except (FormError, ExpenseError) as error:
        return group_page_response(
            request,
            user,
            group_id,
            groups,
            reports,
            expenses,
            settlements,
            status_code=400,
            expense_error=str(error),
            expense_form=form.as_context(),
        )
    return redirect(f"/groups/{group_id}", "expense_added")


def _edit_page(
    request: Request,
    group_id: int,
    expense_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    form: ExpenseForm,
    status_code: int = 200,
    error: str | None = None,
) -> Response:
    details = groups.get_group(user, group_id)
    return render(
        request,
        "groups/expense_edit.html",
        status_code=status_code,
        user=user,
        group=details.group,
        members=details.members,
        expense_id=expense_id,
        expense_form=form.as_context(),
        expense_error=error,
        split_types=SPLIT_TYPES,
        categories_choice=[c.value for c in Category],
        today=date.today().isoformat(),
    )


@router.get(
    "/groups/{group_id}/expenses/{expense_id}/edit", response_class=HTMLResponse
)
def edit_expense_page(
    request: Request,
    group_id: int,
    expense_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    expenses: ExpenseServiceDep,
) -> Response:
    try:
        expense = expenses.get_expense(user, group_id, expense_id)
    except ExpenseNotFoundError:
        return redirect(f"/groups/{group_id}", "expense_not_found")
    return _edit_page(
        request, group_id, expense_id, user, groups, ExpenseForm.from_expense(expense)
    )


@router.post(
    "/groups/{group_id}/expenses/{expense_id}/edit", response_class=HTMLResponse
)
async def edit_expense_submit(
    request: Request,
    group_id: int,
    expense_id: int,
    user: PageUser,
    groups: GroupServiceDep,
    expenses: ExpenseServiceDep,
) -> Response:
    """FR-12: the author or the owner saves the edited expense."""
    form = ExpenseForm.from_form(await request.form())
    try:
        expenses.update_expense(user, group_id, expense_id, form.to_data())
    except ExpenseNotFoundError:
        return redirect(f"/groups/{group_id}", "expense_not_found")
    except ExpensePermissionError:
        return redirect(f"/groups/{group_id}", "expense_forbidden")
    except (FormError, ExpenseError) as error:
        return _edit_page(
            request, group_id, expense_id, user, groups, form, 400, str(error)
        )
    return redirect(f"/groups/{group_id}", "expense_updated")


@router.post("/groups/{group_id}/expenses/{expense_id}/delete")
def delete_expense(
    group_id: int, expense_id: int, user: PageUser, expenses: ExpenseServiceDep
) -> Response:
    try:
        expenses.delete_expense(user, group_id, expense_id)
    except ExpenseNotFoundError:
        return redirect(f"/groups/{group_id}", "expense_not_found")
    except ExpensePermissionError:
        return redirect(f"/groups/{group_id}", "expense_forbidden")
    return redirect(f"/groups/{group_id}", "expense_deleted")


# --- settlements and export ---------------------------------------------------------


@router.post("/groups/{group_id}/settlements")
def add_settlement(
    group_id: int,
    user: PageUser,
    settlements: SettlementServiceDep,
    from_user_id: Annotated[int, Form()],
    to_user_id: Annotated[int, Form()],
    amount: Annotated[int, Form()],
) -> Response:
    try:
        settlements.record_settlement(user, group_id, from_user_id, to_user_id, amount)
    except SettlementPermissionError:
        return redirect(f"/groups/{group_id}", "settlement_forbidden")
    except SettlementError:
        return redirect(f"/groups/{group_id}", "settlement_invalid")
    return redirect(f"/groups/{group_id}", "settlement_added")


@router.get("/groups/{group_id}/export")
def export_expenses(
    group_id: int, user: PageUser, exports: ExportServiceDep, format: str = "csv"
) -> Response:
    """FR-24: download the group's expenses as CSV (or JSON)."""
    try:
        file = exports.export(user, group_id, format)
    except UnknownExportFormatError:
        file = exports.export(user, group_id, "csv")
    return Response(
        content=file.content,
        media_type=file.content_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
