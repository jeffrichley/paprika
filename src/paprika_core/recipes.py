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
    # Whether there is a picture, so a skill can tell. Reported because this is
    # now a field the plugin can *write*: shipping a way to set a photo without
    # a way to see one leaves the one field a whole-object replace would lose
    # most visibly as the only field nothing can check.
    "photo",
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


#: What is worth comparing when she is choosing which copy to keep. Ordered so
#: the things that decide it come first.
COMPARED = (
    "ingredients",
    "directions",
    "servings",
    "total_time",
    "prep_time",
    "cook_time",
    "notes",
    "nutritional_info",
    "source",
    "source_url",
    "rating",
)


def differences(mirror: Mirror, handles: list[str]) -> dict[str, Any]:
    """Show what differs between recipes that look like copies of each other.

    Here a name is **not** sufficient to judge by — that is what separates this
    from re-filing. She is deciding which copy survives, and she can only do
    that if she can see what each one has that the others do not.

    Nothing here proposes a merge, and nothing computes a similarity score. Two
    recipes with the same title and different ingredients are a real question,
    not an obvious duplicate.

    Args:
        mirror: The Mirror to read.
        handles: The recipes in the cluster.

    Returns:
        dict[str, Any]: The recipes by handle, which fields differ, and which
            are identical — because identical ingredients and method is
            structural evidence that asserts, where a similar title only asks.
    """
    bodies = {handle: mirror.recipe_body(handle) for handle in handles}
    present = {h: b for h, b in bodies.items() if b is not None}

    differing: list[str] = []
    same: list[str] = []
    for field_name in COMPARED:
        values = {str(body.get(field_name) or "") for body in present.values()}
        (differing if len(values) > 1 else same).append(field_name)

    return {
        "recipes": [
            {
                "handle": handle,
                "name": str(body.get("name") or ""),
                # Only the fields that actually differ, so a screen shows the
                # decision rather than two whole recipes side by side.
                "differs": {
                    field_name: str(body.get(field_name) or "")
                    for field_name in differing
                },
            }
            for handle, body in present.items()
        ],
        "same": same,
        # Identical ingredients and method is a fact that can be stated. A
        # similar title is a question that has to be asked.
        "identical": not differing,
        "missing": [handle for handle in handles if bodies.get(handle) is None],
    }
