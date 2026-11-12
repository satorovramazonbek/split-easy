"""Group storage abstraction used by ``GroupService``."""

from datetime import datetime
from typing import Protocol

from app.domain.models import Group, GroupMember


class DuplicateMemberError(Exception):
    """The user is already a member of the group."""


class GroupRepository(Protocol):
    def add(self, group: Group) -> Group:
        """Persist a new group and return it with the assigned id."""

    def get_by_id(self, group_id: int) -> Group | None:
        """Return the group, including soft-deleted ones."""

    def list_for_user(self, user_id: int) -> list[Group]:
        """Active (not deleted) groups the user is a member of, newest first."""

    def mark_deleted(self, group_id: int) -> None: ...

    def add_member(self, member: GroupMember) -> GroupMember:
        """Add (or bring back a member who left).

        Raises ``DuplicateMemberError`` if the user is already an active member.
        """

    def remove_member(self, group_id: int, user_id: int, at: datetime) -> None:
        """Delete the membership, or mark it as left at ``at`` if the member has
        expenses, shares or settlements in the group (their history stays)."""

    def is_member(self, group_id: int, user_id: int) -> bool:
        """True only for active members (not those who left)."""

    def list_members(self, group_id: int) -> list[GroupMember]:
        """Active members in the order they joined."""
