"""Tests for suggest_groups heuristic."""
from __future__ import annotations

from dbml_atlas.parser import parse_dbml
from dbml_atlas.suggest import suggest_groups


def test_prefix_clustering():
    """Tables sharing a snake_case prefix end up in the same group."""
    sc = parse_dbml("""
        Table shop_staff { id int [pk] shop_id int }
        Table shop_notes { id int [pk] shop_id int }
        Table plan_addons { id int [pk] }
        Table plan_prices { id int [pk] plan_addon_id int }
    """)
    out = suggest_groups(sc)
    assert "TableGroup Shop" in out
    assert "shop_staff" in out
    assert "shop_notes" in out
    assert "TableGroup Plan" in out
    assert "plan_addons" in out
    assert "plan_prices" in out


def test_fk_affinity_attaches_singleton():
    """A table with no prefix match attaches to the group it has the most FKs into."""
    sc = parse_dbml("""
        Table shop_staff { id int [pk] shop_id int }
        Table shop_notes { id int [pk] shop_id int }
        Table invoices {
          id int [pk]
          shop_id int [ref: > shop_staff.shop_id]
        }
    """)
    out = suggest_groups(sc)
    # invoices has no prefix group but FK into Shop — should land in Shop group
    shop_block_start = out.index("TableGroup Shop")
    closing_brace = out.index("}", shop_block_start)
    shop_block = out[shop_block_start:closing_brace]
    assert "invoices" in shop_block


def test_no_tables():
    out = suggest_groups(parse_dbml("// empty"))
    assert "No tables" in out


def test_output_is_valid_dbml_comment_header():
    sc = parse_dbml("""
        Table users { id int [pk] }
        Table posts { id int [pk] user_id int [ref: > users.id] }
    """)
    out = suggest_groups(sc)
    assert out.startswith("//")
    assert "TableGroup" in out


def test_color_assigned():
    sc = parse_dbml("""
        Table shop_staff { id int [pk] }
        Table shop_notes { id int [pk] }
    """)
    out = suggest_groups(sc)
    assert 'color: "' in out
