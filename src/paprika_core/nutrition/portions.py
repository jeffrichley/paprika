"""Reading USDA's portion rows, which mean three different things.

``food_portion`` has one schema and three incompatible populations, and a
generic parser over it produces confident nonsense:

============  ==================  =====================  =========================
Data type     ``measure_unit_id``  ``portion_description``  ``modifier``
============  ==================  =====================  =========================
Foundation    a real unit          empty                   free-text qualifier
SR Legacy     ``9999`` on all      empty                   the measure, as prose
FNDDS         ``9999`` on all      the measure, as text    a numeric portion code
============  ==================  =====================  =========================

So ``parse_portion(modifier)`` is a bug: in FNDDS that column is a foreign key.
And in SR Legacy, reading USDA's portion data means parsing USDA's own free text
— a second parsing problem nested inside the first.

One row deserves naming: FNDDS code ``90000`` is "Quantity not specified", it is
24% of all FNDDS portion rows, and it frequently sorts first. For `Onions, raw`
it is 15 g where a whole onion is 148 g. Any code that takes ``portions[0]`` is
wrong by 10× some of the time, which is why nothing here ever indexes by
position.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import final

from paprika_core.nutrition.units import Dimension, canonical_unit, dimension, singular

#: The FNDDS portion code for "Quantity not specified".
QUANTITY_NOT_SPECIFIED = "90000"

#: Words USDA uses for a size gradation. Not units — a size word has no fixed
#: gram value, and USDA's own table has a large onion at 114% of a small one.
SIZE_WORDS = frozenset(
    {
        "small",
        "medium",
        "large",
        "extra large",
        "extra small",
        "jumbo",
        "mini",
        "tiny",
        "baby",
        "giant",
    }
)

_LEADING_AMOUNT = re.compile(r"^\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+))?\s+(.*)$")
_PARENTHETICAL = re.compile(r"\([^)]*\)")


class PortionKind(StrEnum):
    """What a portion row can answer."""

    #: A unit with a table behind it — `cup`, `tbsp`, `g`.
    MEASURE = "measure"
    #: A size gradation — `large`, `medium`.
    SIZE = "size"
    #: A thing you can count — `whole`, `slice`, `clove`, `serving`.
    COUNT = "count"
    #: FNDDS "Quantity not specified". Never used unless nothing else exists.
    UNSPECIFIED = "unspecified"


@final
@dataclass(frozen=True, slots=True)
class Portion:
    """One USDA portion, read according to the data type that wrote it.

    Attributes:
        kind: What the portion can answer.
        unit: The canonical unit, for :attr:`PortionKind.MEASURE`.
        size: The size word, for :attr:`PortionKind.SIZE`.
        piece: The counted thing, for :attr:`PortionKind.COUNT`.
        qualifier: USDA's own trailing prose — `chopped`, `sliced`. Kept because
            `1 cup, chopped` is 160 g and `1 cup, sliced` is 115 g.
        grams: Grams for **one** of whatever this portion measures, with USDA's
            own multiplier already divided out.
    """

    kind: PortionKind
    unit: str
    size: str
    piece: str
    qualifier: str
    grams: float


def _split_leading_amount(text: str) -> tuple[float, str]:
    """Separate a count FNDDS wrote into its portion text.

    Args:
        text: Portion text such as ``1 cup`` or ``2 slices``.

    Returns:
        tuple[float, str]: The count and the remaining text. The count is ``1.0``
            when there is none.
    """
    match = _LEADING_AMOUNT.match(text)
    if match is None:
        return 1.0, text.strip()
    whole = float(match.group(1))
    if match.group(2):
        whole = whole / float(match.group(2))
    return whole, match.group(3).strip()


def classify(text: str) -> tuple[PortionKind, str, str, str, str]:
    """Read one piece of USDA portion prose.

    Args:
        text: The measure, as USDA wrote it — ``cup, chopped``,
            ``slice, medium (1/8" thick)``, ``large``, ``rings``.

    Returns:
        tuple[PortionKind, str, str, str, str]: Kind, unit, size, piece and
            qualifier.
    """
    cleaned = _PARENTHETICAL.sub(" ", text).lower()
    head, _, tail = cleaned.partition(",")
    qualifier = " ".join(tail.split())
    words = head.split()
    if not words:
        return PortionKind.COUNT, "", "", "", qualifier

    # Longest first, so `fluid ounce` and `extra large` beat their first word.
    for length in (2, 1):
        if len(words) < length:
            continue
        phrase = " ".join(words[:length])
        rest = " ".join(words[length:])
        if phrase in SIZE_WORDS:
            return PortionKind.SIZE, "", phrase, "", _join(rest, qualifier)
        unit = canonical_unit(phrase)
        if dimension(unit) is not Dimension.COUNT:
            return PortionKind.MEASURE, unit, "", "", _join(rest, qualifier)

    piece = singular(words[0])
    return PortionKind.COUNT, "", "", piece, _join(" ".join(words[1:]), qualifier)


def _join(*parts: str) -> str:
    """Join the non-empty parts of a qualifier.

    Args:
        *parts: The parts.

    Returns:
        str: The parts, space-separated, without the empty ones.
    """
    return " ".join(part for part in parts if part).strip()


def parse_portion(
    data_type: str,
    amount: str,
    measure_unit: str,
    portion_description: str,
    modifier: str,
    gram_weight: str,
) -> Portion | None:
    """Read one ``food_portion`` row according to who wrote it.

    Args:
        data_type: The food's FoodData Central data type.
        amount: The row's ``amount`` column.
        measure_unit: The row's ``measure_unit_id``, already resolved to a name.
        portion_description: The row's ``portion_description`` column.
        modifier: The row's ``modifier`` column.
        gram_weight: The row's ``gram_weight`` column.

    Returns:
        Portion | None: The portion, or ``None`` when the row carries no usable
            weight at all.
    """
    try:
        grams = float(gram_weight)
    except ValueError:
        return None
    if grams <= 0:
        return None

    if data_type == "survey_fndds_food":
        if modifier.strip() == QUANTITY_NOT_SPECIFIED:
            return Portion(PortionKind.UNSPECIFIED, "", "", "", "", grams)
        count, text = _split_leading_amount(portion_description)
        qualifier = ""
    elif data_type == "sr_legacy_food":
        count = _as_count(amount)
        text = modifier
        qualifier = ""
    else:
        count = _as_count(amount)
        text = measure_unit
        qualifier = " ".join(_PARENTHETICAL.sub(" ", modifier).lower().split())

    if not text.strip() or count <= 0:
        return None
    kind, unit, size, piece, own_qualifier = classify(text)
    return Portion(
        kind=kind,
        unit=unit,
        size=size,
        piece=piece,
        qualifier=_join(own_qualifier, qualifier),
        grams=grams / count,
    )


def _as_count(amount: str) -> float:
    """Read a portion's multiplier.

    Args:
        amount: The ``amount`` column.

    Returns:
        float: The multiplier, defaulting to one when the column is empty.
    """
    try:
        return float(amount)
    except ValueError:
        return 1.0
