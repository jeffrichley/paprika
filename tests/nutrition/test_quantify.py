"""The gram-weight ladder, rung by rung, and the refusal at the bottom of it."""

from __future__ import annotations

import pytest

from paprika_core.nutrition.index import FoodRecord, UsdaIndex
from paprika_core.nutrition.matching import match, query_words
from paprika_core.nutrition.parsing import parse_line
from paprika_core.nutrition.quantify import Weight, weigh
from paprika_core.nutrition.tiers import GramsBasis


def weighed(line: str, index: UsdaIndex) -> tuple[Weight, FoodRecord]:
    """Weigh one line against whatever it matches.

    Args:
        line: The ingredient line.
        index: The index.

    Returns:
        tuple[Weight, FoodRecord]: The weight and the record it came from.
    """
    parsed = parse_line(line)
    found = match(parsed, index)
    assert found is not None
    weight = weigh(parsed, found.record, index, query_words(parsed))
    assert weight is not None
    return weight, found.record


class TestTheTopOfTheLadder:
    def test_a_stated_mass_needs_no_food_and_no_conversion(
        self, index: UsdaIndex
    ) -> None:
        weight, _ = weighed("1 lb boneless skinless chicken breast", index)

        assert weight.basis is GramsBasis.STATED_MASS
        assert weight.grams == pytest.approx(453.59237)

    def test_a_unit_that_matched_a_real_portion_is_not_a_conversion(
        self, index: UsdaIndex
    ) -> None:
        weight, _ = weighed("1 cup chopped onion", index)

        assert weight.basis is GramsBasis.PORTION_EXACT
        assert weight.grams == 160.0


class TestTheMiddleOfTheLadder:
    def test_the_line_settles_which_cup_usda_meant(self, index: UsdaIndex) -> None:
        """160 g chopped against 115 g sliced — 39% apart, same food."""
        chopped, _ = weighed("1 cup onion, chopped", index)
        sliced, _ = weighed("1 cup onion, sliced", index)

        assert chopped.grams == 160.0
        assert sliced.grams == 115.0
        assert chopped.ambiguities == ()

    def test_a_choice_the_line_did_not_settle_is_written_down(
        self, index: UsdaIndex
    ) -> None:
        weight, _ = weighed("1 cup onion", index)

        assert weight.ambiguities != ()

    def test_a_size_word_resolves_through_usdas_own_gradation(
        self, index: UsdaIndex
    ) -> None:
        weight, _ = weighed("2 large onions", index)

        assert weight.grams == 300.0

    def test_a_volume_converts_from_another_volume_on_the_same_record(
        self, index: UsdaIndex
    ) -> None:
        weight, _ = weighed("1 quart chicken stock", index)

        assert weight.basis is GramsBasis.PORTION_CONVERTED
        assert weight.grams == pytest.approx(960.0, rel=0.01)

    def test_a_portion_borrowed_from_a_sibling_says_that_it_was(
        self, index: UsdaIndex
    ) -> None:
        """Foundation has the better nutrients and no size gradation at all."""
        weight, record = weighed("2 large yellow onions", index)

        assert record.data_type == "foundation_food"
        assert weight.basis is GramsBasis.PORTION_SIBLING
        assert weight.grams == 300.0

    def test_a_measure_is_borrowed_when_the_record_records_no_portions(
        self, index: UsdaIndex
    ) -> None:
        """A cup of flour is the single largest guess in most baked goods."""
        weight, _ = weighed("1 cup all-purpose flour", index)

        assert weight.basis is GramsBasis.PORTION_SIBLING
        assert weight.grams == 125.0

    def test_a_counted_thing_is_borrowed_the_same_way(self, index: UsdaIndex) -> None:
        weight, _ = weighed("2 cans chickpeas", index)

        assert weight.basis is GramsBasis.PORTION_SIBLING

    def test_a_bare_count_falls_to_what_usda_calls_a_whole_one(
        self, index: UsdaIndex
    ) -> None:
        weight, _ = weighed("2 bananas", index)

        assert weight.grams > 0

    def test_a_size_word_usda_has_no_gradation_for_is_recorded_as_unused(
        self, index: UsdaIndex
    ) -> None:
        """A whole leek is a whole leek; USDA does not know a large one."""
        weight, _ = weighed("2 large leeks", index)

        assert weight.unaccounted == ("large",)


class TestTheBottomOfTheLadder:
    def test_a_measure_nobody_records_gets_no_number(self, index: UsdaIndex) -> None:
        """Nobody knows what a handful is, so nothing here pretends to."""
        parsed = parse_line("a handful of parsley")
        found = match(parsed, index)
        assert found is not None
        assert weigh(parsed, found.record, index, query_words(parsed)) is None

    def test_a_volume_nothing_can_convert_gets_no_number(
        self, index: UsdaIndex
    ) -> None:
        """Neither the record nor any sibling records a fluid ounce of it."""
        parsed = parse_line("1 fl oz vanilla extract")
        found = match(parsed, index)
        assert found is not None
        assert weigh(parsed, found.record, index, query_words(parsed)) is None

    def test_a_line_with_no_quantity_gets_no_number(self, index: UsdaIndex) -> None:
        parsed = parse_line("salt to taste")
        found = match(parsed, index)
        assert found is not None
        assert weigh(parsed, found.record, index, query_words(parsed)) is None
