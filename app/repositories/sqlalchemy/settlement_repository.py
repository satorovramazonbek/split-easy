"""SQLAlchemy implementation of ``SettlementRepository``."""

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Settlement
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.sqlalchemy.orm_models import SettlementORM
from app.repositories.sqlalchemy.user_repository import as_utc


def _to_domain(row: SettlementORM) -> Settlement:
    return Settlement(
        id=row.id,
        group_id=row.group_id,
        from_user_id=row.from_user_id,
        to_user_id=row.to_user_id,
        amount=row.amount,
        created_at=as_utc(row.created_at),
    )


class SqlAlchemySettlementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, settlement: Settlement) -> Settlement:
        try:
            with self._session.begin_nested():
                new_id = self._session.execute(
                    insert(SettlementORM).values(
                        group_id=settlement.group_id,
                        from_user_id=settlement.from_user_id,
                        to_user_id=settlement.to_user_id,
                        amount=settlement.amount,
                        created_at=settlement.created_at,
                    )
                ).inserted_primary_key[0]
        except IntegrityError as error:
            raise ReferenceIntegrityError(str(error.orig)) from error
        return _to_domain(self._session.get(SettlementORM, new_id))

    def list_for_group(self, group_id: int) -> list[Settlement]:
        statement = (
            select(SettlementORM)
            .where(SettlementORM.group_id == group_id)
            .order_by(SettlementORM.created_at, SettlementORM.id)
        )
        return [_to_domain(row) for row in self._session.scalars(statement)]
