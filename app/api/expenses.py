"""Group expense API: add, list, view, edit, delete (FR-10 - FR-14)."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.api.dependencies import CurrentUser, ExpenseServiceDep
from app.api.quick_split import (
    MAX_AMOUNT,
    MAX_DECIMAL_PLACES,
    MAX_MEMBERS,
    MAX_VALUE,
)
from app.domain.models import Category, Expense, SplitType
from app.domain.split_strategies import Participant
from app.services.expense_service import (
    DEFAULT_PAGE_SIZE,
    MAX_DESCRIPTION_LENGTH,
    MAX_PAGE_SIZE,
    ExpenseData,
    ExpenseError,
    ExpenseNotFoundError,
    ExpensePermissionError,
    InvalidExpenseError,
)
from app.services.group_service import (
    GroupError,
    GroupNotFoundError,
    GroupPermissionError,
)

router = APIRouter(prefix="/api/groups/{group_id}", tags=["expenses"])

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    InvalidExpenseError: status.HTTP_400_BAD_REQUEST,
    ExpensePermissionError: status.HTTP_403_FORBIDDEN,
    GroupPermissionError: status.HTTP_403_FORBIDDEN,
    ExpenseNotFoundError: status.HTTP_404_NOT_FOUND,
    GroupNotFoundError: status.HTTP_404_NOT_FOUND,
}


def _http_error(error: Exception) -> HTTPException:
    return HTTPException(_STATUS_BY_ERROR[type(error)], detail=str(error))


class ParticipantIn(BaseModel):
    user_id: int
    value: Decimal | None = Field(
        default=None,
        le=MAX_VALUE,
        decimal_places=MAX_DECIMAL_PLACES,
        description="Aniq summa, foiz yoki ulush (teng bo'lishda kerak emas)",
    )


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    paid_by: int
    split_type: SplitType = SplitType.EQUAL
    category: Category = Category.OTHER
    expense_date: date | None = None
    participants: list[ParticipantIn] = Field(min_length=1, max_length=MAX_MEMBERS)

    def to_data(self) -> ExpenseData:
        return ExpenseData(
            description=self.description,
            amount=self.amount,
            paid_by=self.paid_by,
            split_type=self.split_type.value,
            category=self.category.value,
            expense_date=self.expense_date,
            participants=[Participant(p.user_id, p.value) for p in self.participants],
        )


class ShareOut(BaseModel):
    user_id: int
    share_amount: int


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    description: str
    amount: int
    paid_by: int
    split_type: SplitType
    category: Category
    expense_date: date
    created_by: int | None
    created_at: datetime
    shares: list[ShareOut]

    @classmethod
    def from_domain(cls, e: Expense) -> "ExpenseOut":
        return cls(
            id=e.id,
            group_id=e.group_id,
            description=e.description,
            amount=e.amount,
            paid_by=e.paid_by,
            split_type=e.split_type,
            category=e.category,
            expense_date=e.expense_date,
            created_by=e.created_by,
            created_at=e.created_at,
            shares=[
                ShareOut(user_id=s.user_id, share_amount=s.share_amount)
                for s in e.shares
            ],
        )


class ExpenseList(BaseModel):
    items: list[ExpenseOut]
    total: int
    page: int
    page_size: int
    pages: int


@router.post(
    "/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED
)
def add_expense(
    group_id: int,
    request: ExpenseCreate,
    user: CurrentUser,
    expenses: ExpenseServiceDep,
) -> ExpenseOut:
    try:
        return ExpenseOut.from_domain(
            expenses.add_expense(user, group_id, request.to_data())
        )
    except (ExpenseError, GroupError) as error:
        raise _http_error(error) from error


@router.get("/expenses", response_model=ExpenseList)
def list_expenses(
    group_id: int,
    user: CurrentUser,
    expenses: ExpenseServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    category: Category | None = None,
) -> ExpenseList:
    """FR-13: newest first, paginated; FR-14: ``?category=food``."""
    try:
        result = expenses.list_expenses(
            user,
            group_id,
            page=page,
            page_size=page_size,
            category=category.value if category else None,
        )
    except (ExpenseError, GroupError) as error:
        raise _http_error(error) from error
    return ExpenseList(
        items=[ExpenseOut.from_domain(e) for e in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.get("/expenses/{expense_id}", response_model=ExpenseOut)
def get_expense(
    group_id: int, expense_id: int, user: CurrentUser, expenses: ExpenseServiceDep
) -> ExpenseOut:
    try:
        return ExpenseOut.from_domain(expenses.get_expense(user, group_id, expense_id))
    except (ExpenseError, GroupError) as error:
        raise _http_error(error) from error


@router.put("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(
    group_id: int,
    expense_id: int,
    request: ExpenseCreate,
    user: CurrentUser,
    expenses: ExpenseServiceDep,
) -> ExpenseOut:
    """FR-12: the author or the group owner edits; shares are recalculated."""
    try:
        return ExpenseOut.from_domain(
            expenses.update_expense(user, group_id, expense_id, request.to_data())
        )
    except (ExpenseError, GroupError) as error:
        raise _http_error(error) from error


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    group_id: int, expense_id: int, user: CurrentUser, expenses: ExpenseServiceDep
) -> Response:
    try:
        expenses.delete_expense(user, group_id, expense_id)
    except (ExpenseError, GroupError) as error:
        raise _http_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
