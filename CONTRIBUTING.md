# Contributing to dbml-atlas

Thanks for taking the time to contribute!

## Reporting bugs

Open a [GitHub issue](https://github.com/rupeshstha/dbml-viewer/issues) and include:

- The DBML input (or a minimal reproduction)
- The command you ran
- The Python version (`python --version`)
- The error message or unexpected output

## Suggesting features

Open an issue with the label `enhancement`. Please check the [non-goals](#non-goals) section before proposing — some things are intentionally out of scope.

### Non-goals

- **Canvas editing** (drag tables, save layouts) — use [ChartDB](https://chartdb.io) or [drawDB](https://drawdb.vercel.app)
- **Hosted SaaS or login** — the output is a static file, that's the point
- **Runtime dependencies** — the HTML/SVG render must stay stdlib-only

## Development setup

```bash
git clone https://github.com/rupeshstha/dbml-viewer
cd dbml-atlas
pip install -e ".[dev]"   # installs pytest + ruff in editable mode
```

No Node, no Docker, no other tools required.

## Running tests

```bash
python -m pytest -q                       # full suite
python -m pytest tests/test_parser.py -q  # one file
python -m pytest -k "test_xss" -q         # filter by name
```

### Snapshot tests

Parser snapshot tests compare the parsed `Schema` object against committed JSON files in `tests/snapshots/`. If you intentionally change parser output:

```bash
python -m pytest tests/test_parser.py --update-snapshots
# Review the diff, then commit both the fixture and the updated snapshot
```

### Adding a new DBML fixture

Drop a `*.dbml` file in `tests/fixtures/` and run `--update-snapshots` once to generate the expected snapshot. Commit both files together.

## Code style

```bash
ruff check src/ tests/   # lint
ruff format src/ tests/  # format
```

CI enforces both. Run them before pushing.

## After editing `src/`

Always regenerate the single-file build:

```bash
python scripts/build_single_file.py
python scripts/build_single_file.py --check   # must print "OK"
```

CI runs `--check` automatically — a mismatch fails the build.

The single-file build (`dbml_atlas.py`) is the "download and run" distribution. It must stay in sync with `src/` at all times.

## Pull request checklist

- [ ] Tests pass: `python -m pytest -q`
- [ ] Lint passes: `ruff check src/ tests/`
- [ ] Single-file build is up to date: `python scripts/build_single_file.py --check`
- [ ] New behaviour is covered by a test
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] If parser output changed, snapshots are updated and committed

## Hard rules (never break these)

1. **Stdlib only at runtime.** No pip install needed to produce `.html`/`.svg`. Optional extras are only allowed for PDF and DB introspection, and must be lazily imported with a clear error message.
2. **HTML output is fully self-contained.** No CDN links, external fonts, or network calls. Must work from `file://` and offline.
3. **Deterministic output.** Same input → byte-identical output. Snapshot tests depend on this.
4. **Never crash on unknown DBML.** Skip it, print a warning to stderr, keep rendering.
5. **Escape everything.** All DBML-derived strings are untrusted. Run them through `esc()` before any SVG/HTML output; embedded JSON must replace `</` with `<\/`.

## Releasing (maintainers only)

1. Update `version` in `pyproject.toml` and `src/dbml_atlas/__init__.py`
2. Add a release section to `CHANGELOG.md`
3. Rebuild the single-file: `python scripts/build_single_file.py`
4. Commit: `git commit -am "chore: release vX.Y.Z"`
5. Tag: `git tag vX.Y.Z && git push --tags`
6. The `release.yml` workflow publishes to PyPI automatically via trusted publishing
