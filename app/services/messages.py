"""User-facing Uzbek texts for domain errors.

Domain errors are in English (they are also returned by the JSON quick split
and checked by tests). Services that talk to people show them in Uzbek; the
translation lives here, in one place, instead of inside every service.
"""

import re
from collections.abc import Callable

_UZ_ERRORS: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str]]] = [
    (
        re.compile(r"Exact amounts sum \((\d+)\) must equal total \((\d+)\)"),
        lambda m: f"Aniq summalar yig'indisi ({m[1]}) umumiy summaga ({m[2]}) "
        "teng bo'lishi kerak",
    ),
    (
        re.compile(r"Percentages must add up to 100, got (.+)"),
        lambda m: f"Foizlar yig'indisi 100 bo'lishi kerak (hozir: {m[1]})",
    ),
    (
        re.compile(r"Exact amounts must be whole numbers|Exact split requires integer"),
        lambda m: "Aniq summalar butun son bo'lishi kerak",
    ),
    (
        re.compile(r"Exact amounts cannot be negative"),
        lambda m: "Summa manfiy bo'lishi mumkin emas",
    ),
    (
        re.compile(r"(Percentage|Share) must be positive"),
        lambda m: "Har bir ishtirokchi uchun musbat qiymat kiriting",
    ),
    (
        re.compile(r"(Percentage|Share) must be an integer or Decimal"),
        lambda m: "Har bir tanlangan ishtirokchi uchun qiymat kiriting",
    ),
    (re.compile(r"Amount must be"), lambda m: "Summa musbat butun son bo'lishi kerak"),
    (
        re.compile(r"at least one participant|At least one participant"),
        lambda m: "Kamida bitta ishtirokchini tanlang",
    ),
    (
        re.compile(r"only once"),
        lambda m: "Har bir ishtirokchi faqat bir marta tanlanadi",
    ),
    (re.compile(r"Unknown split type"), lambda m: "Bo'lish usuli noto'g'ri"),
    (re.compile(r"themselves"), lambda m: "O'zingizga to'lov qilib bo'lmaydi"),
]


def translate_error(message: str) -> str:
    """English domain error -> Uzbek text; unknown messages are returned as is."""
    for pattern, render in _UZ_ERRORS:
        match = pattern.search(message)
        if match:
            return render(match)
    return message
