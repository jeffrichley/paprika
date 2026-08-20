"""USDA's portion rows, which share one schema and mean three different things.

Every row here is verbatim from the bulk CSVs.
"""

from __future__ import annotations

import pytest

from paprika_core.nutrition.portions import Portion, PortionKind, parse_portion


def sr_legacy(amount: str, modifier: str, grams: str) -> Portion:
    """Read one SR Legacy row, where the modifier is the measure as prose.

    Args:
        amount: The row's amount.
        modifier: The row's modifier.
        grams: The row's gram weight.

    Returns:
        Portion: The parsed portion.
    """
    portion = parse_portion("sr_legacy_food", amount, "", "", modifier, grams)
    assert portion is not None
    return portion


def fndds(description: str, modifier: str, grams: str) -> Portion:
    """Read one FNDDS row, where the modifier is a numeric portion code.

    Args:
        description: The row's portion description.
        modifier: The row's modifier.
        grams: The row's gram weight.

    Returns:
        Portion: The parsed portion.
    """
    portion = parse_portion("survey_fndds_food", "", "", description, modifier, grams)
    assert portion is not None
    return portion


class TestSrLegacyWritesTheMeasureAsProse:
    def test_a_size_word_is_a_size_and_not_a_unit(self) -> None:
        portion = sr_legacy("1", "large", "150")

        assert portion.kind is PortionKind.SIZE
        assert portion.size == "large"
        assert portion.grams == 150.0

    def test_a_unit_keeps_usdas_own_qualifier(self) -> None:
        """`1 cup, chopped` is 160 g and `1 cup, sliced` is 115 g."""
        chopped = sr_legacy("1", "cup, chopped", "160")
        sliced = sr_legacy("1", "cup, sliced", "115")

        assert chopped.unit == sliced.unit == "cup"
        assert chopped.qualifier == "chopped"
        assert sliced.qualifier == "sliced"

    def test_a_parenthetical_dimension_does_not_become_the_measure(self) -> None:
        portion = sr_legacy("1", 'slice, medium (1/8" thick)', "14")

        assert portion.kind is PortionKind.COUNT
        assert portion.piece == "slice"

    def test_usdas_own_multiplier_is_divided_out(self) -> None:
        """`10 rings` weighing 60 g is 6 g a ring."""
        portion = sr_legacy("10", "rings", "60")

        assert portion.piece == "ring"
        assert portion.grams == 6.0

    def test_a_space_separated_unit_is_still_a_unit(self) -> None:
        portion = sr_legacy("1", "tbsp chopped", "10")

        assert portion.kind is PortionKind.MEASURE
        assert portion.unit == "tbsp"


class TestFnddsWritesTheMeasureInTheDescription:
    def test_the_leading_count_is_taken_off_the_description(self) -> None:
        portion = fndds("1 cup", "10205", "160.0")

        assert portion.kind is PortionKind.MEASURE
        assert portion.unit == "cup"
        assert portion.grams == 160.0

    def test_the_modifier_is_a_foreign_key_and_never_prose(self) -> None:
        """Parsing 62368 as a measure is the bug this test exists to catch."""
        portion = fndds("1 whole", "62368", "148.0")

        assert portion.kind is PortionKind.COUNT
        assert portion.piece == "whole"
        assert portion.qualifier == ""

    def test_quantity_not_specified_is_marked_rather_than_read(self) -> None:
        """Code 90000 is 24% of all FNDDS portion rows, and often sorts first."""
        portion = fndds("Quantity not specified", "90000", "15.0")

        assert portion.kind is PortionKind.UNSPECIFIED

    def test_a_count_greater_than_one_is_divided_out(self) -> None:
        portion = fndds("2 slices", "61935", "30.0")

        assert portion.piece == "slice"
        assert portion.grams == 15.0


class TestFoundationWritesARealUnitId:
    def test_the_resolved_unit_name_is_the_measure(self) -> None:
        portion = parse_portion("foundation_food", "2.0", "tablespoon", "", "", "35.8")

        assert portion is not None
        assert portion.kind is PortionKind.MEASURE
        assert portion.unit == "tbsp"
        assert portion.grams == pytest.approx(17.9)

    def test_the_modifier_is_a_qualifier(self) -> None:
        portion = parse_portion("foundation_food", "1", "cup", "", "sliced", "115")

        assert portion is not None
        assert portion.qualifier == "sliced"


class TestARowWithNothingUsableIsNotAPortion:
    def test_a_zero_weight_is_refused(self) -> None:
        row = parse_portion(
            "survey_fndds_food", "", "", "Quantity not specified", "90000", "0.0"
        )
        assert row is None

    def test_an_unreadable_weight_is_refused(self) -> None:
        assert parse_portion("sr_legacy_food", "1", "", "", "large", "") is None

    def test_a_row_with_no_measure_at_all_is_refused(self) -> None:
        assert parse_portion("sr_legacy_food", "1", "", "", "", "50") is None

    def test_a_zero_multiplier_is_refused(self) -> None:
        assert parse_portion("sr_legacy_food", "0", "", "", "large", "50") is None
