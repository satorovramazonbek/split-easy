"""Group storage abstraction used by ``GroupService``."""

from typing import Protocol

from app.domain.models import Group, GroupMember


class DuplicateMemberError(Exception):
    """The user is already a member of the group."""


class MemberHasRecordsError(Exception):
    """The member paid an expense, has a share in one or took part in a
    settlement in this group."""


class GroupRepository(Protocol):
    def add(self, group: Group) -> Group:
        """Persist a new group and return it with the assigned id."""

    def get_by_id(self, group_id: int) -> Group | None:
        """Return the group, including soft-deleted ones."""

    def list_for_user(self, user_id: int) -> list[Group]:
        """Active (not deleted) groups the user is a member of, newest first."""

    def mark_deleted(self, group_id: int) -> None: ...

    def add_member(self, member: GroupMember) -> GroupMember:
        """Raises ``DuplicateMemberError`` if the user is already a member."""

    def remove_member(self, group_id: int, user_id: int) -> None:
        """Raises ``MemberHasRecordsError`` if the member has financial history."""

    def is_member(self, group_id: int, user_id: int) -> bool: ...

    def list_members(self, group_id: int) -> list[GroupMember]:
        """Members in the order they joined."""
