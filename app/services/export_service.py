"""Exporting a group's expenses to a file (FR-24, FR-25).

The service collects the rows (with names) and asks ``ExporterFactory`` for the
format; it does not know how CSV or JSON is written (SRP, Open/Closed).
"""

from dataclasses import dataclass

from app.domain.models import User
from app.exporters.base import ExpenseRow, ShareRow
from app.exporters.factory import ExporterFactory
from app.services.expense_service import ExpenseService
from app.services.group_service import GroupService


@dataclass(frozen=True)
class ExportFile:
    filename: str
    content_type: str
    content: str


class ExportService:
    def __init__(self, expenses: ExpenseService, groups: GroupService) -> None:
        self._expenses = expenses
        self._groups = groups

    def export(self, user: User, group_id: int, format_name: str) -> ExportFile:
        exporter = ExporterFactory.create(format_name)  # unknown format -> error
        group = self._groups.get_group(user, group_id).group  # access check
        expenses = self._expenses.all_expenses(user, group_id)
        ids = {e.paid_by for e in expenses} | {
            s.user_id for e in expenses for s in e.shares
        }
        names = self._groups.usernames(ids)
        rows = [
            ExpenseRow(
                expense_date=e.expense_date,
                description=e.description,
                category=e.category.value,
                amount=e.amount,
                currency=group.currency,
                paid_by=names.get(e.paid_by, "?"),
                split_type=e.split_type.value,
                shares=tuple(
                    ShareRow(names.get(s.user_id, "?"), s.share_amount)
                    for s in e.shares
                ),
            )
            for e in expenses
        ]
        return ExportFile(
            filename=f"spliteasy-guruh-{group.id}.{exporter.file_extension}",
            content_type=exporter.content_type,
            content=exporter.export(rows),
        )
