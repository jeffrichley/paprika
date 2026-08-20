"""Changing one thing, and nothing else.

This is the operation that destroyed rating, categories, source, nutrition and
photos in a shipping community server, on **every** edit, propagated to every
synced device. Issue #8 found it. These tests exist so it cannot happen here.

The fixture is deliberately hostile: every field carries a distinctive value,
including the ones that are `null` in live data and the ones nobody documented.
A field left at its default would survive a bug that drops it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import RECIPE_FIELDS, FakePaprika
from tests.library import make_recipe
from tests.test_cli import envelope_of

runner = CliRunner()
UID = "5E7A11ED-0000-4000-8000-00000000FFFF"


def _a_recipe_with_everything_filled_in() -> dict[str, Any]:
    """Return a recipe whose every field carries something worth losing.

    Returns:
        dict[str, Any]: The recipe.
    """
    return make_recipe(
        UID,
        "Everything Filled In",
        categories=["CAT-ROAST", "CAT-POULTRY"],
        rating=4,
        total_time="1 hr 10 min",
        ingredients="200g flour\n1 tsp salt\n2 large eggs",
        directions="Mix.\n\nBake.",
        description="A description that is usually null.",
        notes="Notes she typed at midnight — with an em dash and a ‘quote’.",
        nutritional_info="Calories: 430\nProtein: 12g",
        servings="12 muffins",
        difficulty="Medium",
        prep_time="15 mins.",
        cook_time="55",
        source="A Cookbook, p. 214",
        source_url="https://example.com/a?b=c&d=e",
        image_url="https://example.com/photo.jpg",
        photo="thumb.jpg",
        photo_hash="A" * 64,
        photo_large="large.jpg",
        on_favorites=True,
        on_grocery_list=None,
        is_pinned=True,
        scale="2",
        cook_minutes=55,
        prep_minutes=15,
        total_minutes=70,
        servings_min=12,
        servings_max=12,
        cookbook_uid="COOKBOOK-1",
        metadata_version="3",
    )


def _handle(seeded: FakePaprika) -> str:
    """Sync and return the handle of the fixture recipe.

    Args:
        seeded: The fake account.

    Returns:
        str: Its handle.
    """
    seeded.recipes[UID] = _a_recipe_with_everything_filled_in()
    runner.invoke(app, ["sync"])
    envelope = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)
    line = next(e for e in envelope["data"]["recipes"] if "Everything Filled In" in e)
    return str(line.split(" | ")[0])


def test_only_the_named_field_moves(signed_in: Path, seeded: FakePaprika) -> None:
    """The #8 failure, asserted field by field against a fully populated recipe."""
    handle = _handle(seeded)
    before = dict(seeded.recipes[UID])

    result = runner.invoke(
        app, ["write", "recipe", "set", handle, "--set", "servings=6"]
    )

    assert result.exit_code == 0
    after = seeded.recipes[UID]
    assert after["servings"] == "6"
    for field in RECIPE_FIELDS:
        if field in ("servings", "hash", "photo_url"):
            continue
        assert after[field] == before[field], f"{field} moved and should not have"


def test_the_undocumented_fields_survive_byte_identical(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Five of them are structured twins of fields that are usually null."""
    handle = _handle(seeded)
    before = dict(seeded.recipes[UID])

    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "notes=changed"])

    after = seeded.recipes[UID]
    for field in (
        "cook_minutes",
        "prep_minutes",
        "total_minutes",
        "servings_min",
        "servings_max",
        "cookbook_uid",
        "metadata_version",
    ):
        assert after[field] == before[field], field


def test_a_null_stays_null_rather_than_becoming_empty(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Paprika is fussy about exactly this, and `""` is not `null`."""
    handle = _handle(seeded)

    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "notes=changed"])

    sent = seeded.writes[-1]
    assert sent["on_grocery_list"] is None
    assert sent["description"] is not None


def test_her_photos_survive_an_edit(signed_in: Path, seeded: FakePaprika) -> None:
    """Photos were among the five things the community server destroyed."""
    handle = _handle(seeded)

    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "rating=5"])

    after = seeded.recipes[UID]
    assert after["photo"] == "thumb.jpg"
    assert after["photo_large"] == "large.jpg"
    assert after["photo_hash"] == "A" * 64


def test_her_filing_survives_an_edit(signed_in: Path, seeded: FakePaprika) -> None:
    handle = _handle(seeded)

    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "rating=5"])

    assert seeded.recipes[UID]["categories"] == ["CAT-ROAST", "CAT-POULTRY"]


def test_unusual_characters_come_back_unchanged(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Her wording is hers, punctuation included."""
    handle = _handle(seeded)
    before = seeded.recipes[UID]["notes"]

    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "rating=5"])

    assert seeded.recipes[UID]["notes"] == before


def test_two_fields_can_change_at_once(signed_in: Path, seeded: FakePaprika) -> None:
    handle = _handle(seeded)
    before = dict(seeded.recipes[UID])

    runner.invoke(
        app,
        [
            "write",
            "recipe",
            "set",
            handle,
            "--set",
            "servings=6",
            "--set",
            "prep_time=20 mins",
        ],
    )

    after = seeded.recipes[UID]
    assert (after["servings"], after["prep_time"]) == ("6", "20 mins")
    assert after["directions"] == before["directions"]


def test_a_gap_left_by_a_file_read_can_be_replaced(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A Gap is marked in the recipe's own text, so filling it is an ordinary edit."""
    seeded.recipes[UID] = _a_recipe_with_everything_filled_in()
    seeded.recipes[UID]["ingredients"] = "200g flour\n[couldn't read this line]\n2 eggs"
    runner.invoke(app, ["sync"])
    envelope = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)
    handle = str(
        next(
            e for e in envelope["data"]["recipes"] if "Everything Filled In" in e
        ).split(" | ")[0]
    )

    runner.invoke(
        app,
        [
            "write",
            "recipe",
            "set",
            handle,
            "--set",
            "ingredients=200g flour\n1 tsp salt\n2 eggs",
        ],
    )

    after = seeded.recipes[UID]["ingredients"]
    assert "couldn't read" not in after
    assert "1 tsp salt" in after


def test_an_edit_can_be_undone_field_for_field(
    signed_in: Path, seeded: FakePaprika
) -> None:
    handle = _handle(seeded)
    before = dict(seeded.recipes[UID])

    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "name=Wrong"])
    runner.invoke(app, ["write", "undo"])

    after = seeded.recipes[UID]
    for field in RECIPE_FIELDS:
        if field in ("hash", "photo_url"):
            continue
        assert after[field] == before[field], f"{field} did not come back"
