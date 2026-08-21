"""Screening a recipe for allergens by the words it uses.

**Presence, never absence.** A hit is a fact: the recipe says the word. No hits
means nothing at all — the recipe may be full of passata, ketchup or the oil
sun-dried tomatoes came packed in. The moment this reads as *"that one's fine"*
it becomes the failure that motivated the allergen gate in #93: something that
looks checked while going unchecked, which is worse than nothing because it
stops anybody looking.

Written after a live test where two careful sessions independently read 36
recipes and both made errors — one missing a severe allergen named in a notes
field, in the recipe set as the trap. `paprika recipe search` already covered
that field. The mechanical answer existed and nothing pointed at it.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika

runner = CliRunner()


def _found(seeded: FakePaprika, *args: str) -> dict:
    """Run the check and return its data.

    Args:
        seeded: The fake, so a caller reads as a test rather than plumbing.
        args: Arguments after ``recipe check``.

    Returns:
        dict: The envelope's data.
    """
    result = runner.invoke(app, ["recipe", "check", *args])
    return dict(json.loads(result.stdout)["data"])


def test_an_allergen_named_in_the_ingredients_is_found(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    data = _found(seeded, "--for", "lemon")

    assert any("Roast Lemon Chicken" in hit["name"] for hit in data["found"])


def test_the_line_it_matched_is_quoted(signed_in: Path, seeded: FakePaprika) -> None:
    """So a skill can show her the evidence rather than assert the conclusion."""
    runner.invoke(app, ["sync"])

    data = _found(seeded, "--for", "lemon")

    hit = next(h for h in data["found"] if "Roast Lemon Chicken" in h["name"])
    assert any("lemon" in line.casefold() for line in hit["lines"])


def test_it_looks_in_the_notes_as_well_as_the_ingredients(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The trap that beat two careful readings.

    A recipe whose only mention of the allergen is in a free-text note is
    exactly what a human eye skips and a word search cannot miss.
    """
    uid = next(iter(seeded.recipes))
    seeded.recipes[uid]["notes"] = "serve with pineapple tidbits on the side"
    runner.invoke(app, ["sync"])

    data = _found(seeded, "--for", "pineapple")

    assert data["found"], data


def test_a_known_allergen_brings_its_other_spellings(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """`milk` has to find the cream, or naming the allergy achieves nothing."""
    uid = next(iter(seeded.recipes))
    seeded.recipes[uid]["ingredients"] = "200ml double cream\n1 onion"
    runner.invoke(app, ["sync"])

    data = _found(seeded, "--for", "milk")

    assert data["found"]
    assert "cream" in data["searched"]


def test_a_word_we_do_not_know_is_searched_literally_and_says_so(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The honest-limitation test, and the important one.

    `tomatoes` finds the word and does **not** find ketchup. Saying which
    happened is what stops a clean result reading as a clean recipe.
    """
    uid = next(iter(seeded.recipes))
    seeded.recipes[uid]["ingredients"] = "3 cups ketchup\n1 lb beef"
    runner.invoke(app, ["sync"])

    data = _found(seeded, "--for", "tomatoes")

    assert data["found"] == []
    assert data["searched"] == ["tomatoes"]
    assert data["literal_only"] == ["tomatoes"]


def test_nothing_found_never_claims_the_recipe_is_safe(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A detector, not a clearance. The words matter as much as the matching."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["recipe", "check", "--for", "kryptonite"])

    said = result.stdout.casefold()
    for reassurance in ("safe", "clear", "free of", "none found"):
        assert reassurance not in said, reassurance


def test_it_checks_what_the_household_avoids_when_asked_for_nothing(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The common case is *screen this against us*, not against a word."""
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["write", "profile", "set", "people.cynthia.allergies+=lemon"])

    data = _found(seeded)

    assert "lemon" in data["searched"]
    assert data["found"]


def test_the_default_reaches_the_guests_allergies_too(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Found live: on the household guests were built for, the default was blind.

    `always_avoid` is family-only, correctly — that is #96, and it is what stops
    a guest's allergy constraining a week she is not part of. But a *check* is
    not a plan. It reports what a recipe names; who is eating decides what to do
    about it. Defaulting to the family alone meant that on a household whose
    only two allergies belong to guests, the bare command had nothing to look
    for and refused.
    """
    uid = next(iter(seeded.recipes))
    seeded.recipes[uid]["ingredients"] = "1 can pineapple\n1 lb pork"
    runner.invoke(app, ["sync"])
    runner.invoke(
        app, ["write", "profile", "set", "guests.jordan.allergies+=pineapple"]
    )

    data = _found(seeded)

    assert "pineapple" in data["searched"]
    assert data["found"]


def test_every_hit_says_whose_allergy_it_is(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Because a hit for a guest matters on their nights and not on others.

    Reporting the allergy without the person would force a caller to re-derive
    the #96 scoping from the Profile, and a rule re-derived at each call site is
    a rule that will eventually be derived differently.
    """
    uid = next(iter(seeded.recipes))
    seeded.recipes[uid]["ingredients"] = "1 can pineapple\n1 lb pork"
    runner.invoke(app, ["sync"])
    runner.invoke(
        app, ["write", "profile", "set", "guests.jordan.allergies+=pineapple"]
    )

    hit = _found(seeded)["found"][0]

    assert hit["whose"] == ["jordan"]
    assert hit["when"] == "guest"


def test_peanut_butter_is_not_a_dairy_hit(signed_in: Path, seeded: FakePaprika) -> None:
    """Found live: 21 recipes matched `milk` only through peanut butter.

    The cost of a false positive is not the false positive. It is that a check
    which cries wolf teaches the person reading it to skim, and a skimmed
    backstop is not a backstop.
    """
    uid = next(iter(seeded.recipes))
    seeded.recipes[uid]["ingredients"] = "2 tbsp powdered peanut butter\n1 apple"
    runner.invoke(app, ["sync"])

    data = _found(seeded, "--for", "milk")

    assert data["found"] == [], data["found"]
