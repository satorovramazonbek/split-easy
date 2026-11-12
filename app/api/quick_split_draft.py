"""Saved quick split page of the signed-in user.

Guests keep the page in browser memory only. Signed-in users' pages call these
endpoints (with the login cookie) after every change; API clients can use the
Bearer token as well.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.dependencies import DraftServiceDep, PageOrApiUser
from app.api.quick_split import MAX_AMOUNT, MAX_EXPENSES, MAX_MEMBERS
from app.domain.models import SplitType
from app.services.quick_split_draft_service import InvalidDraftError

router = APIRouter(prefix="/api/quick-split", tags=["quick-split"])

MAX_ID = 10**9


class DraftParticipant(BaseModel):
    id: int = Field(ge=1, le=MAX_ID)
    name: str = Field(min_length=1, max_length=20)


class DraftExpenseParticipant(BaseModel):
    user_id: int = Field(ge=1, le=MAX_ID)
    value: str | None = Field(default=None, max_length=30)


class DraftShare(BaseModel):
    user_id: int = Field(ge=1, le=MAX_ID)
    share_amount: int = Field(ge=0, le=MAX_AMOUNT)


class DraftExpense(BaseModel):
    id: int = Field(ge=1, le=MAX_ID)
    description: str = Field(max_length=100)
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    paid_by: int = Field(ge=1, le=MAX_ID)
    split_type: SplitType
    participants: list[DraftExpenseParticipant] = Field(
        min_length=1, max_length=MAX_MEMBERS
    )
    shares: list[DraftShare] = Field(min_length=1, max_length=MAX_MEMBERS)


class DraftIn(BaseModel):
    participants: list[DraftParticipant] = Field(default=[], max_length=MAX_MEMBERS)
    expenses: list[DraftExpense] = Field(default=[], max_length=MAX_EXPENSES)


class DraftOut(DraftIn):
    updated_at: datetime | None = None


@router.get("/draft", response_model=DraftOut)
def get_draft(user: PageOrApiUser, drafts: DraftServiceDep) -> DraftOut:
    draft = drafts.get(user)
    if draft is None:
        return DraftOut()
    return DraftOut(**draft.data, updated_at=draft.updated_at)


@router.put("/draft", response_model=DraftOut)
def save_draft(
    request: DraftIn, user: PageOrApiUser, drafts: DraftServiceDep
) -> DraftOut:
    try:
        draft = drafts.save(user, request.model_dump(mode="json"))
    except InvalidDraftError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return DraftOut(**draft.data, updated_at=draft.updated_at)


@router.delete("/draft", status_code=status.HTTP_204_NO_CONTENT)
def clear_draft(user: PageOrApiUser, drafts: DraftServiceDep) -> Response:
    drafts.clear(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
