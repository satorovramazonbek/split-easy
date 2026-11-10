"""Expense storage, split into reader and writer (Interface Segregation).

A page that only lists expenses depends on ``ExpenseReader``; the expense
service that creates and edits them depends on ``ExpenseRepository`` (both).
"""

from typing import Protocol

from app.domain.models import Category, Expense


class ExpenseReader(Protocol):
    def get(self, expense_id: int) -> Expense | None:
        """The expense with all its shares."""

    def list_for_group(
        self,
        group_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        category: Category | None = None,
    ) -> list[Expense]:
        """Newest first (expense_date, then id), with shares, one page."""

    def count_for_group(self, group_id: int, category: Category | None = None) -> int:
        """Total for pagination."""


class ExpenseWriter(Protocol):
    def add(self, expense: Expense) -> Expense:
        """Store the expense and its shares; return it with the new id.

        Raises ``ReferenceIntegrityError`` if the payer is not a group member
        or a share belongs to an unknown user.
        """

    def replace(self, expense: Expense) -> Expense:
        """Update an existing expense; old shares are replaced by the new ones."""

    def delete(self, expense_id: int) -> None:
        """Remove the expense; its shares go with it (ON DELETE CASCADE)."""


class ExpenseRepository(ExpenseReader, ExpenseWriter, Protocol):
    """Full access, for the expense service."""
