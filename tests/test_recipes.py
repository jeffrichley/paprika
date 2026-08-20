"""The index — one line per recipe, the whole Library at once."""

from __future__ import annotations

import pytest

from paprika_core.mirror import Mirror
from paprika_core.recipes import index_lines
from tests.library import CATEGORY_TREE, LIBRARY_SIZE, build_library


@pytest.fixture
def stocked(mirror: Mirror) -> Mirror:
    """Return a Mirror holding the reference Library and category tree.

    Args:
        mirror: An empty Mirror.

    Returns:
        Mirror: The same Mirror, filled.
    """
    mirror.put_categories(CATEGORY_TREE)
    for recipe in build_library():
        mirror.put_recipe(recipe)
    mirror.assign_handles()
    return mirror


def test_one_line_per_recipe(stocked: Mirror) -> None:
    assert len(index_lines(stocked)) == LIBRARY_SIZE


def test_the_index_names_her_categories_rather_than_their_ids(stocked: Mirror) -> None:
    roast = next(line for line in index_lines(stocked) if "Roast Lemon" in line)

    assert "Roasts" in roast
    assert "CAT-ROAST" not in roast


def test_the_index_leaves_a_blank_rather_than_guessing(stocked: Mirror) -> None:
    """An unrated recipe and an untimed one render empty, never as a guess."""
    casserole = next(line for line in index_lines(stocked) if "Casserole" in line)

    assert casserole.endswith(" |  | ")


def test_the_index_carries_no_ingredients(stocked: Mirror) -> None:
    """A question needing ingredients pulls bodies; it does not widen this line."""
    assert not any("other things" in line for line in index_lines(stocked))


def test_the_index_omits_what_she_trashed(stocked: Mirror) -> None:
    assert not any("Threw Out" in line for line in index_lines(stocked))
