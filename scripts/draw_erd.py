"""Draw docs/erd.png from the ORM metadata.

    poetry run python scripts/draw_erd.py

Tables, columns, keys and relationships are read from ``Base.metadata``, so the
diagram cannot drift away from the real schema; only box positions are fixed.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.infrastructure.database import Base
from app.repositories.sqlalchemy import orm_models  # noqa: F401

OUTPUT = ROOT / "docs" / "erd.png"

# Top-left corner of every table box.
POSITIONS = {
    "users": (70, 150),
    "groups": (1270, 150),
    "group_members": (670, 420),
    "notifications": (70, 760),
    "expense_shares": (380, 1110),
    "expenses": (900, 760),
    "settlements": (1330, 700),
}
WIDTH, HEIGHT = 1780, 1290
BOX_WIDTH = 380
ROW = 26
HEADER = 36

BACKGROUND = "#ffffff"
INK = "#1f2937"
MUTED = "#6b7280"
HEADER_FILL = "#1e3a5f"
LINK_TABLE_FILL = "#7c3aed"
BOX_FILL = "#f8fafc"
LINE = "#2563eb"
LABEL_FILL = "#eef2ff"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for path in (Path("C:/Windows/Fonts") / name, Path("/usr/share/fonts") / name):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


TITLE = font("arialbd.ttf", 30)
BOLD = font("arialbd.ttf", 18)
MONO = font("consola.ttf", 16)
SMALL = font("arial.ttf", 15)


def column_rows(table) -> list[tuple[str, str, str]]:
    """(marker, name, type) for each column."""
    unique = {
        c.name
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
        for c in constraint.columns
    }
    rows = []
    for column in table.columns:
        markers = []
        if column.primary_key:
            markers.append("PK")
        if column.foreign_keys or any(
            column.name in fk.column_keys for fk in table.foreign_key_constraints
        ):
            markers.append("FK")
        if column.name in unique:
            markers.append("UQ")
        type_name = str(column.type.compile())
        if column.nullable and not column.primary_key:
            type_name += " NULL"
        rows.append((",".join(markers), column.name, type_name))
    return rows


def box_of(name: str, table) -> tuple[int, int, int, int]:
    x, y = POSITIONS[name]
    return x, y, x + BOX_WIDTH, y + HEADER + ROW * len(table.columns) + 10


def border_point(box, toward) -> tuple[float, float]:
    """Point where the line from the box centre to ``toward`` leaves the box."""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    scale = min(
        (x2 - x1) / 2 / abs(dx) if dx else float("inf"),
        (y2 - y1) / 2 / abs(dy) if dy else float("inf"),
    )
    return cx + dx * scale, cy + dy * scale


def relationships(tables) -> dict[tuple[str, str], list[str]]:
    """(child, parent) -> FK descriptions; several FKs share one line."""
    links: dict[tuple[str, str], list[str]] = {}
    for name, table in tables.items():
        for fk in table.foreign_key_constraints:
            parent = fk.referred_table.name
            label = ", ".join(fk.column_keys) + f"  [{fk.ondelete or 'NO ACTION'}]"
            links.setdefault((name, parent), []).append(label)
    return links


def draw_label(draw, centre, lines, fill=LABEL_FILL) -> None:
    """Label box centred on ``centre``."""
    text = "\n".join(lines)
    left, top, right, bottom = draw.multiline_textbbox(
        centre, text, font=SMALL, anchor="mm"
    )
    pad = 4
    draw.rounded_rectangle(
        (left - pad, top - pad, right + pad, bottom + pad),
        radius=4,
        fill=fill,
        outline=LINE,
    )
    draw.multiline_text(centre, text, font=SMALL, fill=INK, anchor="mm", align="center")


def main() -> None:
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    missing = set(tables) - set(POSITIONS)
    if missing:
        raise SystemExit(f"Add a position for: {', '.join(sorted(missing))}")

    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((70, 40), "SplitEasy — ERD", font=TITLE, fill=INK)
    draw.text(
        (70, 85),
        "1 - N : bitta ota yozuvga ko'p bola yozuv.   users <-> groups M:N "
        "bog'lanishi group_members orqali.   [..] = ON DELETE qoidasi",
        font=SMALL,
        fill=MUTED,
    )

    boxes = {name: box_of(name, table) for name, table in tables.items()}

    # Lines first, so boxes are drawn over them.
    labels = []
    for (child, parent), descriptions in relationships(tables).items():
        child_box, parent_box = boxes[child], boxes[parent]
        child_centre = (
            (child_box[0] + child_box[2]) / 2,
            (child_box[1] + child_box[3]) / 2,
        )
        parent_centre = (
            (parent_box[0] + parent_box[2]) / 2,
            (parent_box[1] + parent_box[3]) / 2,
        )
        start = border_point(child_box, parent_centre)
        end = border_point(parent_box, child_centre)
        draw.line((start, end), fill=LINE, width=3)
        labels.append((start, end, descriptions))

    for name, table in tables.items():
        x1, y1, x2, y2 = boxes[name]
        is_link = name == "group_members"
        draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill=BOX_FILL, outline=INK)
        draw.rounded_rectangle(
            (x1, y1, x2, y1 + HEADER),
            radius=8,
            fill=LINK_TABLE_FILL if is_link else HEADER_FILL,
        )
        title = f"{name}  (M:N)" if is_link else name
        draw.text((x1 + 12, y1 + 8), title, font=BOLD, fill="white")
        for i, (marker, column, type_name) in enumerate(column_rows(table)):
            y = y1 + HEADER + 6 + i * ROW
            draw.text((x1 + 10, y), marker, font=MONO, fill="#b45309")
            draw.text((x1 + 80, y), column, font=MONO, fill=INK)
            draw.text((x1 + 240, y), type_name.lower(), font=MONO, fill=MUTED)

    # Cardinality marks and FK labels on top of everything.
    for start, end, descriptions in labels:
        for point, other, mark in ((start, end, "N"), (end, start, "1")):
            dx, dy = other[0] - point[0], other[1] - point[1]
            length = max((dx * dx + dy * dy) ** 0.5, 1)
            px, py = point[0] + dx / length * 22, point[1] + dy / length * 22
            draw.ellipse((px - 12, py - 12, px + 12, py + 12), fill=LINE)
            draw.text((px, py), mark, font=BOLD, fill="white", anchor="mm")
        middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        draw_label(draw, middle, descriptions)

    image.save(OUTPUT, optimize=True)
    print(f"Saved {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
