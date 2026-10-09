"""Render tests — escaping, self-contained HTML, determinism."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from dbml_atlas.layout import build_layout
from dbml_atlas.parser import parse_dbml
from dbml_atlas.render_html import render_html
from dbml_atlas.render_svg import render_svg
from dbml_atlas.routing import route_edges
from dbml_atlas.style import resolve  # noqa: F401 — also used by test_area_filter

FIXTURES = Path(__file__).parent / "fixtures"


def _render(name: str, interactive: bool = True):
    text = (FIXTURES / f"{name}.dbml").read_text(encoding="utf-8")
    sc = parse_dbml(text)
    areas, area_color, hubs = resolve(sc, n_hubs=6)
    root, area_boxes, legend, table_boxes = build_layout(sc, areas, area_color, hubs, 1.414, False)
    edges = route_edges(sc, table_boxes, hubs)
    svg, W, H = render_svg(sc, root, areas, area_boxes, legend, table_boxes, area_color, hubs, edges, interactive)
    if not interactive:
        return svg, W, H
    html = render_html(sc, svg, W, H, areas, area_boxes, area_color, table_boxes, edges)
    return html, W, H


def _fixture_ids():
    return [f.stem for f in sorted(FIXTURES.glob("*.dbml"))]


@pytest.mark.parametrize("name", _fixture_ids())
def test_html_no_external_resources(name: str):
    """The HTML output must not load external resources (scripts, fonts, images).
    SVG xmlns namespace URIs are exempt — they are identifiers, not network requests."""
    html, _, _ = _render(name)
    # Strip XML namespace declarations before checking
    stripped = re.sub(r'xmlns(?::\w+)?="https?://[^"]*"', "", html)
    assert not re.search(r'(?:src|href|url)\s*=\s*["\']https?://', stripped), \
        "HTML must not load external resources"


@pytest.mark.parametrize("name", _fixture_ids())
def test_svg_is_valid_xml(name: str):
    """The static SVG must be parseable as XML."""
    import xml.etree.ElementTree as ET
    svg, _, _ = _render(name, interactive=False)
    ET.fromstring(svg)  # raises if invalid


@pytest.mark.parametrize("name", _fixture_ids())
def test_html_deterministic(name: str):
    """Same input → byte-identical HTML output."""
    h1, _, _ = _render(name)
    h2, _, _ = _render(name)
    assert h1 == h2


def test_xss_escaping():
    """Hostile strings in table names/notes must be escaped in output."""
    html, _, _ = _render("xss_hostile")
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    # Escaped forms should be present
    assert "&lt;script&gt;" in html or "\\u003cscript" in html or "alert" not in html


def test_json_blob_escaped():
    """The embedded JSON data blob must have </ escaped as <\\/."""
    html, _, _ = _render("xss_hostile")
    # The </script> sequence must never appear literally inside the data block
    data_block_match = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.DOTALL)
    assert data_block_match, "No data block found"
    assert "</script>" not in data_block_match.group(1)


def test_dark_mode_button_present():
    """v0.1: dark mode toggle button must be in the HTML."""
    html, _, _ = _render("minimal")
    assert 'id="dark"' in html


def test_copy_link_rendered():
    """v0.1: the copy-link button markup must appear when a table is shown."""
    html, _, _ = _render("minimal")
    assert "data-copylink" in html or "copylink" in html


def test_minimap_present():
    """v0.2: minimap element must be in the HTML."""
    html, _, _ = _render("minimal")
    assert 'id="minimap"' in html


def test_area_filter():
    """v0.2: --area renders only tables in that area."""
    text = (FIXTURES / "many_areas.dbml").read_text()
    sc = parse_dbml(text)
    # resolve() must run first to populate t.path (same order as CLI main())
    resolve(sc, n_hubs=6)
    from dbml_atlas.cli import _filter_area
    _filter_area(sc, "Identity")
    assert sc.tables, "should keep some tables"
    assert all(t.path[0] == "Identity" for t in sc.tables.values() if t.path)


def test_poster_svg_no_interactive_elements():
    """Static poster SVG must have no .row hit-rects and no note-dot circles."""
    svg, _, _ = _render("blog", interactive=False)
    assert 'class="row"' not in svg
    assert "note_sink" not in svg  # sanity
