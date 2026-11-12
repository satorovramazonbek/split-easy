"""CSV export (FR-24). Excel opens it directly; amounts are whole numbers."""

import csv
import io

from app.exporters.base import ExpenseRow

HEADER = [
    "sana",
    "tavsif",
    "kategoriya",
    "summa",
    "valyuta",
    "kim_tolagan",
    "bolish_usuli",
    "ulushlar",
]


class CsvExporter:
    content_type = "text/csv; charset=utf-8"
    file_extension = "csv"

    def export(self, rows: list[ExpenseRow]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow(
                [
                    row.expense_date.isoformat(),
                    row.description,
                    row.category,
                    row.amount,
                    row.currency,
                    row.paid_by,
                    row.split_type,
                    "; ".join(f"{s.username}: {s.share_amount}" for s in row.shares),
                ]
            )
        return buffer.getvalue()
