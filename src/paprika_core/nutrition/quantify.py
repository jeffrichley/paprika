"""Turning a quantity into grams, and refusing to when it cannot be done.

This is where every open-source recipe manager has stalled — Tandoor, Mealie and
Grocy independently name the same blocker, and it is not food-name matching, it
is volume to grams. USDA's portion tables are the only broad free answer, and
USDA disclaims them: portion weights "may not be applicable for calculating
density or weight per volume for any specific liquid," and represent "a
composite of several similar products."

So the ladder below descends deliberately and says out loud which rung it landed
on. Its rungs, in order:

1. the line stated a mass — no food, no conversion, no doubt;
2. the parsed unit matched an actual portion on the matched record;
3. a size or count portion on the matched record — `1 large` → 150 g;
4. a conversion from another volume portion on the same record;
5. the same measure borrowed from a different record for the same food;
6. nothing, which means no number.

Two things it never does. It never reads ``foodPortions[0]``: 24% of FNDDS
portion rows are code 90000, "Quantity not specified", they frequently sort
first, and for raw onion that row is 15 g where a whole onion is 148 g. And it
never invents a gram weight to avoid returning nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from paprika_core.nutrition.index import FoodRecord, UsdaIndex
from paprika_core.nutrition.matching import SIGNIFICANT_QUALIFIERS
from paprika_core.nutrition.parsing import ParsedIngredient
from paprika_core.nutrition.portions import Portion, PortionKind
from paprika_core.nutrition.tiers import GramsBasis
from paprika_core.nutrition.units import Dimension, dimension, to_grams, to_millilitres

#: Portion pieces that mean "one of the thing itself".
_WHOLE = ("whole", "each", "fruit", "item", "piece", "unit")


@final
@dataclass(frozen=True, slots=True)
class Weight:
    """A gram weight and how far down the ladder it came from.

    Attributes:
        grams: The weight.
        basis: Which rung answered.
        quantity_not_specified: The only portion available was USDA's own
            "Quantity not specified".
        ambiguities: Choices USDA offered that the line did not settle.
        unaccounted: What the line said that the weight could not honour.
    """

    grams: float
    basis: GramsBasis
    quantity_not_specified: bool = False
    ambiguities: tuple[str, ...] = ()
    unaccounted: tuple[str, ...] = ()


def _choose(
    portions: list[Portion], prep_words: tuple[str, ...]
) -> tuple[Portion | None, tuple[str, ...]]:
    """Choose between portions that answer the same question differently.

    `1 cup, chopped` is 160 g and `1 cup, sliced` is 115 g for the same onion —
    39% apart in USDA's own table — so when the line says which, we use it, and
    when it does not, we say that we picked.

    Args:
        portions: Portions that all answer the question.
        prep_words: The line's preparation words.

    Returns:
        tuple[Portion | None, tuple[str, ...]]: The chosen portion, and a note
            when the line did not determine the choice.
    """
    if not portions:
        return None, ()
    for portion in portions:
        if portion.qualifier and any(
            word in portion.qualifier.split() for word in prep_words
        ):
            return portion, ()
    if len(portions) == 1 and not portions[0].qualifier:
        return portions[0], ()
    unqualified = [portion for portion in portions if not portion.qualifier]
    chosen = unqualified[0] if unqualified else portions[len(portions) // 2]
    if len(portions) == 1:
        return chosen, ()
    return chosen, (
        f"USDA gives {len(portions)} different weights for this measure"
        f"{f'; the one for {chosen.qualifier!r} was used' if chosen.qualifier else ''}",
    )


def _avoid(words: tuple[str, ...]) -> frozenset[str]:
    """Return the specificity a borrowed portion should not come wrapped in.

    Args:
        words: The line's words.

    Returns:
        frozenset[str]: Significant qualifiers the line did not ask for.
    """
    return SIGNIFICANT_QUALIFIERS - set(words)


def weigh(
    parsed: ParsedIngredient,
    record: FoodRecord,
    index: UsdaIndex,
    words: tuple[str, ...],
) -> Weight | None:
    """Work out what one ingredient line weighs.

    Args:
        parsed: The parsed line.
        record: The matched record.
        index: The index, for borrowing a portion from a sibling record.
        words: The line's words, for choosing what to borrow from.

    Returns:
        Weight | None: The weight and its basis, or ``None`` when the question
            cannot be answered — which is a Tier D ingredient, not a guess.
    """
    if parsed.quantity is None:
        return None
    quantity = parsed.quantity

    if dimension(parsed.unit) is Dimension.MASS:
        grams = to_grams(quantity, parsed.unit)
        return None if grams is None else Weight(grams, GramsBasis.STATED_MASS)

    portions = index.portions(record.fdc_id)
    if dimension(parsed.unit) is Dimension.VOLUME:
        return _by_volume(quantity, parsed, portions, index, words)
    return _by_count(quantity, parsed, portions, index, words)


def _by_volume(
    quantity: float,
    parsed: ParsedIngredient,
    portions: list[Portion],
    index: UsdaIndex,
    words: tuple[str, ...],
) -> Weight | None:
    """Weigh a volume, descending the ladder rung by rung.

    Args:
        quantity: How many of the unit.
        parsed: The parsed line.
        portions: The matched record's portions.
        index: The index, for a sibling record's portion.
        words: The line's words, head word last.

    Returns:
        Weight | None: The weight, or ``None``.
    """
    measures = [portion for portion in portions if portion.kind is PortionKind.MEASURE]
    exact = [portion for portion in measures if portion.unit == parsed.unit]
    chosen, ambiguity = _choose(exact, parsed.prep_words)
    if chosen is not None:
        return Weight(
            quantity * chosen.grams, GramsBasis.PORTION_EXACT, ambiguities=ambiguity
        )

    convertible = [
        portion for portion in measures if dimension(portion.unit) is Dimension.VOLUME
    ]
    chosen, ambiguity = _choose(convertible, parsed.prep_words)
    if chosen is not None:
        wanted = to_millilitres(quantity, parsed.unit)
        have = to_millilitres(1.0, chosen.unit)
        if wanted is not None and have:
            return Weight(
                wanted / have * chosen.grams,
                GramsBasis.PORTION_CONVERTED,
                ambiguities=ambiguity,
            )

    borrowed = index.borrow(words, PortionKind.MEASURE, parsed.unit, _avoid(words))
    if borrowed is not None:
        return Weight(quantity * borrowed.grams, GramsBasis.PORTION_SIBLING)
    return None


def _by_count(
    quantity: float,
    parsed: ParsedIngredient,
    portions: list[Portion],
    index: UsdaIndex,
    words: tuple[str, ...],
) -> Weight | None:
    """Weigh a count, a size word, or a bare number of things.

    Args:
        quantity: How many.
        parsed: The parsed line.
        portions: The matched record's portions.
        index: The index, for a sibling record's portion.
        words: The line's words, head word last.

    Returns:
        Weight | None: The weight, or ``None`` when USDA has nothing that
            answers — `2 cans of tomatoes` against a record that has never heard
            of a can is a refusal, because a can is not a tomato.
    """
    if parsed.unit:
        return _by_piece(quantity, parsed, portions, index, words, parsed.unit)

    if parsed.size:
        sized = [
            portion
            for portion in portions
            if portion.kind is PortionKind.SIZE and portion.size == parsed.size
        ]
        chosen, ambiguity = _choose(sized, parsed.prep_words)
        if chosen is not None:
            return Weight(
                quantity * chosen.grams, GramsBasis.PORTION_SIZE, ambiguities=ambiguity
            )
        borrowed = index.borrow(words, PortionKind.SIZE, parsed.size, _avoid(words))
        if borrowed is not None:
            return Weight(quantity * borrowed.grams, GramsBasis.PORTION_SIBLING)

    for piece in _WHOLE:
        weight = _by_piece(quantity, parsed, portions, index, words, piece)
        if weight is not None:
            # The size word was given and USDA has no gradation for this food,
            # so it went unused. That is information lost, and it is recorded.
            unaccounted = (parsed.size,) if parsed.size else ()
            return Weight(
                weight.grams,
                weight.basis,
                ambiguities=weight.ambiguities,
                unaccounted=unaccounted,
            )

    unspecified = [
        portion for portion in portions if portion.kind is PortionKind.UNSPECIFIED
    ]
    if unspecified:
        return Weight(
            quantity * unspecified[0].grams,
            GramsBasis.PORTION_SIZE,
            quantity_not_specified=True,
        )
    return None


def _by_piece(
    quantity: float,
    parsed: ParsedIngredient,
    portions: list[Portion],
    index: UsdaIndex,
    words: tuple[str, ...],
    piece: str,
) -> Weight | None:
    """Weigh a countable thing — a clove, a slice, a whole one.

    Args:
        quantity: How many.
        parsed: The parsed line.
        portions: The matched record's portions.
        index: The index, for a sibling record's portion.
        words: The line's words, head word last.
        piece: The counted thing.

    Returns:
        Weight | None: The weight, or ``None``.
    """
    pieces = [
        portion
        for portion in portions
        if portion.kind is PortionKind.COUNT and portion.piece == piece
    ]
    chosen, ambiguity = _choose(pieces, parsed.prep_words)
    if chosen is not None:
        return Weight(
            quantity * chosen.grams, GramsBasis.PORTION_SIZE, ambiguities=ambiguity
        )
    borrowed = index.borrow(words, PortionKind.COUNT, piece, _avoid(words))
    if borrowed is not None:
        return Weight(quantity * borrowed.grams, GramsBasis.PORTION_SIBLING)
    return None
