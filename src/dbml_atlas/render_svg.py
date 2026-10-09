from __future__ import annotations

import html
import math

from .layout import (
    BADGE_FS, HEAD_H, HEAD_FS, LEG_ROW, NAME_FS, NN_FS, PADX, ROW_H,
    Box, badges, legend_columns, legend_label, measure_legend,
)
from .model import Schema
from .style import (
    CATEGORIES, DEFAULT_EDGE, NOTNULL_COLOR, SANS, SERIF, TYPE_COLOR,
    luminance, mix, shade, text_w,
)


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def render_table(table_box: Box, hubs: dict, interactive: bool) -> list[str]:
    t = table_box.table
    x, y, w, h = table_box.ax, table_box.ay, table_box.w, table_box.h
    head_bg = CATEGORIES[t.category][0] if t.category else (t.headercolor or "#ffffff")
    head_fg = "#000" if luminance(head_bg) > 0.5 else "#fff"
    dash = ' stroke-dasharray="5 3"' if t.is_new else ""
    sw = 2 if t.is_new else 1.2
    out = [f'<g class="tbl" data-t="{esc(t.name)}">']
    hub = hubs.get(t.name)
    if hub:  # Magento's coloured disc behind the corner
        r = min(20, w / 4)
        out.append(
            f'<circle cx="{x + w - r * 0.4:.1f}" cy="{y + HEAD_H * 0.6:.1f}" r="{r:.1f}" '
            f'fill="{hub}" stroke="#000" stroke-width="1"/>'
        )
    out += [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="#000" stroke-width="{sw}"{dash}/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{HEAD_H}" fill="{head_bg}" stroke="#000" stroke-width="{sw}"{dash}/>',
        f'<text x="{x + w / 2}" y="{y + 13}" text-anchor="middle" font-family="{SANS}" '
        f'font-size="{HEAD_FS}" font-weight="bold" fill="{head_fg}">{esc(t.name)}</text>',
    ]
    for i, c in enumerate(t.columns):
        ry = y + HEAD_H + 2 + i * ROW_H
        base = ry + ROW_H - 3
        deco = ' font-weight="bold" text-decoration="underline"' if c.pk else ""
        parts = [f'<tspan{deco}>{esc(c.name)}</tspan>']
        for bd in badges(c):
            parts.append(f'<tspan dx="3" font-size="{BADGE_FS}" font-weight="bold" fill="#666">{bd}</tspan>')
        out.append(
            f'<text x="{x + PADX}" y="{base}" font-family="{SANS}" font-size="{NAME_FS}">{"".join(parts)}</text>'
        )
        out.append(
            f'<text x="{x + table_box.type_x}" y="{base}" font-family="{SANS}" '
            f'font-size="{NAME_FS}" fill="{TYPE_COLOR}">{esc(c.type)}</text>'
        )
        if c.not_null or c.pk:
            out.append(
                f'<text x="{x + table_box.nn_x}" y="{base}" font-family="{SANS}" '
                f'font-size="{NN_FS}" fill="{NOTNULL_COLOR}">not null</text>'
            )
        if interactive:
            if c.note:
                out.append(f'<circle cx="{x + 2.2}" cy="{ry + ROW_H / 2}" r="1.6" fill="#2f5f8a"/>')
            out.append(
                f'<rect class="row" data-c="{esc(c.name)}" x="{x}" y="{ry}" '
                f'width="{w}" height="{ROW_H}" fill="#000" fill-opacity="0"/>'
            )
    if interactive and t.note:
        out.append(f'<path d="M{x + w - 9},{y + 1} h8 v8 z" fill="#2f5f8a"/>')
    out.append("</g>")
    return out


def render_container(container_box: Box, out: list[str], labels: list[str]) -> None:
    depth = container_box.kind_depth
    if depth == 0:
        pen, rx = mix(container_box.color, "#000", 0.35), 34
        fg = "#fff" if luminance(container_box.fill) < 0.42 else "#000"
        out.append(
            f'<g class="area" data-area="{esc(container_box.label)}"><rect x="{container_box.ax}" y="{container_box.ay}" '
            f'width="{container_box.w}" height="{container_box.h}" rx="{rx}" fill="{container_box.fill}" stroke="{pen}" stroke-width="3"/>'
        )
        fs = min(58, (container_box.w - 40) / max(1, text_w(container_box.label.upper(), 1, True)))
        out.append("</g>")
        labels.append(
            f'<text x="{container_box.ax + container_box.w / 2}" y="{container_box.ay + container_box.h - 24}" text-anchor="middle" '
            f'font-family="{SERIF}" font-size="{fs:.1f}" fill="{fg}" pointer-events="none">'
            f'{esc(container_box.label.upper())}</text>'
        )
    else:
        pen = mix(container_box.fill, "#000", 0.28)
        fg = "#fff" if luminance(container_box.fill) < 0.42 else "#000"
        fs = 13 if depth == 1 else 11
        out.append(
            f'<g class="panel" data-path="{esc(" › ".join(container_box.path))}"><rect x="{container_box.ax}" y="{container_box.ay}" '
            f'width="{container_box.w}" height="{container_box.h}" rx="{16 if depth == 1 else 12}" fill="{container_box.fill}" '
            f'stroke="{pen}" stroke-width="1.4"/>'
        )
        out.append("</g>")
        labels.append(
            f'<text x="{container_box.ax + container_box.w / 2}" y="{container_box.ay + (17 if depth == 1 else 15)}" text-anchor="middle" '
            f'font-family="{SERIF}" font-size="{fs}" fill="{fg}" pointer-events="none">'
            f'{esc(container_box.label.upper())}</text>'
        )
    for ch in container_box.children:
        if ch.container:
            render_container(ch, out, labels)


