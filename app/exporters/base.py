"""The common interface of every export format and the rows it receives."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class ShareRow:
    username: str
    share_amount: int


@dataclass(frozen=True)
class ExpenseRow:
    """One expense, already with names instead of ids (ready to export)."""

    expense_date: date
    description: str
    category: str
    amount: int
    currency: str
    paid_by: str
    split_type: str
    shares: tuple[ShareRow, ...]


class Exporter(Protocol):
    """A format turns rows into text. CSV and JSON implement it; any new format
    (e.g. XLSX) is one more class registered in ``ExporterFactory``."""

    content_type: str
    file_extension: str

    def export(self, rows: list[ExpenseRow]) -> str: ...
