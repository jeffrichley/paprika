"""Units — mass converts, volume does not, and a count word is just a word."""

from __future__ import annotations

import pytest

from paprika_core.nutrition.units import (
    Dimension,
    canonical_unit,
    dimension,
    singular,
    to_grams,
    to_millilitres,
)


@pytest.mark.parametrize(
    ("written", "canonical"),
    [
        ("Tablespoons", "tbsp"),
        ("tbs", "tbsp"),
        ("teaspoon", "tsp"),
        ("GRAMS", "g"),
        ("ounces", "oz"),
        ("pound", "lb"),
        ("fluid ounces", "fl oz"),
        ("cups", "cup"),
        ("millilitres", "ml"),
        ("cloves", "clove"),
        ("", ""),
    ],
)
def test_both_sides_of_a_comparison_spell_a_unit_the_same_way(
    written: str, canonical: str
) -> None:
    assert canonical_unit(written) == canonical


def test_a_mass_converts_without_any_food_being_involved() -> None:
    assert to_grams(1.0, "lb") == pytest.approx(453.59237)
    assert to_grams(2.0, "oz") == pytest.approx(56.69904625)


def test_a_volume_does_not_convert_to_grams() -> None:
    """A cup of chopped onion is 160 g and a cup of sliced is 115 g."""
    assert to_grams(1.0, "cup") is None


def test_a_volume_converts_to_millilitres() -> None:
    assert to_millilitres(1.0, "cup") == pytest.approx(236.5882365)
    assert to_millilitres(1.0, "g") is None


def test_a_count_word_is_neither() -> None:
    assert dimension("clove") is Dimension.COUNT
    assert dimension("cup") is Dimension.VOLUME
    assert dimension("kg") is Dimension.MASS


def test_singularising_is_crude_but_symmetric() -> None:
    """It is applied to USDA's word and to hers, so a wrong singular still matches."""
    assert singular("rings") == "ring"
    assert singular("slices") == "slice"
    assert singular("glass") == "glass"
    assert singular("dish") == "dish"
    assert singular("dishes") == "dish"
