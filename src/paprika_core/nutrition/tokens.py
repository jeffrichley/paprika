"""Reducing a food description or an ingredient name to comparable words.

Both sides of every comparison come through here — USDA's description and her
ingredient line — so consistency matters more than any single normalisation
being the *right* one.
"""

from __future__ import annotations

import re

from paprika_core.nutrition.units import singular

_WORD = re.compile(r"[a-z0-9%]+")

#: Words that carry no identity in a food description or an ingredient line.
STOPWORDS = frozenset(
    {"a", "an", "and", "as", "for", "in", "of", "or", "the", "to", "with", "without"}
)


def tokenise(text: str) -> tuple[str, ...]:
    """Reduce a description or an ingredient name to comparable words.

    Args:
        text: The text.

    Returns:
        tuple[str, ...]: Its words, lowercased, singularised, stopwords removed,
            duplicates removed, in order.
    """
    seen: list[str] = []
    for raw in _WORD.findall(text.lower()):
        word = singular(raw)
        if word in STOPWORDS or word in seen:
            continue
        seen.append(word)
    return tuple(seen)
