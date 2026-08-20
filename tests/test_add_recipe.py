"""Getting a recipe in — from a link, or from her saying it out loud.

A create has nothing to fetch, so the object it starts from is the core's own
blank. The rule is unchanged from an edit, arrived at from the other direction:
a caller may fill fields in and may never decide which fields exist.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import RECIPE_FIELDS, FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()


def test_a_dictated_recipe_is_saved(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        [
            "write",
            "recipe",
            "create",
            "--set",
            "name=Nana's Soda Bread",
            "--set",
            "ingredients=450g flour\n1 tsp bicarb\n400ml buttermilk",
            "--set",
            "directions=Mix. Bake at 200C for 40 minutes.",
        ],
    )

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert result.exit_code == 0
    assert envelope["changed"] == {"recipes": 1}
    assert envelope["data"]["saved"] == "Nana's Soda Bread"


def test_a_new_recipe_carries_every_field(signed_in: Path, seeded: FakePaprika) -> None:
    """All thirty-five, including the seven nobody would think to include."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "recipe", "create", "--set", "name=Anything"])

    sent = seeded.writes[-1]
    for field in RECIPE_FIELDS:
        if field == "photo_url":
            continue
        assert field in sent, f"{field} missing from a new recipe"
    assert "photo_url" not in sent


def test_a_new_recipe_starts_empty_rather_than_invented(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Anything she did not say stays blank. Blank means she did not say it."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "recipe", "create", "--set", "name=Anything"])

    sent = seeded.writes[-1]
    assert sent["servings"] == ""
    assert sent["total_time"] == ""
    assert sent["rating"] == 0
    assert sent["categories"] == []
    # The photo fields must be null rather than empty, which Paprika is fussy
    # about, and the undocumented ones must be present and null.
    assert (sent["photo"], sent["photo_hash"], sent["photo_large"]) == (
        None,
        None,
        None,
    )
    assert sent["servings_min"] is None


def test_a_recipe_needs_a_name(signed_in: Path, seeded: FakePaprika) -> None:
    """Paprika treats it as required, and an untitled recipe is unfindable."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app, ["write", "recipe", "create", "--set", "ingredients=flour"]
    )

    assert result.exit_code == 1
    assert seeded.writes == []


def test_a_link_is_kept_as_the_source(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "recipe",
            "create",
            "--set",
            "name=From A Blog",
            "--set",
            "source=Some Blog",
            "--set",
            "source_url=https://example.com/soda-bread",
        ],
    )

    sent = seeded.writes[-1]
    assert sent["source"] == "Some Blog"
    assert sent["source_url"] == "https://example.com/soda-bread"


def test_neither_intake_path_marks_the_recipe_as_ours(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A link and a dictation are hers. Only an invented recipe is ours."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "recipe", "create", "--set", "name=Hers"])

    sent = seeded.writes[-1]
    assert "Created with Claude" not in str(sent["source"])
    assert "Created with Claude" not in str(sent["notes"])


def test_a_new_recipe_can_be_filed_by_category_name(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "recipe",
            "create",
            "--set",
            "name=Something Baked",
            "--add",
            "categories=Sourdough",
        ],
    )

    assert seeded.writes[-1]["categories"] == ["CAT-SOURDOUGH"]


def test_the_duplicate_check_is_the_real_library(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Lexical, against what she actually has — not a guess about what she might."""
    runner.invoke(app, ["sync"])

    envelope = envelope_of(
        runner.invoke(app, ["recipe", "search", "Roast Lemon Chicken"]).stdout
    )

    assert len(envelope["data"]["recipes"]) == 1
    assert "Roast Lemon Chicken" in envelope["data"]["recipes"][0]


def test_the_duplicate_check_finds_nothing_when_there_is_nothing(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    envelope = envelope_of(
        runner.invoke(app, ["recipe", "search", "Nana's Soda Bread"]).stdout
    )

    assert envelope["data"]["recipes"] == []


def test_a_new_recipe_can_be_undone(signed_in: Path, seeded: FakePaprika) -> None:
    """A create undoes to not existing, which is a removal rather than nothing."""
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["write", "recipe", "create", "--set", "name=Mistake"])
    assert any(r["name"] == "Mistake" for r in seeded.recipes.values())

    runner.invoke(app, ["write", "undo"])

    assert not any(r["name"] == "Mistake" for r in seeded.recipes.values())


def test_a_new_recipe_appears_in_her_library(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "recipe", "create", "--set", "name=Newly Added"])

    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    assert any("Newly Added" in line for line in lines)


def test_a_create_cannot_choose_the_key_set(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The same rule as an edit, from the other direction."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        ["write", "recipe", "create", "--set", "name=X", "--set", "invented=1"],
    )

    assert result.exit_code == 1
    assert seeded.writes == []


def test_a_create_cannot_set_a_mechanic(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])

    for forbidden in ("uid=X", "hash=" + "a" * 64, "in_trash=true"):
        result = runner.invoke(
            app, ["write", "recipe", "create", "--set", "name=X", "--set", forbidden]
        )
        assert result.exit_code == 1, forbidden
    assert seeded.writes == []
