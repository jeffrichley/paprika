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


def cold_sync(
    client: PaprikaClient,
    mirror: Mirror,
    progress: Progress | None = None,
) -> int:
    """Download the whole Library into the Mirror.

    Args:
        client: A signed-in client.
        mirror: The Mirror to fill.
        progress: Called with ``(done, total)`` as each recipe lands.

    Returns:
        int: How many recipes the Mirror now holds.

    Raises:
        PaprikaError: On anything the wire says. Whatever landed before the
            failure stays landed.
    """
    counters = client.get(STATUS_PATH, "checking what Paprika has")
    stubs = _as_list(client.get(RECIPE_INDEX_PATH, "listing your recipes"))
    categories = _as_list(client.get(CATEGORIES_PATH, "reading your categories"))

    mirror.begin_library()
    mirror.put_categories(categories)

    total = len(stubs)
    done = 0
    for stub in stubs:
        uid = str(stub.get("uid", ""))
        if not uid:
            continue
        recipe = client.get(RECIPE_PATH.format(uid=uid), "downloading a recipe")
        if isinstance(recipe, dict):
            mirror.put_recipe(recipe)
        done += 1
        if progress is not None:
            progress(done, total)

    mirror.assign_handles()
    mirror.mark_synced(counters if isinstance(counters, dict) else {})
    log_event("cold_sync", recipes=mirror.count_recipes(), categories=len(categories))
    return mirror.count_recipes()
