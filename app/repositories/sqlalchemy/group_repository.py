"""SQLAlchemy implementation of ``GroupRepository``."""

from sqlalchemy import delete, exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Group, GroupMember
from app.repositories.interfaces.group_repository import (
    DuplicateMemberError,
    MemberHasRecordsError,
)
from app.repositories.sqlalchemy.orm_models import GroupMemberORM, GroupORM
from app.repositories.sqlalchemy.user_repository import as_utc


def _group(row: GroupORM) -> Group:
    return Group(
        id=row.id,
        name=row.name,
        currency=row.currency,
        owner_id=row.owner_id,
        is_deleted=row.is_deleted,
        created_at=as_utc(row.created_at),
    )


def _member(row: GroupMemberORM) -> GroupMember:
    return GroupMember(
        group_id=row.group_id, user_id=row.user_id, joined_at=as_utc(row.joined_at)
    )


class SqlAlchemyGroupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, group: Group) -> Group:
        row = GroupORM(
            name=group.name,
            currency=group.currency,
            owner_id=group.owner_id,
            is_deleted=group.is_deleted,
            created_at=group.created_at,
        )
        self._session.add(row)
        self._session.flush()
        return _group(row)

    def get_by_id(self, group_id: int) -> Group | None:
        row = self._session.get(GroupORM, group_id)
        return _group(row) if row else None

    def list_for_user(self, user_id: int) -> list[Group]:
        statement = (
            select(GroupORM)
            .join(GroupMemberORM, GroupMemberORM.group_id == GroupORM.id)
            .where(GroupMemberORM.user_id == user_id, GroupORM.is_deleted.is_(False))
            .order_by(GroupORM.created_at.desc(), GroupORM.id.desc())
        )
        return [_group(row) for row in self._session.scalars(statement)]

    def mark_deleted(self, group_id: int) -> None:
        self._session.execute(
            update(GroupORM).where(GroupORM.id == group_id).values(is_deleted=True)
        )

    def add_member(self, member: GroupMember) -> GroupMember:
        row = GroupMemberORM(
            group_id=member.group_id,
            user_id=member.user_id,
            joined_at=member.joined_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as error:
            raise DuplicateMemberError(str(error.orig)) from error
        return _member(row)

    def remove_member(self, group_id: int, user_id: int) -> None:
        try:
            with self._session.begin_nested():
                self._session.execute(
                    delete(GroupMemberORM).where(
                        GroupMemberORM.group_id == group_id,
                        GroupMemberORM.user_id == user_id,
                    )
                )
        except IntegrityError as error:
            # ON DELETE RESTRICT from expenses / settlements (composite FKs).
            raise MemberHasRecordsError(str(error.orig)) from error

    def is_member(self, group_id: int, user_id: int) -> bool:
        return self._session.scalar(
            select(
                exists().where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == user_id,
                )
            )
        )

    def list_members(self, group_id: int) -> list[GroupMember]:
        statement = (
            select(GroupMemberORM)
            .where(GroupMemberORM.group_id == group_id)
            .order_by(GroupMemberORM.joined_at, GroupMemberORM.user_id)
        )
        return [_member(row) for row in self._session.scalars(statement)]
