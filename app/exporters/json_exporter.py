"""JSON export (FR-25): the same rows, with shares as a list."""

import json

from app.exporters.base import ExpenseRow


class JsonExporter:
    content_type = "application/json"
    file_extension = "json"

    def export(self, rows: list[ExpenseRow]) -> str:
        data = [
            {
                "expense_date": row.expense_date.isoformat(),
                "description": row.description,
                "category": row.category,
                "amount": row.amount,
                "currency": row.currency,
                "paid_by": row.paid_by,
                "split_type": row.split_type,
                "shares": [
                    {"username": s.username, "share_amount": s.share_amount}
                    for s in row.shares
                ],
            }
            for row in rows
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)
