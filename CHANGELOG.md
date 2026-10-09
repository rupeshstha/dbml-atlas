# Changelog

All notable changes to dbml-atlas are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.2.0] — 2025-01-15

### Added
- `--area NAME` flag: render only the tables in one named area
- Minimap: bottom-right inset showing the full diagram with a viewport indicator
- `dbml-atlas introspect <dsn>`: connect to SQLite, PostgreSQL or MySQL and emit DBML to stdout

## [0.1.0] — 2024-12-20

### Added
- Split monolithic `dbml_viewer.py` into `src/dbml_atlas/` package (`model`, `parser`, `style`, `layout`, `routing`, `render_svg`, `render_html`, `pdf`, `cli`)
- Viewer assets extracted to `src/dbml_atlas/viewer/viewer.css` and `viewer.js`
- `scripts/build_single_file.py` regenerates `dbml_atlas.py` (the "download and run" distribution)
- `pyproject.toml` with console script `dbml-atlas` and optional extras `[pdf]`, `[postgres]`, `[mysql]`
- `python -m dbml_atlas` entry point
- 20+ parser fixture files and snapshot/invariant/render test suite
- Dark mode toggle button (persists across sessions via `localStorage`)
- "Copy link to table" button in the side panel
- GitHub Actions: CI (Python 3.9–3.13, Linux/macOS/Windows), GitHub Pages demo, PyPI release

### Changed
- HTML toolbar: added Dark and PDF buttons; Focus lines and Fit remain

### Fixed
- `render_html` no longer duplicates the `areas` parameter in the data blob
