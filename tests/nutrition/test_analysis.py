"""One ingredient line in, one number with its provenance out — or no number.

End to end, against the real bundled data. The numbers asserted are the ones
USDA's own tables give, so a change that quietly moves them fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paprika_core.nutrition import (
    Quantified,
    Tier,
    Unquantified,
    Value,
    analyse,
    analyse_line,
    opened,
)
from paprika_core.nutrition.index import UsdaIndex
from paprika_core.nutrition.memo import Memos

RECIPE = [
    "1 lb boneless skinless chicken breast",
    "2 large yellow onions, diced",
    "salt to taste",
]


def amounts(value: Value) -> Quantified:
    """Assert a value is a number and return it.

    Args:
        value: The value.

    Returns:
        Quantified: The value.
    """
    assert isinstance(value, Quantified), getattr(value, "reason", "")
    return value


class TestWhatAWholeLineWorksOutTo:
    def test_a_weighed_ingredient_reaches_the_top_tier(self, index: UsdaIndex) -> None:
        value = amounts(analyse_line("1 lb boneless skinless chicken breast", index))

        assert value.provenance.tier is Tier.MEASURED
        assert value.provenance.evidence.matched_description is not None
        assert value.amounts.protein_g == pytest.approx(102.2, abs=1.0)

    def test_a_counted_ingredient_cannot_reach_it(self, index: UsdaIndex) -> None:
        """Two large onions is 300 g in USDA's table and 220-500 g in a shop."""
        value = amounts(analyse_line("2 large yellow onions, diced", index))

        assert value.provenance.tier < Tier.MEASURED
        assert value.amounts.energy_kcal == pytest.approx(114.0, abs=5.0)

    def test_every_number_is_traceable_to_a_record(self, index: UsdaIndex) -> None:
        """Provenance means inspectable, not just badged."""
        value = amounts(analyse_line("1 cup chopped onion", index))

        assert value.provenance.evidence.fdc_id == 170000
        assert value.provenance.evidence.matched_description == "Onions, raw"


class TestTheFourWaysToGetNoNumber:
    def test_an_open_ended_line(self, index: UsdaIndex) -> None:
        value = analyse_line("salt to taste", index)

        assert isinstance(value, Unquantified)
        assert value.quantity_stated is False
        assert value.provenance.tier is Tier.UNQUANTIFIED

    def test_a_food_nothing_matches(self, index: UsdaIndex) -> None:
        value = analyse_line("1 lb meat of your choice", index)

        assert isinstance(value, Unquantified)
        assert value.quantity_stated is True

    def test_a_quantity_nothing_can_weigh(self, index: UsdaIndex) -> None:
        value = analyse_line("a handful of parsley", index)

        assert isinstance(value, Unquantified)

    def test_a_line_with_no_food_in_it(self, index: UsdaIndex) -> None:
        value = analyse_line("   ", index)

        assert isinstance(value, Unquantified)


class TestAWholeIngredientList:
    def test_the_total_inherits_its_worst_ingredient(self, index: UsdaIndex) -> None:
        result = analyse(RECIPE, index)

        worst = min(value.provenance.tier for value in result.values[:2])
        assert result.total.provenance.tier <= worst

    def test_nothing_is_dropped_silently(self, index: UsdaIndex) -> None:
        result = analyse(RECIPE, index)

        assert "salt to taste" in result.total.provenance.evidence.omitted_lines

    def test_a_to_taste_omission_does_not_hollow_out_the_total(
        self, index: UsdaIndex
    ) -> None:
        result = analyse(RECIPE, index)

        assert result.total.provenance.evidence.omitted_measured_lines == ()

    def test_an_unmatched_measured_ingredient_caps_the_total(
        self, index: UsdaIndex
    ) -> None:
        result = analyse([*RECIPE, "1 lb meat of your choice"], index)

        assert result.total.provenance.tier is Tier.ESTIMATED
        assert result.total.provenance.evidence.omitted_measured_lines == (
            "1 lb meat of your choice",
        )

    def test_a_list_of_nothing_workable_has_no_total(self, index: UsdaIndex) -> None:
        result = analyse(["salt to taste", "pepper to taste"], index)

        assert isinstance(result.total, Unquantified)


class TestMemosInTheLoop:
    def test_the_second_pass_answers_from_the_memo(
        self, index: UsdaIndex, memos: Memos
    ) -> None:
        first = analyse_line("1 cup chopped onion", index, memos)
        second = analyse_line("1 cup chopped onion", index, memos)

        assert memos.count() == 1
        assert amounts(second).amounts == amounts(first).amounts
        assert second.provenance.tier is first.provenance.tier

    def test_a_recipe_is_never_part_of_the_key(
        self, index: UsdaIndex, memos: Memos
    ) -> None:
        analyse(RECIPE, index, memos)
        analyse(RECIPE, index, memos)

        assert memos.count() == len(RECIPE)


def test_opening_both_stores_puts_them_in_separate_files(paprika_home: Path) -> None:
    with opened() as (index, memos):
        assert index.path.name == "usda.sqlite3"
        assert memos.path.name == "nutrition.sqlite3"
        assert index.count() > 0
