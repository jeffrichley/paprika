"""One name for an allergy, whatever she called it.

This module **tidies; it does not judge**. Every allergy is recorded, including
ones that appear nowhere below.

It used to refuse anything it could not name, on the stated grounds that an
allergy has to be *matchable rather than merely recorded*. That described a
filter which does not exist: nothing in this package ever reads allergies to
reject a recipe. The one caller is the Profile write, and the screening is done
by a skill reading the primer's allergy line and applying cooking judgement —
which handles "tomatoes" as readily as "peanuts", and better than any table
here, because it knows that ketchup and passata are tomatoes and this file
never will.

The gate also failed in the direction that mattered. A household whose only
allergy was unlistable could not reach an answered state, so it was asked every
week, and the way to stop being asked was to declare *no allergies* — a
falsehood that reads as a checked fact. Being unable to record the truth was
steering her into recording a lie. See #93.

What the table is still for: making sure "dairy" and "milk" do not sit in the
list as two separate constraints. That is worth having and is not a reason to
throw anything away.
"""

from __future__ import annotations

#: Canonical name to the spellings people use for it.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "celery": ("celery", "celeriac"),
    "eggs": ("egg", "eggs"),
    "fish": ("fish", "finned fish", "anchovy", "anchovies"),
    "gluten": ("gluten", "wheat", "barley", "rye", "spelt"),
    "lupin": ("lupin", "lupine"),
    "milk": ("milk", "dairy", "lactose", "cheese"),
    "molluscs": ("mollusc", "molluscs", "mollusk", "mollusks", "squid", "octopus"),
    "mustard": ("mustard",),
    "peanuts": ("peanut", "peanuts", "groundnut", "groundnuts"),
    "sesame": ("sesame", "tahini"),
    "shellfish": (
        "shellfish",
        "crustacean",
        "crustaceans",
        "prawn",
        "prawns",
        "shrimp",
        "crab",
        "lobster",
    ),
    "soy": ("soy", "soya", "soybean", "soybeans", "edamame"),
    "sulphites": ("sulphite", "sulphites", "sulfite", "sulfites"),
    "tree nuts": (
        "tree nut",
        "tree nuts",
        "nuts",
        "almond",
        "almonds",
        "cashew",
        "cashews",
        "hazelnut",
        "hazelnuts",
        "pecan",
        "pecans",
        "pistachio",
        "pistachios",
        "walnut",
        "walnuts",
    ),
}

_LOOKUP: dict[str, str] = {
    spelling: canonical
    for canonical, spellings in _SYNONYMS.items()
    for spelling in spellings
}

#: The ones we have alternative spellings for. Not a permitted list — anything
#: she says is recorded — just the ones we can fold onto a single name.
KNOWN: tuple[str, ...] = tuple(sorted(_SYNONYMS))


def normalise(word: str) -> str | None:
    """Turn what she typed into the one name this household uses for it.

    Args:
        word: An allergy as she wrote it.

    Returns:
        str | None: A canonical name when this is one we have a spelling for,
            and otherwise **her own word**, tidied of case and spacing and
            nothing else. ``None`` only when she typed nothing at all.
    """
    cleaned = " ".join(word.strip().casefold().split())
    if not cleaned:
        return None
    if cleaned in _LOOKUP:
        return _LOOKUP[cleaned]
    # "peanut allergy", "allergic to peanuts" — the noun is what matters.
    for spelling, canonical in _LOOKUP.items():
        if spelling in cleaned.split():
            return canonical
    # Not one we know. Keep it exactly as she said it: a word this file cannot
    # name is still a word the session can act on, and guessing at what she
    # meant is how "nightshades" quietly becomes "tomatoes".
    return cleaned
