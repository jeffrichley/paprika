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

#: Canonical name to the words that mean it — both the ones she might type when
#: recording an allergy and the ones a recipe uses when listing an ingredient.
#: Those are different vocabularies and this table serves both: nobody records
#: an allergy to "double cream", and no recipe says "dairy".
#:
#: **Err toward inclusion.** This is a detector, so a false positive costs
#: somebody ten seconds reading a line, and a false negative costs what a false
#: negative in this domain costs. `flour` under gluten will occasionally flag a
#: rice-flour recipe, and that is the direction to be wrong in.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "celery": ("celery", "celeriac"),
    "eggs": ("egg", "eggs", "mayonnaise", "meringue"),
    "fish": ("fish", "finned fish", "anchovy", "anchovies"),
    "gluten": (
        "gluten",
        "wheat",
        "barley",
        "rye",
        "spelt",
        "flour",
        "breadcrumb",
        "breadcrumbs",
        "pasta",
        "couscous",
        "semolina",
    ),
    "lupin": ("lupin", "lupine"),
    "milk": (
        "milk",
        "dairy",
        "lactose",
        "cheese",
        "butter",
        "cream",
        "yoghurt",
        "yogurt",
        "ghee",
        "custard",
    ),
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


def spellings_for(name: str) -> tuple[tuple[str, ...], bool]:
    """Return the words to look for, and whether we know any beyond her own.

    Args:
        name: An allergy, canonical or in her words.

    Returns:
        tuple[tuple[str, ...], bool]: The terms to search, and ``True`` when the
            only term is the word she typed. That flag is the honest half: for
            ``milk`` we look for cream, butter and cheese, and for ``tomatoes``
            we look for *tomatoes* and will not find ketchup. A caller that does
            not say which happened is publishing a clean result that means two
            different things.
    """
    known = _SYNONYMS.get(name.strip().casefold())
    if known:
        return known, False
    return (name.strip().casefold(),), True


#: Words that make a match mean the opposite of what it looks like. "Peanut
#: butter" is not butter; "coconut milk" is not milk. Found live: 21 recipes in
#: one library matched `milk` through peanut butter alone.
#:
#: The cost of a false positive is not the false positive. It is that a check
#: which cries wolf teaches whoever reads it to skim, and a skimmed backstop is
#: not a backstop. So this list exists, and it is deliberately short — every
#: entry here is a hole, and a long one would be a sieve.
BORROWED: dict[str, tuple[str, ...]] = {
    "butter": ("peanut", "apple", "cocoa", "shea", "almond", "cashew", "nut"),
    "milk": ("coconut", "almond", "soy", "soya", "oat", "rice"),
    "cream": ("coconut", "cream of tartar"),
}


def is_borrowed(term: str, line: str) -> bool:
    """Say whether this line's match is another food wearing the word.

    Args:
        term: The word that matched.
        line: The ingredient line it matched in.

    Returns:
        bool: True when every occurrence of the term in this line is borrowed —
            one genuine mention is enough to keep the hit, because a recipe with
            peanut butter *and* butter is a recipe with butter in it.
    """
    qualifiers = BORROWED.get(term)
    if not qualifiers:
        return False
    lowered = line.casefold()
    start = 0
    while (found := lowered.find(term, start)) != -1:
        before = lowered[:found]
        if not any(before.rstrip().endswith(q) for q in qualifiers):
            return False
        start = found + len(term)
    return True
