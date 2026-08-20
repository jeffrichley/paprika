"""Her filing scheme — extended, never rearranged.

Two rules do all the work here.

**A new category must name its parent.** Her tree is three levels deep and she
built it; a new top-level category flattens it, and a flat scheme is what she
was trying to get away from. There is no way to create one without saying where
it goes, because a default would be taken.

**Re-filing only ever adds.** A Run never removes a category she chose. Filing
something at a root may look careless and may well have been deliberate, and the
cost of being wrong in that direction is undoing work she did on purpose.

There is deliberately no way to delete a category. Her scheme wins, and a command
that can dismantle a hundred-node tree has no caller worth the risk.
"""

from __future__ import annotations

import uuid
from typing import Any

from paprika_core.errors import Code, PaprikaError
from paprika_core.http import CATEGORIES_PATH, PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.undo import Run

#: The kind this writes, for the envelope's `changed` map.
KIND = "categories"


def create(
    client: PaprikaClient,
    *,
    name: str,
    parent: str,
    mirror: Mirror,
    run: Run,
) -> str:
    """Add one category under an existing one.

    Args:
        client: A signed-in client.
        name: What she would call it.
        parent: The category it belongs under, by name. Required — a new
            top-level category flattens the tree she built.
        mirror: The Mirror, for resolving the parent by name.
        run: The Run to capture the Pre-image into.

    Returns:
        str: The new category's identity, for filing things into it.

    Raises:
        PaprikaError: When the name is blank, the parent is unknown, or one by
            that name already exists.
    """
    wanted = name.strip()
    if not wanted:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            "A category needs a name.",
            detail="blank category name",
        )

    by_name = {value.casefold(): uid for uid, value in mirror.category_names().items()}
    if wanted.casefold() in by_name:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            f"There's already a {wanted!r} to file things under.",
            detail=f"duplicate category {wanted!r}",
        )
    parent_uid = by_name.get(parent.strip().casefold())
    if parent_uid is None:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            f"There's nothing called {parent!r} to put it under.",
            detail=f"unknown parent {parent!r}",
        )

    entry: dict[str, Any] = {
        "uid": str(uuid.uuid4()).upper(),
        "name": wanted,
        "order_flag": 0,
        "parent_uid": parent_uid,
    }
    # What was there before is nothing, which on this API is a removal.
    run.capture(KIND, str(entry["uid"]), wanted, dict(entry, deleted=True))
    client._post_object(CATEGORIES_PATH, [entry], "adding a category")
    run.mark_landed(KIND, str(entry["uid"]))
    log_event("category_create", parent=parent)
    return str(entry["uid"])


def restore(client: PaprikaClient, body: dict[str, Any]) -> None:
    """Put a category back exactly as it was.

    Args:
        client: A signed-in client.
        body: The Pre-image.
    """
    client._post_object(CATEGORIES_PATH, [dict(body)], "putting a category back")
