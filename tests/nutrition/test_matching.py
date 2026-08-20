"""Matching — the stage that fails silently, tested against the cases it failed on.

Every ingredient here is one the research doc ran through a leading open-source
matcher and a commercial API. Both reported confidence around 1.0 while
inventing specificity. What is asserted below is not that we get the right
record — nobody reliably does — but that when we do not, the line's own words
say so.
"""

from __future__ import annotations

import pytest

from paprika_core.nutrition.index import UsdaIndex
from paprika_core.nutrition.matching import match, query_words
from paprika_core.nutrition.parsing import parse_line


def matched(
    line: str, index: UsdaIndex
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Match one line and return what it cost.

    Args:
        line: The ingredient line.
        index: The index.

    Returns:
        tuple[str, tuple[str, ...], tuple[str, ...]]: The matched description,
            the dropped words, and the qualifiers the record added.
    """
    found = match(parse_line(line), index)
    assert found is not None
    return found.record.description, found.dropped, found.unrequested


class TestTheRecordsTheDocCaughtOtherMatchersOn:
    def test_butter_does_not_silently_become_unsalted_stick_butter(
        self, index: UsdaIndex
    ) -> None:
        """Confidence 1.0 on `butter` → `Butter, stick, unsalted` is the case."""
        description, dropped, unrequested = matched("2 tbsp butter", index)

        assert dropped == ()
        assert unrequested == ()
        assert "unsalted" not in description.lower()

    def test_salt_does_not_silently_become_iodized_salt(self, index: UsdaIndex) -> None:
        description, _, unrequested = matched("1 tsp salt", index)

        assert "iodized" not in description.lower()
        assert unrequested == ()

    def test_milk_does_not_have_a_fat_percentage_invented_for_it(
        self, index: UsdaIndex
    ) -> None:
        """`closestUnbranded` turned `milk` into `Milk, fluid, 1% fat`."""
        description, _, unrequested = matched("1 cup milk", index)

        assert "%" not in description
        assert unrequested == ()

    def test_dropping_yellow_from_yellow_onion_is_recorded_when_it_happens(
        self, index: UsdaIndex
    ) -> None:
        """Zestful labelled this lossy match `matchMethod: "exact"`."""
        description, dropped, _ = matched("1 cup chopped yellow onion", index)

        assert "yellow" in description.lower() or "yellow" in dropped


class TestARecordIsNotHerFoodJustBecauseItSharesAWord:
    def test_a_line_whose_words_mostly_went_unmatched_is_refused(
        self, index: UsdaIndex
    ) -> None:
        """USDA grades beef `choice`, so `meat of your choice` finds a ribeye."""
        assert match(parse_line("1 lb meat of your choice"), index) is None

    def test_a_food_nothing_in_the_index_carries_is_refused(
        self, index: UsdaIndex
    ) -> None:
        assert match(parse_line("2 cups frobnicated wibblefruit"), index) is None

    def test_a_dish_that_merely_mentions_the_food_does_not_win(
        self, index: UsdaIndex
    ) -> None:
        """`plain flour` matches a pretzel on word coverage alone."""
        description, _, _ = matched("250 g plain flour", index)

        assert "pretzel" not in description.lower()
        assert description.lower().startswith("flour")


class TestThePreferencesTheResearchDocAsksFor:
    def test_the_raw_record_wins_when_the_line_did_not_ask_for_cooked(
        self, index: UsdaIndex
    ) -> None:
        """FNDDS `cooked, fat added` is +92% energy and 147× the sodium."""
        description, _, _ = matched("2 large onions", index)

        assert "fat added" not in description.lower()
        assert "raw" in description.lower()

    def test_a_line_that_asks_for_cooked_is_allowed_to_have_it(
        self, index: UsdaIndex
    ) -> None:
        description, _, _ = matched("1 cup cooked rice", index)

        assert "cooked" in description.lower()

    def test_a_part_of_the_food_is_not_the_food(self, index: UsdaIndex) -> None:
        """`3 large eggs` is not three yolks, which sit beside it in the index."""
        description, _, _ = matched("3 large eggs", index)

        assert "yolk" not in description.lower()
        assert "white" not in description.lower()

    def test_a_can_says_canned_rather_than_costing_the_match(
        self, index: UsdaIndex
    ) -> None:
        description, _, unrequested = matched("1 (14.5 oz) can diced tomatoes", index)

        assert "canned" in description.lower()
        assert unrequested == ()


class TestTheWordsAMatchIsMadeOf:
    def test_preparation_that_changes_the_food_joins_the_query(self) -> None:
        assert "dried" in query_words(parse_line("1 cup apricots, dried"))

    def test_preparation_that_is_only_knife_work_does_not(self) -> None:
        assert "diced" not in query_words(parse_line("1 onion, diced"))

    def test_the_size_word_is_not_part_of_the_query(self) -> None:
        """`large` is a portion question, not an identity one."""
        assert "large" not in query_words(parse_line("2 large onions"))

    @pytest.mark.parametrize("line", ["1 can chopped tomatoes", "1 jar passata"])
    def test_a_container_that_is_also_an_identity_is_carried_across(
        self, line: str
    ) -> None:
        assert "canned" in query_words(parse_line(line))
