"""In-memory repositories for fast service-level unit tests."""

from collections.abc import Iterable
from dataclasses import replace

from app.domain.models import Group, GroupMember, User
from app.repositories.interfaces.group_repository import DuplicateMemberError


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    def add(self, user: User) -> User:
        stored = replace(user, id=len(self.users) + 1)
        self.users[stored.id] = stored
        return stored

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def get_many(self, user_ids: Iterable[int]) -> dict[int, User]:
        return {i: self.users[i] for i in user_ids if i in self.users}

    def get_by_username(self, username: str) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)


class InMemoryGroupRepository:
    def __init__(self) -> None:
        self.groups: dict[int, Group] = {}
        self.members: dict[tuple[int, int], GroupMember] = {}

    def add(self, group: Group) -> Group:
        stored = replace(group, id=len(self.groups) + 1)
        self.groups[stored.id] = stored
        return stored

    def get_by_id(self, group_id: int) -> Group | None:
        return self.groups.get(group_id)

    def list_for_user(self, user_id: int) -> list[Group]:
        return [
            g
            for g in reversed(self.groups.values())
            if not g.is_deleted and (g.id, user_id) in self.members
        ]

    def mark_deleted(self, group_id: int) -> None:
        self.groups[group_id] = replace(self.groups[group_id], is_deleted=True)

    def add_member(self, member: GroupMember) -> GroupMember:
        key = (member.group_id, member.user_id)
        if key in self.members:
            raise DuplicateMemberError(str(key))
        self.members[key] = member
        return member

    def remove_member(self, group_id: int, user_id: int) -> None:
        self.members.pop((group_id, user_id), None)

    def is_member(self, group_id: int, user_id: int) -> bool:
        return (group_id, user_id) in self.members

    def list_members(self, group_id: int) -> list[GroupMember]:
        return [m for (g, _), m in self.members.items() if g == group_id]
