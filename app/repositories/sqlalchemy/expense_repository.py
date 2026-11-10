"""SQLAlchemy implementation of ``ExpenseRepository``.

Lists load shares with ``selectinload``: one query for the page of expenses and
one ``... WHERE expense_id IN (...)`` for all their shares - two queries for any
page size instead of 1 + N (see docs/DB.md, section 6).
"""

from sqlalchemy import Select, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.models import Category, Expense, ExpenseShare, SplitType
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.sqlalchemy.orm_models import ExpenseORM, ExpenseShareORM
from app.repositories.sqlalchemy.user_repository import as_utc


def _to_domain(row: ExpenseORM) -> Expense:
    return Expense(
        id=row.id,
        group_id=row.group_id,
        description=row.description,
        amount=row.amount,
        paid_by=row.paid_by,
        split_type=SplitType(row.split_type),
        shares=tuple(ExpenseShare(s.user_id, s.share_amount) for s in row.shares),
        category=Category(row.category),
        expense_date=row.expense_date,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


def _columns(expense: Expense) -> dict:
    return {
        "group_id": expense.group_id,
        "description": expense.description,
        "amount": expense.amount,
        "paid_by": expense.paid_by,
        "category": expense.category.value,
        "split_type": expense.split_type.value,
        "expense_date": expense.expense_date,
        "created_by": expense.created_by,
        "created_at": expense.created_at,
    }


def _share_rows(expense_id: int, expense: Expense) -> list[dict]:
    return [
        {"expense_id": expense_id, "user_id": s.user_id, "share_amount": s.share_amount}
        for s in expense.shares
    ]


class SqlAlchemyExpenseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- reading -------------------------------------------------------------

    def _select(self) -> Select:
        return (
            select(ExpenseORM).options(selectinload(ExpenseORM.shares))
            # Rows changed with Core statements below must not come back stale
            # from the identity map.
            .execution_options(populate_existing=True)
        )

    def get(self, expense_id: int) -> Expense | None:
        row = self._session.scalars(
            self._select().where(ExpenseORM.id == expense_id)
        ).first()
        return _to_domain(row) if row else None

    def list_for_group(
        self,
        group_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        category: Category | None = None,
    ) -> list[Expense]:
        statement = self._select().where(ExpenseORM.group_id == group_id)
        if category is not None:
            statement = statement.where(ExpenseORM.category == category.value)
        statement = (
            statement.order_by(ExpenseORM.expense_date.desc(), ExpenseORM.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in self._session.scalars(statement)]

    def count_for_group(self, group_id: int, category: Category | None = None) -> int:
        statement = select(func.count()).where(ExpenseORM.group_id == group_id)
        if category is not None:
            statement = statement.where(ExpenseORM.category == category.value)
        return self._session.scalar(statement)

    # --- writing -------------------------------------------------------------

    def add(self, expense: Expense) -> Expense:
        try:
            with self._session.begin_nested():
                expense_id = self._session.execute(
                    insert(ExpenseORM).values(**_columns(expense))
                ).inserted_primary_key[0]
                self._session.execute(
                    insert(ExpenseShareORM), _share_rows(expense_id, expense)
                )
        except IntegrityError as error:
            raise ReferenceIntegrityError(str(error.orig)) from error
        return self.get(expense_id)

    def replace(self, expense: Expense) -> Expense:
        """Edit = update the row, delete old shares, insert new ones.

        Runs inside the caller's transaction (Unit of Work), so a failure in
        any step leaves the old expense and shares untouched.
        """
        if expense.id is None:
            raise ValueError("replace() needs an expense id")
        try:
            with self._session.begin_nested():
                updated = self._session.execute(
                    update(ExpenseORM)
                    .where(ExpenseORM.id == expense.id)
                    .values(**_columns(expense))
                ).rowcount
                if updated == 0:
                    raise LookupError(f"Expense {expense.id} does not exist")
                self._session.execute(
                    delete(ExpenseShareORM).where(
                        ExpenseShareORM.expense_id == expense.id
                    )
                )
                self._session.execute(
                    insert(ExpenseShareORM), _share_rows(expense.id, expense)
                )
        except IntegrityError as error:
            raise ReferenceIntegrityError(str(error.orig)) from error
        return self.get(expense.id)

    def delete(self, expense_id: int) -> None:
        self._session.execute(delete(ExpenseORM).where(ExpenseORM.id == expense_id))
