# dbml-atlas

**Turn your DBML schema into a printable database poster and an interactive canvas explorer — one command, no server, no account.**

[![PyPI](https://img.shields.io/pypi/v/dbml-atlas)](https://pypi.org/project/dbml-atlas/)
[![Python](https://img.shields.io/pypi/pyversions/dbml-atlas)](https://pypi.org/project/dbml-atlas/)
[![CI](https://github.com/rupeshstha/dbml-viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/rupeshstha/dbml-viewer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

```
dbml-atlas schema.dbml
# → schema.html   interactive viewer: pan, zoom, search, dark mode, focus lines
# → schema.svg    print-ready poster: nested areas, colour-coded FK lines, legend
```

> **Live demo:** [rupeshstha.github.io/dbml-viewer](https://rupeshstha.github.io/dbml-viewer) — 200+ table real-world schema, loads offline.

---

## Why dbml-atlas?

| | dbml-atlas | dbdiagram.io | ChartDB / drawDB |
|---|---|---|---|
| Input | DBML file | DBML (online editor) | DB connection / import |
| Output | Self-contained HTML + SVG | PNG / shared link | Browser canvas |
| Offline | Yes — works from `file://` | No | No |
| Zero dependencies | Yes — stdlib only | N/A | N/A |
| Printable poster | Yes — nested areas, colour-coded FK bus lanes | No | No |
| Open source | MIT | Closed | MIT / Apache |
| Hosting required | No | Yes | Yes |

dbml-atlas is a **viewer, not an editor**. Your DBML file is the source of truth — it stays in git, gets reviewed in PRs, and the diagram regenerates automatically in CI. If you want drag-and-drop editing or real-time collaboration, [ChartDB](https://chartdb.io) and [drawDB](https://drawdb.vercel.app) are the right tools.

---

## Features

**Interactive HTML viewer**
- Pan and zoom (mouse wheel, pinch, drag)
- Full-text search across table and column names (`/` shortcut)
- Click any table to see its columns, notes, FK targets, and incoming references
- Focus lines mode — hides all FK lines except those for the selected table
- Minimap — bottom-right inset with a viewport indicator
- Dark mode (persists across sessions)
- Deep-link to any table: `diagram.html#orders`
- Export current view as SVG

**Printable SVG poster**
- Nested areas and panels, Magento-style layout
- Header colours by table category (entity, reference, cross-reference, etc.)
- FK lines coloured by hub table, with "bus" lanes in gutter space
- Legend, area labels, table notes rendered as SVG text
- `@page` CSS for PDF-quality printing straight from the browser

**Zero-dependency Python tool**
- Python 3.9+ required; no third-party packages at runtime
- Optional extras: `[pdf]` for cairosvg, `[postgres]` / `[mysql]` for live DB introspection
- Single-file build (`dbml_atlas.py`) — download and run with no install
- Reusable GitHub Action for CI/CD automation

---

## Quick start

```bash
pip install dbml-atlas
dbml-atlas schema.dbml
# Opens schema.html in your browser
```

Or without installing:

```bash
curl -O https://raw.githubusercontent.com/rupeshstha/dbml-viewer/main/dbml_atlas.py
python dbml_atlas.py schema.dbml
```

---

## Installation

### From PyPI

```bash
pip install dbml-atlas
```

With optional extras:

```bash
pip install "dbml-atlas[pdf]"       # PDF output via cairosvg
pip install "dbml-atlas[postgres]"  # PostgreSQL introspection
pip install "dbml-atlas[mysql]"     # MySQL / MariaDB introspection
pip install "dbml-atlas[pdf,postgres,mysql]"  # everything
```

### Without installing (single-file)

Download `dbml_atlas.py` and run it directly — no pip, no virtualenv, no dependencies:

```bash
curl -O https://raw.githubusercontent.com/rupeshstha/dbml-viewer/main/dbml_atlas.py
python dbml_atlas.py schema.dbml
```

---

## Usage

```bash
# Render to HTML viewer + SVG poster (default output names match the input file)
dbml-atlas schema.dbml

# Specify output paths (flag is repeatable — mix .html, .svg, .pdf freely)
dbml-atlas schema.dbml -o docs/diagram.html -o docs/diagram.svg

# PDF output (requires pip install "dbml-atlas[pdf]")
dbml-atlas schema.dbml -o diagram.pdf

# Render only one area (useful for large schemas)
dbml-atlas schema.dbml --area Billing

# Override the diagram title
dbml-atlas schema.dbml --title "My Schema v2"

# Introspect a live database and emit DBML to stdout
dbml-atlas introspect sqlite:///path/to/db.sqlite3
dbml-atlas introspect postgresql://user:pass@host/dbname   # requires [postgres]
dbml-atlas introspect mysql://user:pass@host/dbname        # requires [mysql]

# Pipe introspect directly into a render
dbml-atlas introspect sqlite:///app.db | dbml-atlas /dev/stdin -o diagram.html

# python -m syntax also works
python -m dbml_atlas schema.dbml
```

---

## Directives

Add these in `//` comments immediately above a `Table` block (or anywhere for file-level directives).
They are standard DBML comments — `dbdiagram.io` and `@dbml/core` ignore them safely.

| Directive | Where | Effect |
|---|---|---|
| `//@title My Schema` | File level | Sets the poster title |
| `//@area Sales #e8f5e9` | File level | Declares an area colour (auto-assigned if omitted) |
| `//@hub orders #ff6b6b` | Before `Table` | Colours all FK lines pointing at this table; adds a coloured disc |
| `//@category entity` | Before `Table` | Sets the table's header colour (see categories below) |
| `//@new` | Before `Table` | Draws a dashed border — "recently added" marker |

### Table categories

| Key | Aliases | Colour meaning |
|---|---|---|
| `reference_static` | `ref_static`, `static` | Lookup tables that never change |
| `reference_dynamic` | `ref_dynamic`, `dynamic` | Lookup tables updated by ops |
| `entity` | `core` | Core business objects |
| `entity_detail` | `detail` | Detail / child records |
| `important` | `key` | High-traffic or high-importance tables |
| `cross_reference` | `xref`, `pivot`, `junction` | Many-to-many join tables |
| `other` | — | Everything else |

### Area grouping via `TableGroup`

Areas are derived from `TableGroup` names using `__` as a path separator:

```dbml
TableGroup Sales__Quotes  { quotes  quote_items }
TableGroup Sales__Orders  { orders  order_items }
```

Both groups land inside a `Sales` area. Single-level names become top-level panels.

---

## GitHub Action

Publish a live, always-current diagram to GitHub Pages on every schema change:

```yaml
# .github/workflows/diagram.yml
name: Database diagram
on:
  push:
    paths: ['schema.dbml']

jobs:
  diagram:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: rupeshstha/dbml-viewer@v1
        with:
          dbml: schema.dbml
          html: docs/index.html
          svg: docs/schema.svg
      - uses: actions/upload-pages-artifact@v3
        with:
          path: docs/
      - uses: actions/deploy-pages@v4
```

See [`action.yml`](action.yml) for all inputs (`title`, `hubs`, `area`).

---

## CLI reference

```
dbml-atlas [options] <dbml-file>
dbml-atlas introspect <dsn>

Arguments:
  dbml-file         DBML file to render
  introspect <dsn>  Read schema from a live database (SQLite / PostgreSQL / MySQL)

Options:
  -o, --output PATH  Output file (.html, .svg, .pdf) — repeatable
  --title TEXT       Override the diagram title
  --hubs N           Auto colour-code FKs into the N most-referenced tables (default: 6)
  --aspect RATIO     Target width/height ratio (default: 1.414, A-series landscape)
  --keep-order       Preserve DBML table order inside panels instead of packing by size
  --area NAME        Render only the tables in this area
```

---

## Supported DBML

| Feature | Status | Notes |
|---|---|---|
| `Table`, columns, `[pk]`, `[not null]`, `[unique]`, `[increment]` | Full | |
| `[default: value]` | Full | |
| `[ref: > table.col]` inline | Full | |
| `Ref: a.col > b.col` top-level | Full | |
| `Ref { ... }` blocks | Full | |
| `<` direction | Full | Flipped to `>` internally |
| `<>` many-to-many | Full | Dashed line |
| `TableGroup` (area grouping) | Full | `__` path separator |
| `Enum` | Full | Listed in side panel |
| `Note:` on tables and columns | Full | Single-line and `'''` multi-line |
| `headercolor` on tables | Full | |
| `[color]` on `TableGroup` | Full | |
| `Table alias as A` | Full | |
| `schema.table` prefix | Full | Schema prefix stripped |
| `` `backtick` `` identifiers | Full | |
| Composite PKs via `indexes { (a, b) [pk] }` | Full | |
| Composite foreign keys | Partial | First column only |
| `Project { }` blocks | Skipped | |
| `TablePartial` / `~partial` | Skipped | |
| `Records`, `DiagramView`, `checks` | Skipped | |
| Multi-line column notes in `[...]` | Not supported | Use table-level `Note:` instead |

Unknown blocks are skipped with a warning on stderr — the render always continues.

---

## Development

```bash
git clone https://github.com/rupeshstha/dbml-viewer
cd dbml-atlas
pip install -e ".[dev]"

# Run tests
python -m pytest -q

# Lint / format
ruff check src/ tests/
ruff format src/ tests/

# After editing src/ — regenerate the single-file build and verify it matches
python scripts/build_single_file.py
python scripts/build_single_file.py --check   # CI runs this automatically
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide.

---

## Project structure

```
dbml-atlas/
├── src/dbml_atlas/          source package — edit here, never in dbml_atlas.py
│   ├── cli.py               argparse CLI
│   ├── model.py             Column, Table, Ref, Schema dataclasses
│   ├── parser.py            normalize() + parse_dbml() state machine
│   ├── style.py             palettes, categories, resolve()
│   ├── layout.py            skyline bin-packing, build_layout()
│   ├── routing.py           orthogonal FK polylines with bus lanes
│   ├── render_svg.py        SVG renderer
│   ├── render_html.py       HTML shell + JSON data blob
│   ├── pdf.py               optional PDF backends
│   ├── introspect.py        live DB → DBML (SQLite / Postgres / MySQL)
│   └── viewer/
│       ├── viewer.css       viewer styles + dark mode tokens
│       └── viewer.js        pan / zoom / search / minimap / focus lines
├── dbml_atlas.py            generated single-file build (do not edit)
├── scripts/
│   └── build_single_file.py regenerates dbml_atlas.py from src/
├── tests/
│   ├── fixtures/            *.dbml test inputs
│   ├── snapshots/           expected parsed Schema as JSON
│   ├── test_parser.py
│   ├── test_layout.py
│   └── test_render.py
├── examples/
│   ├── example.dbml         minimal example with directives
│   └── dubdubco.dbml        large real-world schema (200+ tables)
├── action.yml               reusable GitHub Action
├── pyproject.toml
├── CHANGELOG.md
└── LICENSE                  MIT
```

---

## License

MIT — see [LICENSE](LICENSE).

Contributions welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first.
