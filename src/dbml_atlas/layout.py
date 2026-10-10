from __future__ import annotations

import math
from collections import OrderedDict

from .model import Schema, Table
from .style import CATEGORIES, shade, text_w

# ─────────────────────────────────────────────────────────────────────────────
# Sizing constants
# ─────────────────────────────────────────────────────────────────────────────
NAME_FS = 10
HEAD_FS = 11
BADGE_FS = 7
NN_FS = 8.5
ROW_H = 13
HEAD_H = 18
PADX = 5
COLGAP = 8
TABLE_GAP = 22          # room for FK "bus" lanes between tables
PANEL = dict(pad=10, head=26, gap=TABLE_GAP)
SUBPANEL = dict(pad=9, head=22, gap=TABLE_GAP)
AREA = dict(pad=16, head=16, foot=84, gap=16)
ROOT = dict(pad=50, head=110, gap=30)
LEG_ROW = 24


class Box:
    def __init__(self, kind: str, w: float = 0.0, h: float = 0.0, **kw):
        self.kind = kind
        self.w = w
        self.h = h
        self.x = self.y = 0.0
        self.ax = self.ay = 0.0
        self.children: list[Box] = []
        self.__dict__.update(kw)

    @property
    def container(self) -> bool:
        return self.kind in ("area", "panel")


def badges(column) -> list[str]:
    badge_list = []
    if column.pk:
        badge_list.append("PK")
    if column.fk:
        badge_list.append("FK")
    if column.unique and not column.pk:
        badge_list.append("UQ")
    return badge_list


def measure_table(t: Table) -> tuple[int, int, float, float]:
    name_widths, type_widths = [], []
    for c in t.columns:
        w = text_w(c.name, NAME_FS, c.pk)
        for badge in badges(c):
            w += 3 + text_w(badge, BADGE_FS, True)
        name_widths.append(w)
        type_widths.append(text_w(c.type, NAME_FS))
    max_name_width = max(name_widths, default=0)
    max_type_width = max(type_widths, default=0)
    has_nn = any(c.not_null or c.pk for c in t.columns)
    w = PADX + max_name_width + COLGAP + max_type_width + (COLGAP + text_w("not null", NN_FS) if has_nn else 0) + PADX
    w = max(w, text_w(t.name, HEAD_FS, True) + 2 * PADX + 6, 90)
    h = HEAD_H + len(t.columns) * ROW_H + 4
    return math.ceil(w), math.ceil(h), PADX + max_name_width + COLGAP, PADX + max_name_width + COLGAP + max_type_width + COLGAP


def skyline(rects: list[tuple[float, float]], W: float, gap: float) -> list[tuple[float, float]] | None:
    """Bottom-left skyline packing. rects = [(w,h)], returns [(x,y)] or None."""
    sky = [[0.0, 0.0, W + gap]]
    pos = []
    for w, h in rects:
        padded_w, padded_h = w + gap, h + gap
        best = None
        for i in range(len(sky)):
            x = sky[i][0]
            if x + padded_w > W + gap + 1e-6:
                break
            current_top, remaining_width, seg_idx = 0.0, padded_w, i
            while remaining_width > 1e-6 and seg_idx < len(sky):
                current_top = max(current_top, sky[seg_idx][1])
                remaining_width -= sky[seg_idx][2]
                seg_idx += 1
            if remaining_width > 1e-6:
                continue
            cand = (current_top + padded_h, x)
            if best is None or cand < best[0]:
                best = (cand, x, current_top)
        if best is None:
            return None
        _, x, y = best
        pos.append((x, y))
        new = []
        for seg_x, seg_y, seg_w in sky:
            seg_end = seg_x + seg_w
            if seg_end <= x + 1e-6 or seg_x >= x + padded_w - 1e-6:
                new.append([seg_x, seg_y, seg_w]); continue
            if seg_x < x:
                new.append([seg_x, seg_y, x - seg_x])
            if seg_end > x + padded_w:
                new.append([x + padded_w, seg_y, seg_end - (x + padded_w)])
        new.append([x, y + padded_h, padded_w])
        new.sort()
        merged: list = []
        for seg in new:
            if merged and abs(merged[-1][1] - seg[1]) < 1e-6 and abs(merged[-1][0] + merged[-1][2] - seg[0]) < 1e-6:
                merged[-1][2] += seg[2]
            else:
                merged.append(seg)
        sky = merged
    return pos


def pack(items: list[Box], gap: float, aspect: float, keep_order: bool = False) -> tuple[float, float]:
    """Place items to minimise wasted area near a target aspect ratio."""
    if not items:
        return 0.0, 0.0
    if len(items) == 1:
        items[0].x = items[0].y = 0.0
        return items[0].w, items[0].h
    order = list(items) if keep_order else sorted(items, key=lambda b: (-b.h, -b.w))
    rects = [(b.w, b.h) for b in order]
    wmax = max(w for w, _ in rects)
    wsum = sum(w for w, _ in rects) + gap * (len(rects) - 1)
    cands = {wmax, wsum}
    steps = 40
    for k in range(1, steps):
        cands.add(wmax + (wsum - wmax) * k / steps)
    acc = 0.0
    for w, _ in rects:  # natural row breaks
        acc += w + (gap if acc else 0)
        if acc >= wmax:
            cands.add(acc)
    best = None
    for W in sorted(cands):
        pos = skyline(rects, W, gap)
        if pos is None:
            continue
        best_width = max(x + w for (x, _), (w, _) in zip(pos, rects))
        best_height = max(y + h for (_, y), (_, h) in zip(pos, rects))
        score = best_width * best_height * (1 + 0.6 * abs(math.log((best_width / best_height) / aspect)))
        if best is None or score < best[0]:
            best = (score, pos, best_width, best_height)
    _, pos, best_width, best_height = best  # type: ignore[misc]
    for b, (x, y) in zip(order, pos):
        b.x, b.y = x, y
    return best_width, best_height


