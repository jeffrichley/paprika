"""Choosing a record, and writing down what choosing it cost.

This is the stage that fails silently. The best published USDA-specific matcher
gets *a* match for 94.49% of ingredients and the *right* one for 71.6% — it
returns a confident wrong record about a quarter of the time — and the matchers
that report confidence report it wrong: `butter` → `Butter, stick, unsalted` at
1.0, `salt` → `Salt, table, iodized` at 1.0, `milk` → a record that invented a
fat percentage.

So there are two entirely separate things in this module and they must not be
confused:

* :func:`_rank` orders candidates. It is a preference, it is arbitrary where the
  evidence runs out, and it decides **nothing** about how much a number is worth.
* :func:`match` writes down what is structurally true about the record it chose —
  which of the line's words the record does not carry, which words the record
  adds that the line never asked for, and which data type it came from. That,
  and only that, reaches :class:`~paprika_core.nutrition.tiers.Evidence`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from paprika_core.nutrition.index import FoodRecord, UsdaIndex
from paprika_core.nutrition.parsing import ParsedIngredient
from paprika_core.nutrition.tokens import tokenise

#: Words a USDA description can add that change the food nutritionally. Salted
#: versus unsalted butter is a real difference, and a matcher inventing one is
#: the failure this whole module is arranged around.
SIGNIFICANT_QUALIFIERS = frozenset(
    {
        "salted",
        "unsalted",
        "iodized",
        "sweetened",
        "unsweetened",
        "skim",
        "nonfat",
        "lowfat",
        "fat",
        "free",
        "light",
        "reduced",
        "enriched",
        "unenriched",
        "fortified",
        "cooked",
        "boiled",
        "fried",
        "sauteed",
        "roasted",
        "baked",
        "grilled",
        "toasted",
        "dried",
        "dehydrated",
        "canned",
        "frozen",
        "smoked",
        "creamed",
        "whipped",
        "condensed",
        "instant",
        "salt",
        "1%",
        "2%",
        # A part of the food rather than the food. `3 large eggs` is not three
        # yolks, and USDA's yolk and white records sit right beside the whole
        # egg with the same head word.
        "yolk",
        "white",
        "skin",
        "seed",
        "leaf",
        "kernel",
        "juice",
        "peel",
        "rind",
        "pulp",
    }
)

#: Words that assert the *absence* of added specificity — USDA's own way of
#: saying "no further detail", or of saying "the whole food" — so they cost
#: nothing.
NEUTRAL_WORDS = frozenset({"nfs", "ns", "raw", "whole", "ingredient", "all", "purpose"})

#: FNDDS records coded as eaten rather than as an ingredient. `cooked, fat
#: added` double-counts a recipe's own oil — 73 kcal against 38 for raw onion —
#: and even `no added fat` carries 141 mg of sodium from nowhere, because the
#: survey's respondents salted their food. Never the best answer for a line in
#: an ingredient list.
_AS_EATEN = ("fat added", "no added fat", "ns as to fat")

#: Count words that also say what the food is. Deliberately three: a container
#: word is normally about packaging, and this is the case where it is not.
_CONTAINER_IDENTITY = {"can": "canned", "tin": "canned", "jar": "canned"}

#: Words that mean the line wanted something other than the raw ingredient.
_COOKED_WORDS = frozenset(
    {"cooked", "roasted", "boiled", "fried", "baked", "grilled", "steamed", "toasted"}
)

_DATA_TYPE_PREFERENCE = {
    # 18.4% of SR Legacy foods are raw commodities against 2.7% of FNDDS, and
    # raw commodities are most of what an ingredient list contains.
    "sr_legacy_food": 2,
    "foundation_food": 1,
    "survey_fndds_food": 0,
}


@final
@dataclass(frozen=True, slots=True)
class Match:
    """A chosen record and the structural cost of choosing it.

    Attributes:
        record: The record.
        dropped: Words the line gave that the record does not carry.
        unrequested: Nutritionally significant words the record adds.
    """

    record: FoodRecord
    dropped: tuple[str, ...]
    unrequested: tuple[str, ...]


def query_words(parsed: ParsedIngredient) -> tuple[str, ...]:
    """Reduce a parsed line to the words a search should be made of.

    Preparation that changes what the food *is* — roasted, dried, canned — joins
    the query. Preparation that changes only the knife work is already absent,
    and the size word is deliberately absent too: `large` is a portion question,
    not an identity one.

    One count word does double duty and has to be carried across: a line saying
    `1 can` is saying the tomatoes are canned, which is a real nutritional
    difference and would otherwise be charged against the match as specificity
    the record invented.

    Args:
        parsed: The parsed line.

    Returns:
        tuple[str, ...]: The words, head word last.
    """
    words = list(tokenise(" ".join(parsed.preparation)))
    carried = _CONTAINER_IDENTITY.get(parsed.container or parsed.unit)
    if carried is not None:
        words.append(carried)
    words.extend(word for word in tokenise(parsed.name) if word not in words)
    return tuple(words)


def _rank(record: FoodRecord, words: tuple[str, ...]) -> tuple[float, ...]:
    """Order candidates. Nothing here decides what a number is worth.

    Args:
        record: The candidate.
        words: The query's words.

    Returns:
        tuple[float, ...]: A sort key, larger being preferred.
    """
    lowered = record.description.lower()
    tokens = record.tokens
    missing = sum(1 for word in words if word not in tokens)
    unrequested = _unrequested(tokens, words)
    head = words[-1]
    position = tokens.index(head) if head in tokens else len(tokens)
    found = [tokens.index(word) for word in words if word in tokens]
    depth = sum(found) / len(found) if found else len(tokens)
    return (
        0 if any(phrase in lowered for phrase in _AS_EATEN) else 1,
        # USDA descriptions run general to specific and name the food first —
        # `Onions, raw`, `Lemon juice, raw` — so a description that opens with
        # the line's head word is describing that food, and one that mentions it
        # six words in is a dish that contains it. Two words of grace, because
        # plenty of foods are two words. This outranks word coverage because a
        # record carrying every word of the line is routinely a dish rather than
        # an ingredient: `plain flour` matches a pretzel long before flour.
        1 if position <= 1 else 0,
        -missing,
        -len(unrequested),
        -position,
        # Among records that cover the line equally, the one whose matched words
        # sit closest to the front is describing the food rather than qualifying
        # it: `Oil, olive, salad or cooking` over `Oil, corn, peanut, and olive`.
        -depth,
        # The research doc's instruction, and a large source of wrong numbers
        # when ignored: prefer the raw record unless the line asked for cooked.
        1 if "raw" in tokens and not _asks_cooked(words) else 0,
        # USDA's own "not further specified" record is precisely the record that
        # adds nothing, which is what an unqualified line asked for.
        1 if "nfs" in tokens or "ns" in tokens else 0,
        -len(tokens),
        _DATA_TYPE_PREFERENCE.get(record.data_type, 0),
        -record.fdc_id,
    )


def _asks_cooked(words: tuple[str, ...]) -> bool:
    """Return whether the line itself asked for something cooked.

    Args:
        words: The query's words.

    Returns:
        bool: True when any of them describes cooking.
    """
    return any(word in _COOKED_WORDS for word in words)


def _unrequested(tokens: tuple[str, ...], words: tuple[str, ...]) -> tuple[str, ...]:
    """Return the significant words a record adds that the line did not ask for.

    Args:
        tokens: The record's words.
        words: The query's words.

    Returns:
        tuple[str, ...]: The added words, in the record's order.
    """
    return tuple(
        token
        for token in tokens
        if token in SIGNIFICANT_QUALIFIERS
        and token not in words
        and token not in NEUTRAL_WORDS
    )


def match(parsed: ParsedIngredient, index: UsdaIndex) -> Match | None:
    """Choose a record for a parsed line, and record what it cost.

    Args:
        parsed: The parsed line.
        index: The index to search.

    Returns:
        Match | None: The chosen record with its structural cost, or ``None``
            when nothing in the index carries the line's head word. That is a
            refusal: widening the search until something comes back is how a
            matcher reaches 94% coverage and 72% correctness.
    """
    words = query_words(parsed)
    candidates = index.candidates(words)
    if not candidates:
        return None
    record = max(candidates, key=lambda candidate: _rank(candidate, words))
    dropped = tuple(word for word in words if word not in record.tokens)
    if len(dropped) * 2 > len(words):
        # More of the line went unaccounted for than was matched. `1 lb meat of
        # your choice` finds a ribeye, because USDA grades beef "choice" — and a
        # record answering a minority of the words she wrote is not her food,
        # however cleanly the rest of the pipeline would run on it.
        return None
    return Match(
        record=record,
        dropped=dropped,
        unrequested=_unrequested(record.tokens, words),
    )
