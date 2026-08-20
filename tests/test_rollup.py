"""The week Rollup — uncertainty visible in the shape, not in a footnote.

A range is the normal rendering, so a bare number is rare enough to mean
something. Tier letters never reach her: the Tier decides the shape and then
stops existing as far as she is concerned.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from paprika_core.nutrition import rollup
from paprika_core.nutrition.tiers import (
    Amounts,
    Evidence,
    GramsBasis,
    Provenance,
    Quantified,
    Unquantified,
)
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_no_mechanics, envelope_of


def _amounts(energy: float = 100.0) -> Amounts:
    """Build amounts worth summing.

    Args:
        energy: Kilocalories.

    Returns:
        Amounts: The four.
    """
    return Amounts(energy_kcal=energy, protein_g=10.0, carbohydrate_g=20.0, fat_g=5.0)


def _measured(energy: float = 100.0) -> Quantified:
    """Build a fully measured value.

    Args:
        energy: Kilocalories.

    Returns:
        Quantified: A Tier A value.
    """
    return Quantified(
        _amounts(energy),
        Provenance(Evidence(grams_basis=GramsBasis.STATED_MASS, fdc_id=1)),
    )


def _derived(energy: float = 100.0) -> Quantified:
    """Build a value whose grams came from a portion rather than a scale.

    Args:
        energy: Kilocalories.

    Returns:
        Quantified: A Tier B value.
    """
    return Quantified(
        _amounts(energy),
        Provenance(Evidence(grams_basis=GramsBasis.PORTION_SIZE, fdc_id=1)),
    )


def _unquantified(line: str, *, stated: bool) -> Unquantified:
    """Build a value that earned no number.

    Args:
        line: The ingredient line.
        stated: Whether the line said how much.

    Returns:
        Unquantified: A Tier D value.
    """
    return Unquantified(
        Provenance(Evidence(grams_basis=GramsBasis.NONE, fdc_id=None)),
        reason="nothing matched",
        line=line,
        quantity_stated=stated,
    )


def test_a_range_is_the_normal_rendering() -> None:
    made = rollup._shape([_derived()], days=1, meals=1)

    energy = next(n for n in made.nutrients if n.name == "energy")
    assert energy.exact is False
    assert energy.low < energy.high


def test_a_bare_number_is_rare_enough_to_mean_something() -> None:
    """Reserved for fully measured, and even then capped by cooking.

    Anything summed from raw ingredients and shown as a cooked dish cannot be a
    point value, because cooking moves energy by as much as half — so a total is
    never exact, however clean its ingredients were.
    """
    made = rollup._shape([_measured()], days=1, meals=1)

    assert all(not n.exact for n in made.nutrients)


def test_no_tier_letter_ever_reaches_her() -> None:
    data = rollup.as_data(rollup._shape([_derived()], days=1, meals=1))

    rendered = str(data).casefold()
    for leak in ("tier", "measured", "derived", "estimated", "provenance", "grade"):
        assert leak not in rendered


def test_a_worse_ingredient_widens_the_whole_total() -> None:
    """A total inherits the provenance of its worst ingredient."""
    tight = rollup._shape([_derived(), _derived()], days=1, meals=1)
    loose = rollup._shape(
        [
            _derived(),
            Quantified(
                _amounts(),
                Provenance(Evidence(grams_basis=GramsBasis.ESTIMATED, fdc_id=1)),
            ),
        ],
        days=1,
        meals=1,
    )

    tight_energy = next(n for n in tight.nutrients if n.name == "energy")
    loose_energy = next(n for n in loose.nutrients if n.name == "energy")
    assert (loose_energy.high - loose_energy.low) > (
        tight_energy.high - tight_energy.low
    )


def test_an_unmatched_main_component_yields_no_number_at_all() -> None:
    """A total missing its meat is not a smaller total; it is a wrong one."""
    made = rollup._shape(
        [_measured(), _unquantified("1 lb beef, your choice", stated=True)],
        days=1,
        meals=1,
    )

    assert made.nutrients == ()
    assert made.refused == "1 lb beef, your choice"


def test_seasoning_is_footnoted_once_as_a_class() -> None:
    made = rollup._shape(
        [
            _derived(),
            _unquantified("salt to taste", stated=False),
            _unquantified("pepper to taste", stated=False),
        ],
        days=1,
        meals=1,
    )

    assert made.to_taste == 2
    assert made.excluded == ()
    assert made.nutrients


def test_anything_else_unmatched_is_named() -> None:  # noqa: D103
    made = rollup._shape(
        [_derived(), _unquantified("1 splash of something", stated=False)],
        days=1,
        meals=1,
    )

    assert made.excluded == ("1 splash of something",)


def test_the_single_weakest_input_is_named() -> None:
    """A disclaimer she can act on beats a paragraph about uncertainty."""
    made = rollup._shape(
        [_derived(), _unquantified("2 handfuls of greens", stated=True)],
        days=1,
        meals=1,
    )

    assert made.weakest == "2 handfuls of greens"


def test_nothing_worth_naming_names_nothing() -> None:
    made = rollup._shape([_derived(), _derived()], days=1, meals=1)

    assert made.weakest is None


def test_a_week_with_nothing_in_it_refuses_rather_than_reporting_zero() -> None:
    made = rollup._shape([], days=7, meals=0)

    assert made.nutrients == ()
    assert made.days == 7


def test_the_write_back_carries_its_own_hedge_and_date() -> None:
    """This string escapes to her phone, where nothing can explain it."""
    made = rollup._shape([_derived()], days=1, meals=1)

    text = rollup.written_back(made, "2026-08-20")

    assert "2026-08-20" in text
    assert "approximate" in text.casefold()
    assert "Energy:" in text


def test_the_write_back_refuses_when_no_number_was_earned() -> None:
    """Writing "we could not say" into her recipe is worse than writing nothing."""
    made = rollup._shape(
        [_unquantified("1 lb beef, your choice", stated=True)], days=1, meals=1
    )

    try:
        rollup.written_back(made, "2026-08-20")
    except ValueError:
        return
    raise AssertionError("a refusal was written back as though it were a number")


def test_the_write_back_shows_a_range_the_same_way_she_saw_it() -> None:
    made = rollup._shape([_derived()], days=1, meals=1)

    text = rollup.written_back(made, "2026-08-20")

    assert "–" in text


def test_the_write_back_names_what_it_left_out() -> None:
    made = rollup._shape(
        [_derived(), _unquantified("1 splash of something", stated=False)],
        days=1,
        meals=1,
    )

    assert "1 splash of something" in rollup.written_back(made, "2026-08-20")


def test_a_week_is_rolled_up_through_the_command(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """End to end: the Plan, her recipes, and the bundled data."""
    runner = CliRunner()
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app, ["nutrition", "rollup", "--from", "2026-08-24", "--to", "2026-08-30"]
    )

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["data"]["meals"] >= 1
    assert_no_mechanics(envelope)


def test_numbers_never_appear_unasked(signed_in: Path, seeded: FakePaprika) -> None:
    """Computed on request. Nothing is journaled and nothing rides on a plan."""
    runner = CliRunner()
    runner.invoke(app, ["sync"])

    plan = envelope_of(runner.invoke(app, ["plan", "show"]).stdout)
    index = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)

    for rendered in (str(plan), str(index)):
        for leak in ("kcal", "protein", "energy_kcal"):
            assert leak not in rendered


def test_one_recipe_can_be_rolled_up(signed_in: Path, seeded: FakePaprika) -> None:
    runner = CliRunner()
    runner.invoke(app, ["sync"])
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    handle = str(next(entry for entry in lines if "Cod" in entry).split(" | ")[0])

    result = runner.invoke(app, ["nutrition", "recipe", handle])

    assert result.exit_code == 0
    assert_no_mechanics(envelope_of(result.stdout))
