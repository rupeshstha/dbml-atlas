from __future__ import annotations

import sys
from pathlib import Path

# Make sure the package is importable without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOTS = Path(__file__).parent / "snapshots"


def all_fixtures():
    return sorted(FIXTURES.glob("*.dbml"))


def pytest_addoption(parser):
    parser.addoption("--update-snapshots", action="store_true", default=False)


@pytest.fixture
def fixtures_dir():
    return FIXTURES
