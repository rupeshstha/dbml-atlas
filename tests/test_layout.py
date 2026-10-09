"""Layout invariant tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from dbml_atlas.layout import build_layout
from dbml_atlas.parser import parse_dbml
from dbml_atlas.style import resolve

FIXTURES = Path(__file__).parent / "fixtures"


def _build(name: str):
    text = (FIXTURES / f"{name}.dbml").read_text(encoding="utf-8")
    sc = parse_dbml(text)
    areas, area_color, hubs = resolve(sc, n_hubs=6)
    return build_layout(sc, areas, area_color, hubs, aspect=1.414, keep_order=False)


def _fixture_ids():
    return [f.stem for f in sorted(FIXTURES.glob("*.dbml"))]


@pytest.mark.parametrize("name", _fixture_ids())
def test_no_crash(name: str):
    """Every fixture must lay out without raising."""
    root, area_boxes, legend, table_boxes = _build(name)
    assert root.w > 0
    assert root.h > 0


@pytest.mark.parametrize("name", _fixture_ids())
def test_tables_inside_root(name: str):
    """Every table box must be within root bounds."""
    root, _, _, table_boxes = _build(name)
    for tname, b in table_boxes.items():
        assert b.ax >= 0, f"{tname}: x < 0"
        assert b.ay >= 0, f"{tname}: y < 0"
        assert b.ax + b.w <= root.w + 1, f"{tname}: overflows right"
        assert b.ay + b.h <= root.h + 1, f"{tname}: overflows bottom"


@pytest.mark.parametrize("name", _fixture_ids())
def test_no_table_overlaps(name: str):
    """No two table boxes may intersect."""
    _, _, _, table_boxes = _build(name)
    boxes = list(table_boxes.values())
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            no_overlap = (
                a.ax + a.w <= b.ax + 1e-3 or b.ax + b.w <= a.ax + 1e-3 or
                a.ay + a.h <= b.ay + 1e-3 or b.ay + b.h <= a.ay + 1e-3
            )
            assert no_overlap, (
                f"Overlap: {a.table.name} [{a.ax:.0f},{a.ay:.0f}] ↔ "
                f"{b.table.name} [{b.ax:.0f},{b.ay:.0f}]"
            )


@pytest.mark.parametrize("name", _fixture_ids())
def test_deterministic(name: str):
    """Same input → identical layout."""
    r1, _, _, tb1 = _build(name)
    r2, _, _, tb2 = _build(name)
    assert r1.w == r2.w
    assert r1.h == r2.h
    for tname in tb1:
        assert tb1[tname].ax == tb2[tname].ax
        assert tb1[tname].ay == tb2[tname].ay


def test_legend_present():
    root, area_boxes, legend, table_boxes = _build("blog")
    assert legend.w > 0
    assert legend.h > 0
