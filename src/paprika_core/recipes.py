"""Reading the Library back — one line per recipe, the whole thing at once.

Five hundred entries at roughly sixteen tokens each is about eight thousand
tokens, which the model can simply read. That arithmetic is why there is no
local semantic search here and no similarity score anywhere: the model is the
semantic engine, and it shortlists from this index before pulling any bodies.

Ingredients are deliberately absent. A question that needs them is a question
that pulls a handful of recipes, not one that widens this line.
"""

from __future__ import annotations

from paprika_core.mirror import Mirror

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
    lines: list[str] = []
    for recipe in mirror.recipes():
        categories = ", ".join(names[uid] for uid in recipe.categories if uid in names)
        rating = str(recipe.rating) if recipe.rating else ""
        lines.append(
            SEPARATOR.join(
                [
                    recipe.handle,
                    recipe.name,
                    categories,
                    rating,
                    recipe.total_time,
                ]
            )
        )
    return lines
