"""Reading the Library back — one line per recipe, the whole thing at once.

Five hundred entries at roughly sixteen tokens each is about eight thousand
tokens, which the model can simply read. That arithmetic is why there is no
local semantic search here and no similarity score anywhere: the model is the
semantic engine, and it shortlists from this index before pulling any bodies.

Ingredients are deliberately absent. A question that needs them is a question
that pulls a handful of recipes, not one that widens this line.
"""

from __future__ import annotations

from typing import Any

from paprika_core.mirror import Mirror, MirroredRecipe

SEPARATOR = " | "


def index_lines(mirror: Mirror) -> list[str]:
    """Render the whole Library as one line per recipe.

    The shape is ``handle | name | categories | rating | total time``. A rating of
    zero and an unrecorded time render empty rather than as a guess, so a blank
    column means Paprika holds nothing there.

    Args:
        mirror: The Mirror to read.

    Returns:
        list[str]: One entry per recipe, ordered by name.
    """
    names = mirror.category_names()
    return [_line(recipe, names) for recipe in mirror.recipes()]


def _line(recipe: MirroredRecipe, names: dict[str, str]) -> str:
    """Render one index entry.

    Shared by the index and by search so the two can never drift into showing
    her the same recipe two different ways.

    Args:
        recipe: The recipe.
        names: Category uid to category name.

    Returns:
        str: ``handle | name | categories | rating | total time``.
    """
    return SEPARATOR.join(
        [
            recipe.handle,
            recipe.name,
            ", ".join(names[uid] for uid in recipe.categories if uid in names),
            str(recipe.rating) if recipe.rating else "",
            recipe.total_time,
        ]
    )


#: What a recipe looks like once Paprika's record-keeping is taken off it. The
#: list is a whitelist rather than a set of exclusions, so a field added to the
#: wire later cannot arrive in the session by default.
SHOWN = (
    "name",
    "ingredients",
    "directions",
    "description",
    "notes",
    "nutritional_info",
    "servings",
    "difficulty",
    "prep_time",
    "cook_time",
    "total_time",
    "rating",
    "source",
    "source_url",
)


def rendered(mirror: Mirror, handle: str) -> dict[str, Any] | None:
    """Return one whole recipe, with none of Paprika's record-keeping on it.

    Args:
        mirror: The Mirror to read.
        handle: How the session names the recipe.

    Returns:
        dict[str, Any] | None: The recipe, or ``None`` when the handle is
            unknown. Categories are named rather than identified, and the handle
            rides along so a later change can aim at it.
    """
    body = mirror.recipe_body(handle)
    if body is None:
        return None
    names = mirror.category_names()
    shown: dict[str, Any] = {"handle": handle}
    for field in SHOWN:
        shown[field] = body.get(field)
    shown["categories"] = [
        names[uid] for uid in (body.get("categories") or []) if uid in names
    ]
    return shown


def search(mirror: Mirror, term: str) -> list[str]:
    """Return index entries for recipes whose text contains a term.

    Lexical, and deliberately only that. It exists for the one question the
    index cannot answer — an ingredient across the whole Library without
    fetching any of it — and for the duplicate check. Nothing here scores a near
    miss as a hit, because a similarity score is a second judge competing with
    the model, returning a confident number with no Provenance behind it.

    Args:
        mirror: The Mirror to read.
        term: What to look for.

    Returns:
        list[str]: Index entries for the matches, in the index's own order.
    """
    wanted = term.strip().casefold()
    if not wanted:
        return []
    names = mirror.category_names()
    found: list[str] = []
    for recipe in mirror.recipes():
        body = mirror.recipe_body(recipe.handle) or {}
        haystack = " ".join(
            str(body.get(field) or "")
            for field in ("name", "ingredients", "directions", "notes", "source")
        ).casefold()
        if wanted in haystack:
            found.append(_line(recipe, names))
    return found
