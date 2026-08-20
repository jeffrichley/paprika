"""Fixtures for the nutrition tests.

The index is built once for the whole session and shared read-only. It is the
real bundled data rather than a fixture: the facts these tests assert — that a
large onion is 150 g, that FNDDS code 90000 is 15 g against a whole onion's 148,
that `butter` reaches a record which does not invent `unsalted` — are the
findings ``docs/research/usda-nutrition-matching.md`` established, and a
synthetic index would assert them against ourselves.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from paprika_core.nutrition.index import UsdaIndex, materialise
from paprika_core.nutrition.memo import Memos


@pytest.fixture(scope="session")
def usda_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialise the bundled data once for the whole session.

    Args:
        tmp_path_factory: pytest's session-wide directory factory.

    Returns:
        Path: The materialised index.
    """
    path = tmp_path_factory.mktemp("usda") / "usda.sqlite3"
    materialise(path)
    return path


@pytest.fixture
def index(usda_file: Path) -> Iterator[UsdaIndex]:
    """Open the shared index.

    Args:
        usda_file: The materialised index.

    Yields:
        UsdaIndex: The open index.
    """
    with UsdaIndex(usda_file) as open_index:
        yield open_index


@pytest.fixture
def memos(tmp_path: Path) -> Iterator[Memos]:
    """Open an empty memo store.

    Args:
        tmp_path: pytest's per-test directory.

    Yields:
        Memos: The open store.
    """
    with Memos(tmp_path / "nutrition.sqlite3") as store:
        yield store
