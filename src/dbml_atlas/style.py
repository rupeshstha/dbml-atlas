from __future__ import annotations

import sys
from collections import Counter, OrderedDict

from .model import Schema

# ─────────────────────────────────────────────────────────────────────────────
# Palettes (sampled from the Magento 1.3 poster)
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIES = OrderedDict([
    ("reference_static",  ("#ffff00", "Reference Tables [Static]")),
    ("reference_dynamic", ("#ffffb3", "Reference Tables [Dynamic]")),
    ("entity",            ("#ffb3a7", "Entity Tables")),
    ("entity_detail",     ("#ffe0e0", "Entity Detail Tables")),
    ("important",         ("#99ff99", '"Important" Tables')),
    ("cross_reference",   ("#ccffff", "Cross-Reference Tables")),
    ("other",             ("#ffffff", "Other Tables")),
])
CATEGORY_ALIASES: dict[str, str] = {
    "reference": "reference_static", "static": "reference_static", "lookup": "reference_static",
    "dynamic": "reference_dynamic", "config": "reference_dynamic",
    "detail": "entity_detail", "eav": "entity_detail",
    "pivot": "cross_reference", "xref": "cross_reference", "junction": "cross_reference",
    "core": "important", "key": "important",
}
AREA_PALETTE = ["#777777", "#3a6e6a", "#7d3b3b", "#7d7a3b", "#44508a",
                "#5b3f7a", "#8a5a2b", "#2f5f8a", "#6a6a3a", "#3f6f3f"]
HUB_PALETTE = ["#0000ff", "#ff0000", "#4f4520", "#ff8000", "#004d26", "#ff1080",
               "#800080", "#e6c000", "#ff88cc", "#00cc00", "#00a0a0", "#a05000"]
DEFAULT_EDGE = "#000000"
TYPE_COLOR, NOTNULL_COLOR = "#0000cc", "#cc0000"
SANS = "Helvetica, Arial, sans-serif"
SERIF = "'Times New Roman', Times, serif"

# ─────────────────────────────────────────────────────────────────────────────
# Text metrics — Helvetica/Arial advance widths (1/1000 em)
# ─────────────────────────────────────────────────────────────────────────────
_W: dict[str, int] = {}
for _chars, _w in [
    ("abdeghnopqu0123456789_$#", 556), ("ckszvxy", 500), ("fjt", 278), ("il", 222),
    ("m", 833), ("r", 333), ("w", 722), ("ABEKPSVXY", 667), ("CDHNRUw", 722),
    ("GOQ", 778), ("FTZ", 611), ("IJ", 278), ("L", 556), ("M", 833), ("W", 944),
    (" ,.:;'/!|[]", 278), ("()-", 333), ('"', 355), ("&", 667), ("<>=+", 584),
]:
    for _ch in _chars:
        _W.setdefault(_ch, _w)
_W["J"] = 500


def text_w(s: str, size: float, bold: bool = False) -> float:
    return sum(_W.get(ch, 600) for ch in str(s)) / 1000 * size * (1.08 if bold else 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ─────────────────────────────────────────────────────────────────────────────
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(h: str, other: str = "#ffffff", t: float = 0.5) -> str:
    a, b = _rgb(h), _rgb(other)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def luminance(h: str) -> float:
    r, g, b = (c / 255 for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def shade(c: str, depth: int) -> str:
    return c if depth == 0 else mix(c, "#ffffff", (0.35, 0.6, 0.75, 0.85)[min(depth - 1, 3)])


# ─────────────────────────────────────────────────────────────────────────────
# Styling decisions — assign areas, categories, hubs
# ─────────────────────────────────────────────────────────────────────────────
def resolve(sc: Schema, n_hubs: int) -> tuple[list[str], dict[str, str], OrderedDict]:
    areas: list[str] = []
    for path in sc.groups:
        if path and path[0] not in areas:
            areas.append(path[0])
    grouped: set[str] = set()
    for path, ts in sc.groups.items():
        for t in ts:
            if t in sc.tables and t not in grouped:
                grouped.add(t)
                sc.tables[t].path = path
            elif t in grouped:
                print(f"warning: '{t}' is in more than one TableGroup; using the first", file=sys.stderr)
            else:
                print(f"warning: TableGroup {'__'.join(path)} lists unknown table '{t}'", file=sys.stderr)
    loose = [t for t in sc.tables if t not in grouped]
    if loose:
        areas.append("Ungrouped")
        sc.groups[("Ungrouped",)] = loose
        for t in loose:
            sc.tables[t].path = ("Ungrouped",)

    area_color = {
        a: sc.area_colors.get(a) or sc.group_colors.get(a) or AREA_PALETTE[i % len(AREA_PALETTE)]
        for i, a in enumerate(areas)
    }

    for t in sc.tables.values():
        if t.category and t.category not in CATEGORIES:
            print(f"warning: unknown category '{t.category}' on {t.name}; using 'other'", file=sys.stderr)
            t.category = "other"
        if not t.category and not t.headercolor:
            fks = sum(c.fk for c in t.columns)
            t.category = "cross_reference" if fks >= 2 and len(t.columns) <= fks + 3 else "other"

    hubs: OrderedDict[str, str | None] = OrderedDict()
    used: set[str] = set()
    for t, colr in sc.hubs.items():
        if t in sc.tables:
            hubs[t] = colr
            if colr:
                used.add(colr.lower())
        else:
            print(f"warning: //@hub {t} — no such table", file=sys.stderr)
    counts = Counter(r.parent for r in sc.refs if r.parent in sc.tables)
    for t, n in counts.most_common():
        if len(hubs) >= max(n_hubs, len(sc.hubs)):
            break
        if t not in hubs and n >= 2:
            hubs[t] = None
    free = [c for c in HUB_PALETTE if c.lower() not in used]
    for t in hubs:
        if not hubs[t]:
            hubs[t] = free.pop(0) if free else HUB_PALETTE[len(used) % len(HUB_PALETTE)]
    return areas, area_color, hubs  # type: ignore[return-value]
