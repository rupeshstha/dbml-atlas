from __future__ import annotations

import sys

from .layout import HEAD_H, ROW_H, TABLE_GAP
from .model import Schema
from .style import DEFAULT_EDGE


def route_edges(sc: Schema, table_boxes: dict, hubs: dict) -> list[dict]:
    def port_y(box, col: str) -> float:
        i = box.table.col_index(col)
        return box.ay + HEAD_H / 2 if i is None else box.ay + HEAD_H + 2 + i * ROW_H + ROW_H / 2

    lanes: dict = {}

    def lane(key, slot) -> int:
        lst = lanes.setdefault(key, [])
        if slot not in lst:
            lst.append(slot)
        return lst.index(slot)

    max_lanes = max(1, int((TABLE_GAP - 8) / 4))
    edges = []
    for i, r in enumerate(sc.refs):
        source_box = table_boxes.get(r.child)
        target_box = table_boxes.get(r.parent)
        if not source_box or not target_box:
            print(
                f"warning: ref {r.child}.{r.child_col} -> {r.parent}.{r.parent_col}: unknown table, skipped",
                file=sys.stderr,
            )
            continue
        source_y = port_y(source_box, r.child_col)
        target_y = port_y(target_box, r.parent_col)
        color = r.color or hubs.get(r.parent, DEFAULT_EDGE)
        source_left = source_box.ax
        source_right = source_box.ax + source_box.w
        target_left = target_box.ax
        target_right = target_box.ax + target_box.w
        if target_left >= source_right - 1e-6:  # target to the right
            k = lane((r.parent, "L"), r.parent_col) % max_lanes
            lx = target_left - 6 - 4 * k
            pts = [(source_right, source_y), (lx, source_y), (lx, target_y), (target_left, target_y)]
        elif target_right <= source_left + 1e-6:  # target to the left
            k = lane((r.parent, "R"), r.parent_col) % max_lanes
            lx = target_right + 6 + 4 * k
            pts = [(source_left, source_y), (lx, source_y), (lx, target_y), (target_right, target_y)]
        else:  # stacked / self-ref: loop on the right
            k = lane((r.parent, "R"), r.parent_col) % max_lanes
            lx = max(source_right, target_right) + 6 + 4 * k
            pts = [(source_right, source_y), (lx, source_y), (lx, target_y), (target_right, target_y)]
        edges.append(dict(
            i=len(edges), s=r.child, sc=r.child_col,
            t=r.parent, tc=r.parent_col,
            color=color, pts=pts, kind=r.kind,
        ))
    return edges
