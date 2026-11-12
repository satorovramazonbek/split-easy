"""SQLAlchemy implementation of ``GroupRepository``."""

from datetime import datetime

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Group, GroupMember
from app.repositories.interfaces.group_repository import DuplicateMemberError
from app.repositories.sqlalchemy.orm_models import (
    ExpenseORM,
    ExpenseShareORM,
    GroupMemberORM,
    GroupORM,
    SettlementORM,
)

ACTIVE = GroupMemberORM.left_at.is_(None)
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
            .where(
                GroupMemberORM.user_id == user_id,
                ACTIVE,
                GroupORM.is_deleted.is_(False),
            )
            .order_by(GroupORM.created_at.desc(), GroupORM.id.desc())
        )
        return [_group(row) for row in self._session.scalars(statement)]

    def mark_deleted(self, group_id: int) -> None:
        self._session.execute(
            update(GroupORM).where(GroupORM.id == group_id).values(is_deleted=True)
        )

    def add_member(self, member: GroupMember) -> GroupMember:
        row = self._session.get(
            GroupMemberORM, (member.group_id, member.user_id), populate_existing=True
        )
        if row is not None:
            if row.left_at is None:
                raise DuplicateMemberError(f"{member.user_id} in {member.group_id}")
            row.left_at = None  # the member who left comes back
            row.joined_at = member.joined_at
            self._session.flush()
            return _member(row)
        row = GroupMemberORM(
            group_id=member.group_id,
            user_id=member.user_id,
            joined_at=member.joined_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as error:  # lost a race with a parallel request
            raise DuplicateMemberError(str(error.orig)) from error
        return _member(row)

    def remove_member(self, group_id: int, user_id: int, at: datetime) -> None:
        member = (GroupMemberORM.group_id == group_id) & (
            GroupMemberORM.user_id == user_id
        )
        if self._has_history(group_id, user_id):
            # Expenses and settlements point to this row: keep it, mark as left.
            self._session.execute(
                update(GroupMemberORM).where(member).values(left_at=at)
            )
        else:
            self._session.execute(delete(GroupMemberORM).where(member))

    def _has_history(self, group_id: int, user_id: int) -> bool:
        paid_or_shared = (
            exists()
            .where(ExpenseORM.group_id == group_id)
            .where(
                or_(
                    ExpenseORM.paid_by == user_id,
                    exists().where(
                        ExpenseShareORM.expense_id == ExpenseORM.id,
                        ExpenseShareORM.user_id == user_id,
                    ),
                )
            )
        )
        settled = exists().where(
            SettlementORM.group_id == group_id,
            or_(
                SettlementORM.from_user_id == user_id,
                SettlementORM.to_user_id == user_id,
            ),
        )
        return bool(self._session.scalar(select(paid_or_shared | settled)))

    def is_member(self, group_id: int, user_id: int) -> bool:
        return self._session.scalar(
            select(
                exists().where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == user_id,
                    ACTIVE,
                )
            )
        )

    def list_members(self, group_id: int) -> list[GroupMember]:
        statement = (
            select(GroupMemberORM)
            .where(GroupMemberORM.group_id == group_id, ACTIVE)
            .order_by(GroupMemberORM.joined_at, GroupMemberORM.user_id)
        )
        return [_member(row) for row in self._session.scalars(statement)]
