from __future__ import annotations

import argparse
import os
import sys
from collections import OrderedDict

from .layout import build_layout
from .parser import parse_dbml
from .pdf import write_pdf
from .render_html import render_html
from .render_svg import render_svg
from .routing import route_edges
from .style import resolve


def _filter_area(sc, area_name: str) -> None:
    """Remove all tables not in the given area, and their dangling refs/groups."""
    keep = {name for name, t in sc.tables.items() if t.path and t.path[0] == area_name}
    if not keep:
        available = ", ".join(sorted({t.path[0] for t in sc.tables.values() if t.path}))
        sys.exit(f"Area '{area_name}' not found. Available areas: {available}")
    sc.tables = OrderedDict((k, v) for k, v in sc.tables.items() if k in keep)
    sc.refs = [r for r in sc.refs if r.child in keep and r.parent in keep]
    sc.groups = OrderedDict(
        (p, [t for t in ts if t in keep])
        for p, ts in sc.groups.items()
        if p and p[0] == area_name and any(t in keep for t in ts)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DBML → Magento-style poster (.svg/.pdf) and interactive viewer (.html)",
    )
    parser.add_argument("dbml", nargs="?",
                        help="DBML file to render, or 'introspect' to read from a live database")
    parser.add_argument("introspect_dsn", nargs="?",
                        help="DSN for introspect: sqlite:///path.db | postgresql://... | mysql://...")
    parser.add_argument("-o", "--output", action="append",
                        help="output file(s): .html, .svg or .pdf (repeatable). Default: <name>.html and <name>.svg")
    parser.add_argument("--title")
    parser.add_argument("--hubs", type=int, default=6,
                        help="auto colour-code FKs into the N most-referenced tables")
    parser.add_argument("--aspect", type=float, default=1.414,
                        help="poster width/height target (A-series landscape = 1.414)")
    parser.add_argument("--keep-order", action="store_true",
                        help="keep DBML order inside panels instead of packing by size")
    parser.add_argument("--area", metavar="NAME",
                        help="render only tables in this area (v0.2)")
    args = parser.parse_args()

    if not args.dbml:
        parser.print_help()
        sys.exit(1)

    # ── introspect subcommand ─────────────────────────────────────────────────
    if args.dbml == "introspect":
        if not args.introspect_dsn:
            parser.error("introspect requires a DSN argument")
        from .introspect import introspect
        print(introspect(args.introspect_dsn))
        return

    # ── suggest-groups subcommand ─────────────────────────────────────────────
    if args.dbml == "suggest-groups":
        if not args.introspect_dsn:
            parser.error("suggest-groups requires a DBML file argument")
        from .suggest import suggest_groups
        try:
            with open(args.introspect_dsn, encoding="utf-8") as f:
                sc = parse_dbml(f.read())
        except FileNotFoundError:
            sys.exit(f"Error: could not find {args.introspect_dsn}")
        print(suggest_groups(sc))
        return

    # ── render ────────────────────────────────────────────────────────────────
    try:
        with open(args.dbml, encoding="utf-8") as f:
            sc = parse_dbml(f.read())
    except FileNotFoundError:
        sys.exit(f"Error: could not find {args.dbml}")

    if args.title:
        sc.title = args.title
    if not sc.tables:
        sys.exit("No tables found in the DBML file.")

    areas, area_color, hubs = resolve(sc, args.hubs)

    if not sc.groups:
        print(
            f"hint → no TableGroups found in {args.dbml}. "
            f"Run: dbml-atlas suggest-groups {args.dbml}",
            file=sys.stderr,
        )

    if args.area:
        _filter_area(sc, args.area)
        # Re-resolve with filtered schema
        areas, area_color, hubs = resolve(sc, args.hubs)

    root, area_boxes, legend, table_boxes = build_layout(sc, areas, area_color, hubs, args.aspect, args.keep_order)
    edges = route_edges(sc, table_boxes, hubs)

    stem = os.path.splitext(args.dbml)[0]
    outputs = args.output or [stem + ".html", stem + ".svg"]
    static_svg = None
    for out in outputs:
        ext = out.rsplit(".", 1)[-1].lower()
        if ext == "html":
            svg_markup, W, H = render_svg(sc, root, areas, area_boxes, legend, table_boxes, area_color, hubs, edges, True)
            doc = render_html(sc, svg_markup, W, H, areas, area_boxes, area_color, table_boxes, edges)
            with open(out, "w", encoding="utf-8") as output_file:
                output_file.write(doc)
            print(f"  viewer  → {out}")
        elif ext in ("svg", "pdf"):
            if static_svg is None:
                static_svg = render_svg(sc, root, areas, area_boxes, legend, table_boxes, area_color, hubs, edges, False)
            svg_markup, W, H = static_svg
            if ext == "svg":
                with open(out, "w", encoding="utf-8") as output_file:
                    output_file.write(svg_markup)
                print(f"  poster  → {out}  ({W}×{H})")
            else:
                via = write_pdf(svg_markup, W, H, out)
                print(f"  poster  → {out}  ({W}×{H}, via {via})")
        else:
            sys.exit(f"Unknown output type: {out} (use .html, .svg or .pdf)")
    print(f"{len(sc.tables)} tables · {len(edges)} FKs · {len(areas)} areas · {len(sc.groups)} groups")
