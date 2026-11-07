"""Groups: create, view, delete, add and remove members.

Access rules (technical specification, section 11):
- a missing or deleted group -> GroupNotFoundError (404);
- a user who is not a member -> GroupPermissionError (403);
- only the owner adds members, removes members and deletes the group;
- the owner cannot be removed; the owner deletes the group instead (soft delete).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.models import Group, GroupMember, User
from app.repositories.interfaces.group_repository import (
    DuplicateMemberError,
    GroupRepository,
    MemberHasRecordsError,
)
from app.repositories.interfaces.user_repository import UserRepository

MAX_NAME_LENGTH = 100
DEFAULT_CURRENCY = "UZS"
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class GroupError(Exception):
    """Base class for group errors."""


class InvalidGroupError(GroupError):
    """Name or currency is invalid."""


class GroupNotFoundError(GroupError):
    """The group does not exist or is deleted."""


class GroupPermissionError(GroupError):
    """The user is not a member, or not the owner for owner-only actions."""


class UserNotFoundError(GroupError):
    """No user with the given username or email."""


class AlreadyMemberError(GroupError):
    """The user is already in the group."""


class MemberNotFoundError(GroupError):
    """The user is not in the group."""


class OwnerCannotLeaveError(GroupError):
    """The owner must delete the group instead of leaving it."""


class MemberHasHistoryError(GroupError):
    """The member has expenses or settlements in the group."""


@dataclass(frozen=True)
class MemberInfo:
    user_id: int
    username: str
    joined_at: datetime
    is_owner: bool


@dataclass(frozen=True)
class GroupDetails:
    group: Group
    members: list[MemberInfo]


class GroupService:
    def __init__(
        self,
        groups: GroupRepository,
        users: UserRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._groups = groups
        self._users = users
        self._clock = clock

    def create_group(
        self, owner: User, name: str, currency: str = DEFAULT_CURRENCY
    ) -> GroupDetails:
        name = name.strip()
        currency = currency.strip().upper()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise InvalidGroupError(
                f"Guruh nomi 1–{MAX_NAME_LENGTH} belgidan iborat bo'lishi kerak"
            )
        if not _CURRENCY_RE.match(currency):
            raise InvalidGroupError("Valyuta 3 harfli kod bo'lishi kerak (UZS, USD)")

        now = self._clock()
        group = self._groups.add(
            Group(
                id=None,
                name=name,
                currency=currency,
                owner_id=owner.id,
                created_at=now,
            )
        )
        self._groups.add_member(
            GroupMember(group_id=group.id, user_id=owner.id, joined_at=now)
        )
        return self._details(group)

    def list_groups(self, user: User) -> list[Group]:
        return self._groups.list_for_user(user.id)

    def get_group(self, user: User, group_id: int) -> GroupDetails:
        return self._details(self._member_group(user, group_id))

    def delete_group(self, user: User, group_id: int) -> None:
        group = self._owned_group(user, group_id, "Guruhni faqat egasi o'chira oladi")
        self._groups.mark_deleted(group.id)

    def add_member(self, user: User, group_id: int, login: str) -> GroupDetails:
        group = self._owned_group(
            user, group_id, "A'zoni faqat guruh egasi qo'sha oladi"
        )
        new_member = self._find_user(login)
        if new_member is None:
            raise UserNotFoundError("Bunday foydalanuvchi topilmadi")
        try:
            self._groups.add_member(
                GroupMember(
                    group_id=group.id, user_id=new_member.id, joined_at=self._clock()
                )
            )
        except DuplicateMemberError as error:
            raise AlreadyMemberError("Foydalanuvchi allaqachon guruhda") from error
        return self._details(group)

    def remove_member(self, user: User, group_id: int, member_id: int) -> None:
        group = self._owned_group(
            user, group_id, "A'zoni faqat guruh egasi chiqara oladi"
        )
        if member_id == group.owner_id:
            raise OwnerCannotLeaveError(
                "Guruh egasini chiqarib bo'lmaydi; guruhni o'chiring"
            )
        if not self._groups.is_member(group.id, member_id):
            raise MemberNotFoundError("Bu foydalanuvchi guruhda emas")
        # TODO: when the expense service exists, also refuse a member who only
        # appears in expense shares (the database guards payers and settlements).
        try:
            self._groups.remove_member(group.id, member_id)
        except MemberHasRecordsError as error:
            raise MemberHasHistoryError(
                "A'zoning guruhda xarajat yoki to'lovlari bor, uni chiqarib bo'lmaydi"
            ) from error

    def _member_group(self, user: User, group_id: int) -> Group:
        group = self._groups.get_by_id(group_id)
        if group is None or group.is_deleted:
            raise GroupNotFoundError("Guruh topilmadi")
        if not self._groups.is_member(group_id, user.id):
            raise GroupPermissionError("Siz bu guruh a'zosi emassiz")
        return group

    def _owned_group(self, user: User, group_id: int, message: str) -> Group:
        group = self._member_group(user, group_id)
        if group.owner_id != user.id:
            raise GroupPermissionError(message)
        return group

    def _find_user(self, login: str) -> User | None:
        login = login.strip().lower()
        if "@" in login:
            return self._users.get_by_email(login)
        return self._users.get_by_username(login)

    def _details(self, group: Group) -> GroupDetails:
        members = self._groups.list_members(group.id)
        users = self._users.get_many(m.user_id for m in members)
        return GroupDetails(
            group=group,
            members=[
                MemberInfo(
                    user_id=m.user_id,
                    username=users[m.user_id].username,
                    joined_at=m.joined_at,
                    is_owner=m.user_id == group.owner_id,
                )
                for m in members
            ],
        )
