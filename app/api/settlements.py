"""Balances, settlement plan and payments of a group (FR-16 - FR-18)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import CurrentUser, SettlementServiceDep
from app.api.quick_split import MAX_AMOUNT
from app.domain.models import Settlement
from app.services.group_service import (
    GroupError,
    GroupNotFoundError,
    GroupPermissionError,
)
from app.services.settlement_service import (
    InvalidSettlementError,
    SettlementError,
    SettlementPermissionError,
)

router = APIRouter(prefix="/api/groups/{group_id}", tags=["settlements"])

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    InvalidSettlementError: status.HTTP_400_BAD_REQUEST,
    SettlementPermissionError: status.HTTP_403_FORBIDDEN,
    GroupPermissionError: status.HTTP_403_FORBIDDEN,
    GroupNotFoundError: status.HTTP_404_NOT_FOUND,
}


def _http_error(error: Exception) -> HTTPException:
    return HTTPException(_STATUS_BY_ERROR[type(error)], detail=str(error))


class BalanceOut(BaseModel):
    user_id: int
    username: str
    paid: int
    owed: int
    sent: int
    received: int
    balance: int


class TransferOut(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: int


class SettlementCreate(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: int = Field(gt=0, le=MAX_AMOUNT)


class SettlementOut(BaseModel):
    id: int
    group_id: int
    from_user_id: int
    to_user_id: int
    amount: int
    created_at: datetime

    @classmethod
    def from_domain(cls, s: Settlement) -> "SettlementOut":
        return cls(
            id=s.id,
            group_id=s.group_id,
            from_user_id=s.from_user_id,
            to_user_id=s.to_user_id,
            amount=s.amount,
            created_at=s.created_at,
        )


@router.get("/balances", response_model=list[BalanceOut])
def balances(
    group_id: int, user: CurrentUser, settlements: SettlementServiceDep
) -> list[BalanceOut]:
    """FR-16: positive - the group owes the member, negative - the member owes."""
    try:
        rows = settlements.balances(user, group_id)
    except GroupError as error:
        raise _http_error(error) from error
    return [BalanceOut(**row.__dict__) for row in rows]


@router.get("/settle-plan", response_model=list[TransferOut])
def settle_plan(
    group_id: int, user: CurrentUser, settlements: SettlementServiceDep
) -> list[TransferOut]:
    """FR-17: the fewest transfers that bring every balance to 0."""
    try:
        plan = settlements.settle_plan(user, group_id)
    except GroupError as error:
        raise _http_error(error) from error
    return [
        TransferOut(
            from_user_id=t.from_user_id, to_user_id=t.to_user_id, amount=t.amount
        )
        for t in plan
    ]


@router.post(
    "/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED
)
def record_settlement(
    group_id: int,
    request: SettlementCreate,
    user: CurrentUser,
    settlements: SettlementServiceDep,
) -> SettlementOut:
    """FR-18: mark a payment as done; it changes both balances."""
    try:
        settlement = settlements.record_settlement(
            user, group_id, request.from_user_id, request.to_user_id, request.amount
        )
    except (SettlementError, GroupError) as error:
        raise _http_error(error) from error
    return SettlementOut.from_domain(settlement)


@router.get("/settlements", response_model=list[SettlementOut])
def list_settlements(
    group_id: int, user: CurrentUser, settlements: SettlementServiceDep
) -> list[SettlementOut]:
    try:
        return [
            SettlementOut.from_domain(s)
            for s in settlements.list_settlements(user, group_id)
        ]
    except GroupError as error:
        raise _http_error(error) from error
