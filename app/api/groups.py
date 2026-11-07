"""Group API: create, list, view, delete groups and manage members."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.dependencies import CurrentUser, GroupServiceDep
from app.domain.models import Group
from app.services.group_service import (
    AlreadyMemberError,
    GroupDetails,
    GroupError,
    GroupNotFoundError,
    GroupPermissionError,
    InvalidGroupError,
    MemberNotFoundError,
    OwnerCannotLeaveError,
    UserNotFoundError,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])

_STATUS_BY_ERROR: dict[type[GroupError], int] = {
    InvalidGroupError: status.HTTP_400_BAD_REQUEST,
    GroupPermissionError: status.HTTP_403_FORBIDDEN,
    GroupNotFoundError: status.HTTP_404_NOT_FOUND,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    MemberNotFoundError: status.HTTP_404_NOT_FOUND,
    AlreadyMemberError: status.HTTP_409_CONFLICT,
    OwnerCannotLeaveError: status.HTTP_409_CONFLICT,
}


def _http_error(error: GroupError) -> HTTPException:
    return HTTPException(_STATUS_BY_ERROR[type(error)], detail=str(error))


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="UZS", pattern=r"^[A-Za-z]{3}$")


class MemberAdd(BaseModel):
    login: str = Field(
        min_length=3, max_length=254, description="Foydalanuvchi nomi yoki email"
    )


class GroupSummary(BaseModel):
    id: int
    name: str
    currency: str
    owner_id: int
    created_at: datetime

    @classmethod
    def from_domain(cls, group: Group) -> "GroupSummary":
        return cls(
            id=group.id,
            name=group.name,
            currency=group.currency,
            owner_id=group.owner_id,
            created_at=group.created_at,
        )


class MemberOut(BaseModel):
    user_id: int
    username: str
    joined_at: datetime
    is_owner: bool


class GroupOut(GroupSummary):
    members: list[MemberOut]

    @classmethod
    def from_details(cls, details: GroupDetails) -> "GroupOut":
        return cls(
            **GroupSummary.from_domain(details.group).model_dump(),
            members=[
                MemberOut(
                    user_id=m.user_id,
                    username=m.username,
                    joined_at=m.joined_at,
                    is_owner=m.is_owner,
                )
                for m in details.members
            ],
        )


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    request: GroupCreate, user: CurrentUser, groups: GroupServiceDep
) -> GroupOut:
    try:
        details = groups.create_group(user, request.name, request.currency)
    except GroupError as error:
        raise _http_error(error) from error
    return GroupOut.from_details(details)


@router.get("", response_model=list[GroupSummary])
def list_groups(user: CurrentUser, groups: GroupServiceDep) -> list[GroupSummary]:
    return [GroupSummary.from_domain(g) for g in groups.list_groups(user)]


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group_id: int, user: CurrentUser, groups: GroupServiceDep) -> GroupOut:
    try:
        return GroupOut.from_details(groups.get_group(user, group_id))
    except GroupError as error:
        raise _http_error(error) from error


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, user: CurrentUser, groups: GroupServiceDep) -> Response:
    try:
        groups.delete_group(user, group_id)
    except GroupError as error:
        raise _http_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{group_id}/members",
    response_model=GroupOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    group_id: int, request: MemberAdd, user: CurrentUser, groups: GroupServiceDep
) -> GroupOut:
    try:
        return GroupOut.from_details(groups.add_member(user, group_id, request.login))
    except GroupError as error:
        raise _http_error(error) from error


@router.delete(
    "/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    group_id: int, member_id: int, user: CurrentUser, groups: GroupServiceDep
) -> Response:
    """Owner removes anyone; a member can remove only themselves (leave)."""
    try:
        groups.remove_member(user, group_id, member_id)
    except GroupError as error:
        raise _http_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
