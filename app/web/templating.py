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


# Avatar colours: hues that read well as a pastel background with dark text.
# static/app.js has the same list and hash, so a name gets the same colour
# on every page.
AVATAR_HUES = [168, 199, 221, 262, 292, 338, 24, 43, 142, 186]


def avatar_hue(name: str) -> int:
    value = 0
    for char in name:
        value = (value * 31 + ord(char)) % 1_000_003
    return AVATAR_HUES[value % len(AVATAR_HUES)]


def initials(name: str) -> str:
    """'Ali Valiyev' -> 'AV', 'aziza_a' -> 'AA', 'Ali' -> 'AL'."""
    parts = [p for p in name.replace("_", " ").replace(".", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() if name else "?"


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
templates.env.filters["avatar_hue"] = avatar_hue
templates.env.filters["initials"] = initials
