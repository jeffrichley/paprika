"""The Plan minus the Pantry — so she stops buying a fourth jar of cumin.

The subtraction is arithmetic over two lists, done here rather than in a
conversation, because it has to come out the same every time.

The age gates whether the list *explains itself*, never whether it subtracts. A
stale Pantry is still the best information there is; what changes is that the
list says out loud what it took off.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()
WEEK = ["--from", "2026-08-24", "--to", "2026-08-30"]


def _plan_a_recipe(seeded: FakePaprika, ingredients: str) -> None:
    """Put one recipe with known ingredients on the plan.

    Args:
        seeded: The fake account.
        ingredients: Newline-separated ingredient lines.
    """
    first = next(iter(seeded.recipes.values()))
    first["ingredients"] = ingredients
    runner.invoke(app, ["sync"])


def test_the_list_is_the_plans_ingredients(
    signed_in: Path, seeded: FakePaprika
) -> None:
    _plan_a_recipe(seeded, "1 lemon\n2 chicken thighs\n1 tbsp olive oil")

    result = runner.invoke(app, ["grocery-draft", *WEEK])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert {item["line"] for item in envelope["data"]["buy"]} == {
        "1 lemon",
        "2 chicken thighs",
        "1 tbsp olive oil",
    }


def test_what_she_already_has_is_taken_off(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The whole point of the ticket."""
    _plan_a_recipe(seeded, "2 tsp ground cumin\n1 lemon")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert [item["line"] for item in envelope["data"]["buy"]] == ["1 lemon"]
    assert envelope["data"]["already_have"] == ["cumin"]


def test_something_she_has_run_out_of_is_not_subtracted(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """`soy sauce` is in her pantry marked gone, so it still has to be bought."""
    _plan_a_recipe(seeded, "1 tbsp soy sauce")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert [item["line"] for item in envelope["data"]["buy"]] == ["1 tbsp soy sauce"]


def test_a_word_inside_another_word_is_not_a_match(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Whole words. Not buying something she needed is worse than the extra jar."""
    _plan_a_recipe(seeded, "1 loaf cuminseed bread")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert [item["line"] for item in envelope["data"]["buy"]] == [
        "1 loaf cuminseed bread"
    ]
    assert envelope["data"]["already_have"] == []


def test_the_same_ingredient_twice_is_bought_once(
    signed_in: Path, seeded: FakePaprika
) -> None:
    _plan_a_recipe(seeded, "1 lemon\n1 Lemon\n2 eggs")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert len(envelope["data"]["buy"]) == 2


def test_a_heading_is_not_something_to_buy(
    signed_in: Path, seeded: FakePaprika
) -> None:
    _plan_a_recipe(seeded, "For the sauce:\n1 lemon\n\n---\n2 eggs")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert {item["line"] for item in envelope["data"]["buy"]} == {"1 lemon", "2 eggs"}


def test_a_night_that_is_not_a_recipe_contributes_nothing(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """`Leftovers` is on the plan and has no ingredients to shop for."""
    _plan_a_recipe(seeded, "1 lemon")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert [item["line"] for item in envelope["data"]["buy"]] == ["1 lemon"]


def test_a_never_confirmed_pantry_still_subtracts(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The age gates the explanation, never the subtraction."""
    _plan_a_recipe(seeded, "2 tsp ground cumin\n1 lemon")

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert envelope["data"]["already_have"] == ["cumin"]
    assert envelope["data"]["pantry_stale"] is True
    assert envelope["data"]["pantry_age_days"] is None


def test_a_fresh_pantry_needs_no_explaining(
    signed_in: Path, seeded: FakePaprika
) -> None:
    _plan_a_recipe(seeded, "2 tsp ground cumin")
    runner.invoke(app, ["write", "pantry", "confirm", "cumin"])

    envelope = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)

    assert envelope["data"]["pantry_stale"] is False
    assert envelope["data"]["pantry_age_days"] == 0.0


def test_the_staleness_threshold_is_hers_to_set(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A number that lives only in a prompt is one nobody can tune."""
    _plan_a_recipe(seeded, "2 tsp ground cumin")
    runner.invoke(app, ["write", "pantry", "confirm", "cumin"])

    default = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)
    assert default["data"]["pantry_stale"] is False

    # She wants the list to explain itself every time, however recent.
    runner.invoke(app, ["write", "profile", "set", "rhythm.pantry_stale_days=0"])

    hers = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)
    assert hers["data"]["pantry_stale"] is True
    # And it still subtracted, because the age never gates that.
    assert hers["data"]["already_have"] == ["cumin"]


def test_the_list_goes_into_her_own_shopping_list(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The plugin builds no list of its own; Paprika renders it."""
    _plan_a_recipe(seeded, "1 lemon\n2 eggs")

    result = runner.invoke(app, ["write", "groceries", "push", *WEEK, "--done"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["changed"] == {"groceries": 2}
    assert {i["name"] for i in seeded.groceries} == {"1 lemon", "2 eggs"}


def test_a_pushed_item_lands_on_her_default_list(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """`list_uid` is required, and the wrong one puts it on the hardware list."""
    _plan_a_recipe(seeded, "1 lemon")

    runner.invoke(app, ["write", "groceries", "push", *WEEK])

    assert {i["list_uid"] for i in seeded.groceries} == {"LIST-1"}


def test_a_pushed_item_lets_paprika_file_it(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """An empty aisle is how her own scheme decides, rather than ours."""
    _plan_a_recipe(seeded, "1 lemon")

    runner.invoke(app, ["write", "groceries", "push", *WEEK])

    written = seeded.grocery_writes[-1][0]
    assert written["aisle"] == ""
    assert written["purchased"] is False


def test_a_pushed_item_says_what_it_is_for(
    signed_in: Path, seeded: FakePaprika
) -> None:
    _plan_a_recipe(seeded, "1 lemon")

    runner.invoke(app, ["write", "groceries", "push", *WEEK])

    assert seeded.grocery_writes[-1][0]["recipe"] == "Roast Lemon Chicken"


def test_the_push_reports_what_it_left_off(
    signed_in: Path, seeded: FakePaprika
) -> None:
    _plan_a_recipe(seeded, "2 tsp ground cumin\n1 lemon")

    envelope = envelope_of(
        runner.invoke(app, ["write", "groceries", "push", *WEEK]).stdout
    )

    assert envelope["data"]["added"] == ["1 lemon"]
    assert envelope["data"]["already_have"] == ["cumin"]


def test_a_pushed_list_can_be_undone(signed_in: Path, seeded: FakePaprika) -> None:
    _plan_a_recipe(seeded, "1 lemon\n2 eggs")
    runner.invoke(app, ["write", "groceries", "push", *WEEK])

    runner.invoke(app, ["write", "undo"])

    # Marking purchased is the only removal this API has.
    assert all(i["purchased"] for i in seeded.groceries)


def test_correcting_the_pantry_changes_the_next_draft(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """She can fix what she has without leaving the conversation."""
    _plan_a_recipe(seeded, "1 lemon\n2 eggs")
    before = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)
    assert len(before["data"]["buy"]) == 2

    runner.invoke(app, ["write", "pantry", "add", "eggs"])

    after = envelope_of(runner.invoke(app, ["grocery-draft", *WEEK]).stdout)
    assert [item["line"] for item in after["data"]["buy"]] == ["1 lemon"]
    assert after["data"]["already_have"] == ["eggs"]
