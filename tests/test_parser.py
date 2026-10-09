"""Parser tests — smoke + snapshot + specific behaviours."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dbml_atlas.parser import parse_dbml

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOTS = Path(__file__).parent / "snapshots"


def _schema_to_dict(sc) -> dict:
    """Serialise a Schema to a JSON-compatible dict for snapshots."""
    return dict(
        title=sc.title,
        tables={
            name: dict(
                name=t.name,
                columns=[dict(
                    name=c.name, type=c.type, pk=c.pk, fk=c.fk,
                    not_null=c.not_null, unique=c.unique,
                    increment=c.increment, default=c.default, note=c.note,
                ) for c in t.columns],
                category=t.category,
                is_new=t.is_new,
                note=t.note,
                path=list(t.path),
            )
            for name, t in sc.tables.items()
        },
        refs=[dict(child=r.child, child_col=r.child_col, parent=r.parent, parent_col=r.parent_col, kind=r.kind)
              for r in sc.refs],
        enums={name: [[v, note] for v, note in vals] for name, vals in sc.enums.items()},
    )


def _fixture_ids():
    return [f.stem for f in sorted(FIXTURES.glob("*.dbml"))]


@pytest.mark.parametrize("name", _fixture_ids())
def test_parser_does_not_crash(name: str):
    """Every fixture must parse without raising an exception."""
    text = (FIXTURES / f"{name}.dbml").read_text(encoding="utf-8")
    sc = parse_dbml(text)
    assert sc is not None


@pytest.mark.parametrize("name", _fixture_ids())
def test_parser_snapshot(name: str, request):
    """Snapshot test: parsed Schema matches stored JSON (or writes it on first run)."""
    text = (FIXTURES / f"{name}.dbml").read_text(encoding="utf-8")
    sc = parse_dbml(text)
    actual = _schema_to_dict(sc)

    snap_path = SNAPSHOTS / f"{name}.json"
    if request.config.getoption("--update-snapshots", default=False):
        SNAPSHOTS.mkdir(exist_ok=True)
        snap_path.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    if not snap_path.exists():
        pytest.skip(f"No snapshot for {name} — run with --update-snapshots to create it")

    expected = json.loads(snap_path.read_text(encoding="utf-8"))
    assert actual == expected


# ── specific behaviour tests ───────────────────────────────────────────────

def test_minimal_tables():
    sc = parse_dbml("""
        Table users {
          id bigint [pk]
          email varchar(255) [unique, not null]
        }
    """)
    assert "users" in sc.tables
    assert len(sc.tables["users"].columns) == 2
    assert sc.tables["users"].columns[0].pk is True
    assert sc.tables["users"].columns[1].unique is True
    assert sc.tables["users"].columns[1].not_null is True


def test_inline_ref_marks_fk():
    sc = parse_dbml("""
        Table a {
          id int [pk]
        }
        Table b {
          id int [pk]
          a_id int [ref: > a.id]
        }
    """)
    col = sc.tables["b"].col("a_id")
    assert col is not None
    assert col.fk is True


def test_top_level_ref():
    sc = parse_dbml("""
        Table a { id int [pk] }
        Table b { id int [pk] a_id int }
        Ref: b.a_id > a.id
    """)
    assert len(sc.refs) == 1
    assert sc.refs[0].child == "b"
    assert sc.refs[0].parent == "a"


def test_ref_direction_flip():
    """Ref with < should be stored as > with child/parent swapped."""
    sc = parse_dbml("""
        Table a { id int [pk] }
        Table b { a_id int }
        Ref: b.a_id < a.id
    """)
    assert sc.refs[0].kind == ">"
    assert sc.refs[0].child == "a"
    assert sc.refs[0].parent == "b"


def test_composite_pk():
    sc = parse_dbml("""
        Table memberships {
          org_id bigint
          user_id bigint
          indexes { (org_id, user_id) [pk] }
        }
    """)
    t = sc.tables["memberships"]
    assert t.col("org_id").pk is True
    assert t.col("user_id").pk is True


def test_alias():
    sc = parse_dbml("""
        Table users as U { id int [pk] }
        Table posts as P { id int [pk] author_id int }
        Ref: P.author_id > U.id
    """)
    assert sc.refs[0].parent == "users"
    assert sc.refs[0].child == "posts"


def test_enum_parsed():
    sc = parse_dbml("""
        Enum status {
          active
          inactive [note: 'Soft-deleted']
        }
        Table items {
          id int [pk]
          status status
        }
    """)
    assert "status" in sc.enums
    assert sc.enums["status"][1][0] == "inactive"
    assert "Soft-deleted" in sc.enums["status"][1][1]


def test_multiline_note():
    sc = parse_dbml("""
        Table t {
          id int [pk]
          Note: '''
            Line one.
            Line two.
          '''
        }
    """)
    assert "Line one" in sc.tables["t"].note
    assert "Line two" in sc.tables["t"].note


def test_category_directive():
    sc = parse_dbml("""
        //@category important
        Table core { id int [pk] }
    """)
    assert sc.tables["core"].category == "important"


def test_new_directive():
    sc = parse_dbml("""
        //@new
        Table fresh { id int [pk] }
    """)
    assert sc.tables["fresh"].is_new is True


def test_hub_directive():
    sc = parse_dbml("""
        //@hub orders #ff0000
        Table orders { id int [pk] }
    """)
    assert sc.hubs.get("orders") == "#ff0000"


def test_title_directive():
    sc = parse_dbml("//@title My Schema\nTable t { id int [pk] }")
    assert sc.title == "My Schema"


def test_xss_content_not_interpreted():
    """Parser stores raw strings; escaping happens at render time."""
    sc = parse_dbml("""
        Table "<script>alert(1)</script>" { id int [pk] }
    """)
    name = list(sc.tables.keys())[0]
    assert "<script>" in name  # stored as-is; render_svg will escape it


def test_unknown_syntax_skipped():
    """Unknown blocks (Records, DiagramView) should not crash the parser."""
    text = (Path(__file__).parent / "fixtures" / "unknown_syntax.dbml").read_text()
    sc = parse_dbml(text)
    assert "users" in sc.tables
    assert "posts" in sc.tables


def test_schema_prefix_stripped():
    sc = parse_dbml("Table public.users { id int [pk] }")
    assert "users" in sc.tables


def test_no_tables_returns_empty():
    sc = parse_dbml("// just a comment\n")
    assert len(sc.tables) == 0


def test_deterministic():
    """Parsing the same text twice gives identical results."""
    text = (Path(__file__).parent / "fixtures" / "ecommerce.dbml").read_text()
    sc1 = parse_dbml(text)
    sc2 = parse_dbml(text)
    assert list(sc1.tables.keys()) == list(sc2.tables.keys())
    assert len(sc1.refs) == len(sc2.refs)
