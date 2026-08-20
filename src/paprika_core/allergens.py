"""What counts as an allergy we can actually check for.

An allergy is the one thing in the Profile that a filter has to be able to *act*
on, which means it has to be matchable rather than merely recorded. So it is
normalised to a known name here, and anything we cannot match is **refused out
loud** rather than stored.

Refusing is the safer failure. A word we do not understand, written down beside
the ones we do, looks exactly like a fact that is being checked — and the first
anyone would learn otherwise is a plan that proposed it.

The list is the common allergens with the synonyms people actually type. It is
not medical advice and does not pretend to be exhaustive; it is the set this
plugin can honestly claim to screen for.
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

#: Every allergy this plugin can honestly claim to screen for.
KNOWN: tuple[str, ...] = tuple(sorted(_SYNONYMS))


def normalise(word: str) -> str | None:
    """Turn what she typed into the name the filter matches on.

    Args:
        word: An allergy as she wrote it.

    Returns:
        str | None: The canonical name, or ``None`` when this is not something
            we can check for — which the caller must surface rather than store.
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
    return None
