"""Reading an ingredient line, and noticing what we failed to read.

Parsing is the one stage of this pipeline that is genuinely solved: the CRF in
``ingredient-parser-nlp`` scores 95.6% at sentence level over 81,346 labelled
sentences. It is used here for exactly that and nothing else. The same package
will also match a parsed name to a FoodData Central record, and that part is
deliberately unused — its own docs publish no accuracy figure for it, and it
returns confidence 1.0 while turning `butter` into `Butter, stick, unsalted`.

The import is heavy — numpy and nltk, about half a second — so it happens inside
the function rather than at module scope. A test pins that importing
:mod:`paprika_core` does not pay for it.

It also reaches for the network unless it is stopped. NLTK ships no part-of-speech
tagger with the library: ``ingredient-parser-nlp`` looks for
``averaged_perceptron_tagger_eng`` and, not finding it, calls
``nltk.download`` — which on her machine means a silent 1.5 MB fetch the first
time she asks about nutrition, and an outright failure if she is offline or
behind a firewall. That is exactly the outcome bundling the USDA data exists to
avoid, so the tagger is bundled the same way and NLTK is pointed at our copy
before the parser is ever imported. If the bundled copy is missing, this module
says so in a sentence rather than quietly going to the internet.

What this module adds to the parse is the accounting: anything the parser set
aside as a comment is carried out as an unaccounted word rather than dropped,
because a silently discarded `plus more for greasing` is how a line quietly
becomes worth less than it looks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, final

from paprika_core.errors import Code, PaprikaError
from paprika_core.nutrition.units import Dimension, canonical_unit, dimension

#: The one NLTK resource the parser needs. NLTK reads the three JSON files it
#: wants straight out of the bundled zip, so it is shipped zipped: 1.5 MB
#: against 5.4 MB unpacked.
TAGGER = "averaged_perceptron_tagger_eng"

#: Phrases that mean the author declined to say how much, which is a fact about
#: the recipe rather than a failure of ours.
_OPEN_ENDED = (
    "to taste",
    "as needed",
    "as desired",
    "if desired",
    "for serving",
    "for garnish",
    "to serve",
    "to garnish",
)

#: Preparation words that change what the food *is*, so they belong in the
#: search. Everything else a parser calls preparation — diced, chopped, minced —
#: changes only the knife work, and dropping it costs nothing.
IDENTITY_PREPARATIONS = frozenset(
    {
        "raw",
        "cooked",
        "roasted",
        "toasted",
        "dried",
        "canned",
        "frozen",
        "smoked",
        "cured",
        "pickled",
        "boiled",
        "fried",
        "baked",
        "steamed",
        "ground",
        "grilled",
        "blanched",
    }
)


@final
@dataclass(frozen=True, slots=True)
class ParsedIngredient:
    """One ingredient line, read.

    Attributes:
        line: The line, verbatim.
        quantity: How many of :attr:`unit`, or ``None`` when the author did not
            say. A range becomes its midpoint, and :attr:`is_range` records that.
        unit: The canonical unit or count word, empty when the line gave none.
        container: The thing the unit was per — `1 (14.5 oz) can` is 14.5
            ounces per can — which is sometimes also a statement about the food.
        size: A size word — `large`, `medium` — which has no fixed gram value.
        name: The food.
        preparation: Preparation words that change what the food is.
        prep_words: Every preparation word, including the ones that change only
            the knife work — which is exactly what USDA's own portion qualifiers
            record, `1 cup, chopped` being 160 g and `1 cup, sliced` 115 g.
        is_range: The author gave a range rather than a quantity.
        open_ended: The author declined to quantify it at all.
        alternatives: Other foods the line offered — `1 cup milk or cream`.
        unaccounted: Anything in the line we could not place.
    """

    line: str
    quantity: float | None
    unit: str
    size: str
    name: str
    container: str = ""
    preparation: tuple[str, ...] = ()
    prep_words: tuple[str, ...] = ()
    is_range: bool = False
    open_ended: bool = False
    alternatives: tuple[str, ...] = ()
    unaccounted: tuple[str, ...] = ()


def _text(value: Any) -> str:
    """Read the text off one of the parser's tagged spans.

    Args:
        value: The span, or ``None``.

    Returns:
        str: Its text, or an empty string.
    """
    return "" if value is None else str(value.text).strip()


def _quantity(amounts: list[Any]) -> tuple[float | None, str, str, bool]:
    """Choose the amount that actually says how much food there is.

    ``1 (14.5 oz) can diced tomatoes`` parses to two amounts: one can, and 14.5
    ounces marked as being *per* can. The mass is the useful one, and it has to
    be multiplied by the count rather than read on its own.

    Args:
        amounts: The parser's amounts.

    Returns:
        tuple[float | None, str, str, bool]: The quantity, its canonical unit,
            the container word the quantity was per — which is often also a
            statement about the food, `can` meaning canned — and whether the
            author gave a range.
    """
    if not amounts:
        return None, "", "", False

    measured = [
        amount
        for amount in amounts
        if dimension(canonical_unit(str(amount.unit))) is not Dimension.COUNT
    ]
    chosen = measured[0] if measured else amounts[0]
    quantity = _midpoint(chosen)
    is_range = bool(chosen.RANGE) or chosen.quantity != chosen.quantity_max
    container = ""

    if measured and chosen.SINGULAR:
        counts = [amount for amount in amounts if amount is not chosen]
        if counts:
            quantity *= _midpoint(counts[0])
            is_range = is_range or bool(counts[0].RANGE)
            container = canonical_unit(str(counts[0].unit))
    return quantity, canonical_unit(str(chosen.unit)), container, is_range


def _midpoint(amount: Any) -> float:
    """Return an amount's midpoint, which is also its value when it is not a range.

    Args:
        amount: The parser's amount.

    Returns:
        float: The midpoint.
    """
    return (float(amount.quantity) + float(amount.quantity_max)) / 2.0


def nltk_data_dir() -> Path:
    """Return the directory holding the bundled NLTK resources.

    Returns:
        Path: The package's ``data/nltk`` directory, laid out the way NLTK
            expects — ``taggers/<resource>.zip``.
    """
    return Path(__file__).parent / "data" / "nltk"


def _use_bundled_tagger() -> None:
    """Point NLTK at our copy of the tagger, ahead of anything on the machine.

    Prepending rather than appending is the point: a stale or half-downloaded
    ``~/nltk_data`` must not win, and neither must the downloader.

    Raises:
        PaprikaError: ``nutrition_data_missing`` when the bundled tagger is not
            there. Failing loudly is the whole reason this function exists — the
            alternative, which is what the parser does on its own, is a silent
            download.
    """
    bundled = nltk_data_dir() / "taggers" / f"{TAGGER}.zip"
    if not bundled.is_file():
        raise PaprikaError(
            Code.NUTRITION_DATA_MISSING,
            "Part of the language data that ships with this plugin is missing, "
            "so I can't read ingredient lines.",
            detail=f"no bundled NLTK tagger at {bundled}",
        )

    import nltk.data

    directory = str(nltk_data_dir())
    if directory not in nltk.data.path:
        nltk.data.path.insert(0, directory)


def parse_line(line: str) -> ParsedIngredient:
    """Parse one ingredient line.

    Args:
        line: The line as she wrote it.

    Returns:
        ParsedIngredient: What we read, and what we could not.
    """
    if not line.strip():
        return ParsedIngredient(line=line, quantity=None, unit="", size="", name="")

    # Deferred deliberately: this pulls numpy and nltk, and no session that never
    # asks about nutrition should pay for it. The tagger has to be in place
    # before the import, because the parser checks for it as it loads.
    _use_bundled_tagger()

    from ingredient_parser import parse_ingredient

    parsed = parse_ingredient(line)
    names = [_text(name) for name in parsed.name]
    comment = _text(parsed.comment)
    lowered = comment.lower()
    open_ended = any(phrase in lowered for phrase in _OPEN_ENDED)
    quantity, unit, container, is_range = _quantity(list(parsed.amount))

    prep_words = tuple(_text(parsed.preparation).replace(",", " ").lower().split())
    preparation = tuple(word for word in prep_words if word in IDENTITY_PREPARATIONS)
    unaccounted: list[str] = []
    if comment and not open_ended:
        unaccounted.append(comment)

    return ParsedIngredient(
        line=line,
        quantity=quantity,
        unit=unit,
        container=container,
        size=_text(parsed.size).lower(),
        name=names[0] if names else "",
        preparation=preparation,
        prep_words=prep_words,
        is_range=is_range,
        open_ended=open_ended or quantity is None,
        alternatives=tuple(names[1:]),
        unaccounted=tuple(unaccounted),
    )
