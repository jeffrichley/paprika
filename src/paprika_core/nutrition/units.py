"""Units, and the only two questions worth asking about one.

Is it a mass? Then it converts to grams with no food in the loop, and it is the
one input that can reach the top tier. Is it a volume? Then it converts to
millilitres, but *not* to grams — a cup of chopped onion is 160 g and a cup of
sliced onion is 115 g, in USDA's own table, for the same food. Volume becomes
mass only through a portion record on the matched food, and USDA explicitly
disclaims even that as a density source.

Anything else — a clove, a can, a slice — is a count word. It is kept as a word
and matched literally against USDA's own portion text, because there is nothing
to convert it with.
"""

from __future__ import annotations

from enum import StrEnum

#: Grams per unit of mass. Exact by definition of the international pound.
MASS_GRAMS = {
    "mg": 0.001,
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.349523125,
    "lb": 453.59237,
}

#: Millilitres per unit of volume, US customary — the system USDA measures in.
VOLUME_ML = {
    "ml": 1.0,
    "l": 1000.0,
    "tsp": 4.92892159375,
    "tbsp": 14.78676478125,
    "fl oz": 29.5735295625,
    "cup": 236.5882365,
    "pint": 473.176473,
    "quart": 946.352946,
    "gallon": 3785.411784,
}

_ALIASES = {
    "milligram": "mg",
    "milligrams": "mg",
    "gram": "g",
    "grams": "g",
    "gm": "g",
    "gms": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "ounce": "oz",
    "ounces": "oz",
    "ozs": "oz",
    "pound": "lb",
    "pounds": "lb",
    "lbs": "lb",
    "millilitre": "ml",
    "milliliter": "ml",
    "millilitres": "ml",
    "milliliters": "ml",
    "litre": "l",
    "liter": "l",
    "litres": "l",
    "liters": "l",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsps": "tsp",
    "t": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsps": "tbsp",
    "tbs": "tbsp",
    "tb": "tbsp",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
    "floz": "fl oz",
    "fl. oz.": "fl oz",
    "c": "cup",
    "cups": "cup",
    "pints": "pint",
    "pt": "pint",
    "quarts": "quart",
    "qt": "quart",
    "gallons": "gallon",
    "gal": "gallon",
}


class Dimension(StrEnum):
    """What kind of thing a unit measures."""

    MASS = "mass"
    VOLUME = "volume"
    #: A count word — `clove`, `can`, `slice`. Not convertible to anything.
    COUNT = "count"


def canonical_unit(text: str) -> str:
    """Reduce a unit word to the spelling this package uses.

    Both sides of every comparison go through here — the unit a recipe line wrote
    and the unit USDA's portion text wrote — so consistency matters more than any
    single spelling being the *right* one.

    Args:
        text: The unit as written.

    Returns:
        str: The canonical spelling, or the singularised original when it is a
            count word we have no table for.
    """
    word = " ".join(text.lower().replace(".", " ").split())
    if not word:
        return ""
    if word in MASS_GRAMS or word in VOLUME_ML:
        return word
    if word in _ALIASES:
        return _ALIASES[word]
    return singular(word)


def singular(word: str) -> str:
    """Strip a plural ``s`` so both sides of a comparison agree.

    Deliberately crude. It is applied identically to the recipe's word and to
    USDA's, so a wrong singular is still a matching one.

    Args:
        word: The word.

    Returns:
        str: The word, without a trailing ``s`` when that leaves something.
    """
    if len(word) > 3 and word.endswith("es") and word[-3] in "shx":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def dimension(unit: str) -> Dimension:
    """Return what a canonical unit measures.

    Args:
        unit: A canonical unit.

    Returns:
        Dimension: Mass, volume, or a count word.
    """
    if unit in MASS_GRAMS:
        return Dimension.MASS
    if unit in VOLUME_ML:
        return Dimension.VOLUME
    return Dimension.COUNT


def to_grams(quantity: float, unit: str) -> float | None:
    """Convert a mass to grams.

    Args:
        quantity: How many.
        unit: A canonical unit.

    Returns:
        float | None: The grams, or ``None`` when the unit is not a mass — which
            is a refusal, not a zero.
    """
    factor = MASS_GRAMS.get(unit)
    return None if factor is None else quantity * factor


def to_millilitres(quantity: float, unit: str) -> float | None:
    """Convert a volume to millilitres.

    Args:
        quantity: How many.
        unit: A canonical unit.

    Returns:
        float | None: The millilitres, or ``None`` when the unit is not a volume.
    """
    factor = VOLUME_ML.get(unit)
    return None if factor is None else quantity * factor