def render_legend(b: Box, sc: Schema, areas: list[str], area_color: dict, hubs: dict) -> list[str]:
    out = [
        f'<g class="legend"><rect x="{b.ax}" y="{b.ay}" width="{b.w}" height="{b.h}" rx="22" '
        f'fill="#fff" stroke="#000" stroke-width="3"/>',
        f'<text x="{b.ax + b.w - 22}" y="{b.ay + 48}" text-anchor="end" font-family="{SERIF}" '
        f'font-size="36">LEGEND</text>',
    ]
    x = b.ax + 20
    for col in legend_columns(sc, areas, hubs):
        y = b.ay + 76
        cw = max(text_w(legend_label(k, v), 12) for k, v in col) + 56
        for kind, v in col:
            if kind == "area":
                c = area_color[v]
                for i in range(3):
                    out.append(
                        f'<rect x="{x + i * 13}" y="{y}" width="14" height="20" rx="3" '
                        f'fill="{shade(c, i)}" stroke="#444" stroke-width=".6"/>'
                    )
            elif kind == "cat":
                c = CATEGORIES[v][0]
                out.append(
                    f'<rect x="{x + 6}" y="{y}" width="24" height="20" fill="{c}" stroke="#000" stroke-width="1.4"/>'
                    f'<line x1="{x + 6}" y1="{y + 5}" x2="{x + 30}" y2="{y + 5}" stroke="#000" stroke-width="1.2"/>'
                )
            elif kind == "new":
                out.append(
                    f'<rect x="{x + 6}" y="{y}" width="24" height="20" fill="#fff" stroke="#000" '
                    f'stroke-width="1.6" stroke-dasharray="3 2"/>'
                )
            else:
                c = hubs.get(v, DEFAULT_EDGE) if kind == "hub" else DEFAULT_EDGE
                out.append(
                    f'<rect x="{x}" y="{y + 5}" width="40" height="9" fill="{c}" stroke="#000" stroke-width="1"/>'
                )
            italic = ' font-style="italic"' if kind == "hub_other" else ""
            out.append(
                f'<text x="{x + 48}" y="{y + 15}" font-family="{SANS}" font-size="12"{italic}>'
                f'{esc(legend_label(kind, v))}</text>'
            )
            y += LEG_ROW
        x += cw + 24
    out.append("</g>")
    return out


def render_svg(
    sc: Schema,
    root: Box,
    areas: list[str],
    area_boxes: list[Box],
    legend: Box,
    table_boxes: dict[str, Box],
    area_color: dict[str, str],
    hubs: dict,
    edges: list[dict],
    interactive: bool,
) -> tuple[str, int, int]:
    W, H = math.ceil(root.w), math.ceil(root.h)
    size = "" if interactive else f' width="{W}" height="{H}"'
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"{size} '
        f'preserveAspectRatio="xMidYMid meet">'
    ]
    colors = sorted({e["color"] for e in edges})
    out.append("<defs>")
    for c in colors:
        mid = "a" + c.lstrip("#")
        out.append(
            f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
        )
    out.append("</defs>")
    out.append(
        f'<rect x="4" y="4" width="{W - 8}" height="{H - 8}" rx="140" fill="#e6e9ec" stroke="#000" stroke-width="5"/>'
    )
    out.append(
        f'<text x="{W / 2}" y="92" text-anchor="middle" font-family="{SERIF}" '
        f'font-size="46">{esc(root.title)}</text>'
    )
    labels: list[str] = []
    for a in area_boxes:
        render_container(a, out, labels)
    out.extend(render_legend(legend, sc, areas, area_color, hubs))

    out.append('<g id="edges" fill="none" stroke-linejoin="round">')
    for e in edges:
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in e["pts"])
        dash = ' stroke-dasharray="6 3"' if e["kind"] == "<>" else ""
        out.append(
            f'<path class="edge" data-i="{e["i"]}" d="{d}" stroke="{e["color"]}" stroke-width="1.3"'
            f'{dash} marker-end="url(#a{e["color"].lstrip("#")})"/>'
        )
    out.append("</g>")

    out.extend(labels)
    out.append('<g id="tables">')
    for table_box in table_boxes.values():
        out.extend(render_table(table_box, hubs, interactive))
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out), W, H
