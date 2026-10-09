from __future__ import annotations

import json
import re
from pathlib import Path

from .model import Schema
from .render_svg import esc
from .style import CATEGORIES

_HERE = Path(__file__).parent


def _load(name: str) -> str:
    """Load a viewer asset. Replaced with inline strings in the single-file build."""
    return (_HERE / "viewer" / name).read_text(encoding="utf-8")


_HTML_SHELL = """\
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
{css}
@page{{size:{W}px {H}px;margin:0}}
@media print{{#bar,#side,#tip{{display:none!important}}html,body{{height:auto;background:#fff}}#stage{{position:static;width:{W}px;height:{H}px}}}}
</style></head>
<body>
<div id="bar">
  <h1>{title}</h1>
  <input id="q" list="tlist" placeholder="Search table or column  ( / )" autocomplete="off">
  <datalist id="tlist"></datalist>
  <button id="fit" title="Fit (F)">Fit</button>
  <button id="focus" title="Show only the selected table's lines (L)">Focus lines</button>
  <button id="dark" title="Toggle dark mode">Dark</button>
  <span class="sep"></span>
  <span id="areas"></span>
  <span class="sep"></span>
  <button id="dl">SVG</button>
  <button id="pr" title="Print → Save as PDF gives the full poster">PDF</button>
  <span id="help">scroll = zoom · drag = pan · click a table</span>
</div>
<div id="stage">{svg}</div>
<aside id="side"></aside>
<div id="tip"></div>
<div id="minimap"><svg><rect class="vp" x="0" y="0" width="10" height="10"/></svg></div>
<script type="application/json" id="data">{data}</script>
<script>
{js}
</script>
</body></html>"""


def render_html(
    sc: Schema,
    svg: str,
    W: int,
    H: int,
    _areas: list,
    area_boxes: list,
    area_color: dict,
    table_boxes: dict,
    edges: list[dict],
) -> str:
    t_edges: dict[str, list[int]] = {}
    for e in edges:
        t_edges.setdefault(e["s"], []).append(e["i"])
        if e["t"] != e["s"]:
            t_edges.setdefault(e["t"], []).append(e["i"])

    data = dict(
        W=W, H=H,
        slug=re.sub(r"\W+", "-", (sc.title or "schema").lower()).strip("-")[:60],
        cats={k: list(v) for k, v in CATEGORIES.items()},
        areas=[dict(name=a.label, color=area_color[a.label], box=[a.ax, a.ay, a.w, a.h]) for a in area_boxes],
        enums={k: v for k, v in sc.enums.items()},
        edges=[[e["s"], e["sc"], e["t"], e["tc"]] for e in edges],
        tEdges=t_edges,
        tables={
            n: dict(
                name=n, path=list(t.path), cat=t.category or "", note=t.note,
                gnote=sc.group_notes.get(t.path, ""),
                box=[round(table_boxes[n].ax, 1), round(table_boxes[n].ay, 1),
                     table_boxes[n].w, table_boxes[n].h],
                cols=[dict(n=c.name, t=c.type, pk=c.pk, fk=c.fk, nn=c.not_null,
                           uq=c.unique, inc=c.increment, d=c.default, note=c.note)
                      for c in t.columns],
            )
            for n, t in sc.tables.items() if n in table_boxes
        },
    )
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = esc(sc.title or "Database Diagram")

    return _HTML_SHELL.format(
        title=title,
        W=W, H=H,
        css=_load("viewer.css"),
        js=_load("viewer.js"),
        svg=svg,
        data=blob,
    )