def fill_gaps(items: list[Box], W: float, H: float, gap: float) -> None:
    """Grow containers down, then right, into empty space (Magento's tidy look)."""
    conts = sorted([b for b in items if b.container], key=lambda b: (b.y, b.x))
    for c in conts:
        lim = H
        for o in items:
            if o is not c and o.x < c.x + c.w - 1e-6 and o.x + o.w > c.x + 1e-6 and o.y >= c.y + c.h - 1e-6:
                lim = min(lim, o.y - gap)
        c.h = max(c.h, lim - c.y)
    for c in sorted(conts, key=lambda b: (b.x, b.y)):
        lim = W
        for o in items:
            if o is not c and o.y < c.y + c.h - 1e-6 and o.y + o.h > c.y + 1e-6 and o.x >= c.x + c.w - 1e-6:
                lim = min(lim, o.x - gap)
        c.w = max(c.w, lim - c.x)


def legend_columns(sc: Schema, areas: list[str], hubs: dict) -> list[list[tuple[str, str]]]:
    cats = [k for k in CATEGORIES if any(t.category == k for t in sc.tables.values())]
    area_items = [("area", a) for a in areas]
    category_items = [("cat", k) for k in cats]
    if any(t.is_new for t in sc.tables.values()):
        category_items.append(("new", "Recently Added"))
    hub_items = [("hub", t) for t in hubs] + ([("hub_other", "other foreign keys")] if hubs else [])
    return [col for col in (area_items, category_items, hub_items) if col]


def legend_label(kind: str, v: str) -> str:
    if kind == "area":
        return f"Area:  {v}"
    if kind == "cat":
        return CATEGORIES[v][1]
    return v


def measure_legend(sc: Schema, areas: list[str], hubs: dict) -> tuple[int, int]:
    cols = legend_columns(sc, areas, hubs)
    widths = [max(text_w(legend_label(k, v), 12) for k, v in col) + 56 for col in cols]
    w = sum(widths) + 24 * (len(cols) - 1) + 40
    h = 70 + max(len(c) for c in cols) * LEG_ROW + 20
    return math.ceil(max(w, 260)), math.ceil(h)


def build_layout(
    sc: Schema,
    areas: list[str],
    area_color: dict[str, str],
    hubs: dict,
    aspect: float,
    keep_order: bool,
) -> tuple[Box, list[Box], Box, dict[str, Box]]:
    tree: OrderedDict = OrderedDict()
    for path, tables in sc.groups.items():
        node = tree
        for part in path:
            node = node.setdefault(part, OrderedDict({"__tables__": []}))
        node["__tables__"].extend(t for t in tables if t in sc.tables and sc.tables[t].path == path)

    table_boxes: dict[str, Box] = {}

    def make(name: str, node: OrderedDict, depth: int, color: str, path: tuple) -> Box:
        kids: list[Box] = []
        for t in node["__tables__"]:
            w, h, type_x, nn_x = measure_table(sc.tables[t])
            box = Box("table", w, h, table=sc.tables[t], type_x=type_x, nn_x=nn_x)
            table_boxes[t] = box
            kids.append(box)
        for child, sub in node.items():
            if child != "__tables__":
                kids.append(make(child, sub, depth + 1, color, path + (child,)))
        m = AREA if depth == 0 else (PANEL if depth == 1 else SUBPANEL)
        aspect_here = 0.9 if depth == 0 else 1.25
        inner_width, inner_height = pack(kids, m["gap"], aspect_here, keep_order)
        label_fs = 13 if depth == 1 else 11
        min_w = text_w(name.upper(), label_fs) + 24 if depth else 0
        box = Box(
            "area" if depth == 0 else "panel",
            kind_depth=depth, label=name, color=color,
            fill=shade(color, depth), m=m, path=path, children=kids,
            note=sc.group_notes.get(path, ""),
        )
        box.w = max(inner_width + 2 * m["pad"], min_w)
        box.h = inner_height + m["head"] + m.get("foot", m["pad"])
        return box

    area_boxes = [make(a, tree[a], 0, area_color[a], (a,)) for a in areas if a in tree]
    legend_width, legend_height = measure_legend(sc, areas, hubs)
    legend = Box("legend", legend_width, legend_height)
    items = area_boxes + [legend]
    inner_width, inner_height = pack(items, ROOT["gap"], aspect, keep_order=False)
    title = sc.title or "Database Diagram"
    inner_width = max(inner_width, text_w(title, 46) + 40)
    root = Box(
        "root",
        inner_width + 2 * ROOT["pad"],
        inner_height + ROOT["head"] + ROOT["pad"],
        children=items,
        title=title,
    )

    def finish(c: Box, W: float, H: float) -> None:
        fill_gaps(c.children, W, H, c.m["gap"] if hasattr(c, "m") else ROOT["gap"])
        for ch in c.children:
            if ch.container:
                finish(ch, ch.w - 2 * ch.m["pad"], ch.h - ch.m["head"] - ch.m.get("foot", ch.m["pad"]))

    root.m = dict(ROOT, foot=ROOT["pad"])
    finish(root, inner_width, inner_height)

    def place(c: Box, ox: float, oy: float) -> None:
        c.ax, c.ay = ox, oy
        m = c.m
        for ch in c.children:
            if ch.container:
                place(ch, ox + m["pad"] + ch.x, oy + m["head"] + ch.y)
            else:
                ch.ax, ch.ay = ox + m["pad"] + ch.x, oy + m["head"] + ch.y

    place(root, 0, 0)
    return root, area_boxes, legend, table_boxes
