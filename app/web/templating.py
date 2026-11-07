"""Shared Jinja2 environment for all HTML pages."""

from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

CATEGORY_LABELS = {
    "food": "🍽 Ovqat",
    "transport": "🚕 Transport",
    "accommodation": "🏨 Turar joy",
    "other": "📦 Boshqa",
}

MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]  # fmt: skip


def money(amount: float | None, currency: str = "so'm") -> str:
    """1250000 -> '1 250 000 so'm' (whole numbers, non-breaking spaces)."""
    value = round(amount or 0)
    text = f"{abs(value):,}".replace(",", "\u00a0")
    return f"{'-' if value < 0 else ''}{text}\u00a0{currency}"


def category_label(value: str) -> str:
    return CATEGORY_LABELS.get(value, value)


def month_label(value: str) -> str:
    """'2026-10' -> 'oktabr 2026'."""
    year, month = value.split("-")
    return f"{MONTHS[int(month) - 1]} {year}"


def human_date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


templates.env.filters["money"] = money
templates.env.filters["category"] = category_label
templates.env.filters["month"] = month_label
templates.env.filters["human_date"] = human_date
