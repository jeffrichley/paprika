"""The Mirror — our local copy, only ever fresh or stale."""

from __future__ import annotations

from paprika_core.mirror import Mirror
from tests.library import CATEGORY_TREE, LIBRARY_SIZE, build_library, make_recipe

A_UID = "8F2A1C4E-11D3-4A1B-9C3D-1A2B3C4D5E6F"


def test_the_mirror_keeps_every_field_it_was_given(mirror: Mirror) -> None:
    """A field dropped here is a field a later write cannot echo back."""
    recipe = make_recipe(A_UID, "Anything")
    mirror.put_recipe(recipe)
    mirror.assign_handles()

    assert mirror.recipe_body("8f2a1c") == recipe


def test_the_mirror_ignores_an_object_with_no_identity(mirror: Mirror) -> None:
    mirror.put_recipe({"name": "Nameless"})

    assert mirror.count_recipes() == 0


def test_a_trashed_recipe_is_mirrored_but_not_in_her_library(mirror: Mirror) -> None:
    """She deleted it. Paprika's own trash is where it lives until she empties it."""
    for recipe in build_library():
        mirror.put_recipe(recipe)
    mirror.assign_handles()

    assert mirror.count_recipes() == LIBRARY_SIZE
    assert all("Threw Out" not in r.name for r in mirror.recipes())


def test_untrashing_a_recipe_returns_it_to_her_library(mirror: Mirror) -> None:
    """The Mirror is rebuilt from what Paprika says, never merged with what it held."""
    trashed = make_recipe(A_UID, "Back Again", in_trash=True)
    mirror.put_recipe(trashed)
    assert mirror.count_recipes() == 0

    mirror.put_recipe(make_recipe(A_UID, "Back Again", in_trash=False))

    assert mirror.count_recipes() == 1


def test_the_mirror_reports_its_own_age(mirror: Mirror) -> None:
    assert mirror.age_seconds() is None

    mirror.mark_synced({"recipes": 5})

    age = mirror.age_seconds()
    assert age is not None and age >= 0


def test_the_category_tree_keeps_its_parents(mirror: Mirror) -> None:
    mirror.put_categories(CATEGORY_TREE)

    by_uid = {c.uid: c for c in mirror.categories()}
    assert by_uid["CAT-ROAST"].parent_uid == "CAT-POULTRY"
    assert by_uid["CAT-MAINS"].parent_uid is None


def test_a_refetched_recipe_replaces_rather_than_duplicates(mirror: Mirror) -> None:
    """The Mirror is keyed by identity, so the same recipe twice is still one."""
    mirror.put_recipe(make_recipe(A_UID, "First Name"))
    mirror.put_recipe(make_recipe(A_UID, "Renamed"))

    assert mirror.count_recipes() == 1
    assert mirror.recipes()[0].name == "Renamed"
