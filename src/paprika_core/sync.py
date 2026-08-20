"""The cold sync — one request, then one per recipe, and no way around it.

There is no bulk recipe download. Five hundred recipes is five hundred and one
sequential round trips, which is the dominant cost in the whole API and the
reason the Mirror is a requirement rather than an optimisation.

Every recipe is committed as it lands, so an interrupted sync keeps exactly what
it had. Nothing here is on a timer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from paprika_core.http import (
    CATEGORIES_PATH,
    RECIPE_INDEX_PATH,
    STATUS_PATH,
    PaprikaClient,
)
from paprika_core.log import log_event
from paprika_core.mirror import Mirror

RECIPE_PATH = "/api/v2/sync/recipe/{uid}/"
MEALS_PATH = "/api/v2/sync/meals/"

#: Called with (done, total) after each recipe lands, so a long wait can say so.
Progress = Callable[[int, int], None]


def _as_list(value: Any) -> list[dict[str, Any]]:
    """Coerce a collection response into a list of objects.

    Args:
        value: Whatever the endpoint returned.

    Returns:
        list[dict[str, Any]]: The objects in it, ignoring anything that is not one.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def refresh_recipes(client: PaprikaClient, mirror: Mirror) -> int:
    """Refetch only the recipes that actually differ, and drop the ones that went.

    One request for the index of ``{uid, token}`` stubs, then one request per
    recipe whose token moved. A uid the Mirror holds but the index no longer
    lists has been removed in Paprika — absence is the only evidence there is,
    since deletion leaves no tombstone.

    Args:
        client: A signed-in client.
        mirror: The Mirror to bring up to date.

    Returns:
        int: How many recipes were refetched or dropped.

    Raises:
        PaprikaError: On anything the wire says.
    """
    stubs = _as_list(client.get(RECIPE_INDEX_PATH, "listing your recipes"))
    live = {
        str(stub.get("uid", "")): str(stub.get("hash") or "")
        for stub in stubs
        if stub.get("uid")
    }
    held = mirror.recipe_tokens()

    stale = [uid for uid, token in live.items() if held.get(uid) != token]
    vanished = [uid for uid in held if uid not in live]

    for uid in stale:
        recipe = client.get(RECIPE_PATH.format(uid=uid), "downloading a recipe")
        if isinstance(recipe, dict):
            mirror.put_recipe(recipe)

    dropped = mirror.forget_recipes(vanished)
    if stale or vanished:
        mirror.assign_handles()
    log_event("refresh_recipes", refetched=len(stale), dropped=dropped)
    return len(stale) + dropped


def refresh_categories(client: PaprikaClient, mirror: Mirror) -> int:
    """Refetch her whole category tree.

    The tree arrives in one request and is small, so there is nothing to diff.

    Args:
        client: A signed-in client.
        mirror: The Mirror to bring up to date.

    Returns:
        int: How many categories the tree now holds.

    Raises:
        PaprikaError: On anything the wire says.
    """
    categories = _as_list(client.get(CATEGORIES_PATH, "reading your categories"))
    mirror.put_categories(categories)
    log_event("refresh_categories", categories=len(categories))
    return len(categories)


def refresh_meals(client: PaprikaClient, mirror: Mirror) -> int:
    """Refetch the whole Plan.

    It arrives in one request and is small, so there is nothing to diff.

    Args:
        client: A signed-in client.
        mirror: The Mirror to bring up to date.

    Returns:
        int: How many meals the Plan now holds.

    Raises:
        PaprikaError: On anything the wire says.
    """
    meals = _as_list(client.get(MEALS_PATH, "reading your plan"))
    mirror.put_meals(meals)
    log_event("refresh_meals", meals=len(meals))
    return len(meals)


def cold_sync(
    client: PaprikaClient,
    mirror: Mirror,
    progress: Progress | None = None,
) -> int:
    """Download the whole Library into the Mirror, resuming if it was interrupted.

    Deliberately **not** a wipe-and-refetch. Each recipe commits as it lands, and
    this skips any whose change token the Mirror already holds — so a sync that
    was killed at recipe four hundred costs the remaining hundred rather than the
    whole five. A cold sync is then just this same diff run against an empty
    Mirror, which is one code path instead of two.

    Args:
        client: A signed-in client.
        mirror: The Mirror to fill.
        progress: Called with ``(done, total)`` as each recipe lands, where
            ``total`` counts only what is actually left to fetch.

    Returns:
        int: How many recipes are in her Library afterwards.

    Raises:
        PaprikaError: On anything the wire says. Whatever landed before the
            failure stays landed, and a re-run picks up from there.
    """
    counters = client.get(STATUS_PATH, "checking what Paprika has")
    stubs = _as_list(client.get(RECIPE_INDEX_PATH, "listing your recipes"))
    categories = _as_list(client.get(CATEGORIES_PATH, "reading your categories"))

    mirror.put_categories(categories)
    refresh_meals(client, mirror)

    live = {
        str(stub.get("uid", "")): str(stub.get("hash") or "")
        for stub in stubs
        if stub.get("uid")
    }
    held = mirror.recipe_tokens()
    outstanding = [uid for uid, token in live.items() if held.get(uid) != token]

    total = len(outstanding)
    for done, uid in enumerate(outstanding, start=1):
        recipe = client.get(RECIPE_PATH.format(uid=uid), "downloading a recipe")
        if isinstance(recipe, dict):
            mirror.put_recipe(recipe)
        if progress is not None:
            progress(done, total)

    mirror.forget_recipes([uid for uid in held if uid not in live])
    mirror.assign_handles()
    mirror.mark_synced(counters if isinstance(counters, dict) else {})
    mirror.mark_checked()
    log_event("cold_sync", downloaded=total, categories=len(categories))
    return mirror.count_recipes()
