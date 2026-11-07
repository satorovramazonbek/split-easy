"""Stateless API for the quick split page (no auth, no database)."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.exceptions import DomainError
from app.domain.split_strategies import Participant
from app.services.quick_split_service import ExpenseInput, QuickSplitService

router = APIRouter(prefix="/api", tags=["quick-split"])
service = QuickSplitService()

MAX_MEMBERS = 50
MAX_EXPENSES = 500


class ParticipantIn(BaseModel):
    user_id: int
    value: Decimal | None = None


class ExpenseIn(BaseModel):
    description: str = Field(default="", max_length=100)
    amount: int
    paid_by: int
    split_type: str = "equal"
    participants: list[ParticipantIn] = Field(max_length=MAX_MEMBERS)

    def to_input(self) -> ExpenseInput:
        return ExpenseInput(
            description=self.description,
            amount=self.amount,
            paid_by=self.paid_by,
            split_type=self.split_type,
            participants=[Participant(p.user_id, p.value) for p in self.participants],
        )


class PreviewRequest(BaseModel):
    members: list[int] = Field(max_length=MAX_MEMBERS)
    expense: ExpenseIn


class CalculateRequest(BaseModel):
    members: list[int] = Field(max_length=MAX_MEMBERS)
    expenses: list[ExpenseIn] = Field(max_length=MAX_EXPENSES)


class ShareOut(BaseModel):
    user_id: int
    share_amount: int


class PreviewResponse(BaseModel):
    shares: list[ShareOut]


class MemberSummary(BaseModel):
    user_id: int
    paid: int
    owed: int
    balance: int


class TransferOut(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: int


class CalculateResponse(BaseModel):
    total: int
    members: list[MemberSummary]
    transfers: list[TransferOut]


@router.post("/expenses/preview", response_model=PreviewResponse)
def preview_expense(request: PreviewRequest) -> PreviewResponse:
    """Validate one expense and return how it is split."""
    try:
        expense = service.build_expense(request.members, request.expense.to_input())
    except DomainError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return PreviewResponse(
        shares=[
            ShareOut(user_id=s.user_id, share_amount=s.share_amount)
            for s in expense.shares
        ]
    )


@router.post("/calculate", response_model=CalculateResponse)
def calculate(request: CalculateRequest) -> CalculateResponse:
    """Return balances and the minimal settlement plan."""
    try:
        result = service.calculate(
            request.members, [expense.to_input() for expense in request.expenses]
        )
    except DomainError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return CalculateResponse(
        total=result.total,
        members=[
            MemberSummary(
                user_id=user_id,
                paid=result.paid[user_id],
                owed=result.owed[user_id],
                balance=result.balances[user_id],
            )
            for user_id in request.members
        ],
        transfers=[
            TransferOut(
                from_user_id=t.from_user_id, to_user_id=t.to_user_id, amount=t.amount
            )
            for t in result.transfers
        ],
    )
