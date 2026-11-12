"""Export formats and their factory (FR-24, FR-25, Factory pattern)."""

import csv
import io
import json
from datetime import date

import pytest

from app.exporters.base import ExpenseRow, ShareRow
from app.exporters.csv_exporter import CsvExporter
from app.exporters.factory import ExporterFactory, UnknownExportFormatError
from app.exporters.json_exporter import JsonExporter

ROWS = [
    ExpenseRow(
        expense_date=date(2026, 11, 1),
        description='Ovqat, "Rayhon"',
        category="food",
        amount=300_000,
        currency="UZS",
        paid_by="aziza",
        split_type="equal",
        shares=(ShareRow("aziza", 150_000), ShareRow("ramazon", 150_000)),
    )
]


def test_csv_has_header_and_quotes_commas() -> None:
    text = CsvExporter().export(ROWS)

    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][:4] == ["sana", "tavsif", "kategoriya", "summa"]
    assert rows[1][1] == 'Ovqat, "Rayhon"'  # read back exactly
    assert rows[1][3] == "300000"
    assert rows[1][7] == "aziza: 150000; ramazon: 150000"


def test_json_keeps_shares_as_a_list() -> None:
    data = json.loads(JsonExporter().export(ROWS))

    assert data[0]["amount"] == 300_000
    assert data[0]["shares"][1] == {"username": "ramazon", "share_amount": 150_000}


@pytest.mark.parametrize(
    ("name", "cls"), [("csv", CsvExporter), ("JSON", JsonExporter)]
)
def test_factory_creates_exporter_by_name(name: str, cls: type) -> None:
    assert isinstance(ExporterFactory.create(name), cls)


def test_factory_rejects_unknown_format() -> None:
    with pytest.raises(UnknownExportFormatError, match="xml"):
        ExporterFactory.create("xml")


def test_new_format_is_added_without_changing_existing_code(monkeypatch) -> None:
    """Open/Closed: a new format is one class + one register() call."""

    class TsvExporter:
        content_type = "text/tab-separated-values"
        file_extension = "tsv"

        def export(self, rows: list[ExpenseRow]) -> str:
            return "\n".join(f"{r.description}\t{r.amount}" for r in rows)

    monkeypatch.setattr(ExporterFactory, "_registry", dict(ExporterFactory._registry))
    ExporterFactory.register("tsv", TsvExporter)

    assert ExporterFactory.create("tsv").export(ROWS) == 'Ovqat, "Rayhon"\t300000'
    assert "tsv" in ExporterFactory.available_formats()
