"""The Plan — meals on dates, written to the one resource that can hold them.

``/sync/meals/`` and never ``menus``/``menuitems``. A menu item has no date at
all, only an integer day offset, and its ``recipe_uid`` cannot be null — so
falling back to it would lose every date and silently drop every meal she typed
as free text rather than picked from her Library.

Two things about this endpoint shape the code:

**There is no per-uid route.** The whole array is posted and each entry upserts
by uid, so a write here is a read-modify-write over a *collection* rather than
over one object. The rule is the same as everywhere else, though: this module
takes named values and never an object a caller assembled.

**The real risk is not overwriting, it is silent duplication.** If she puts
something in Tuesday's dinner on her phone while we put something else there,
the two carry different client-minted identifiers, nothing reconciles them, and
Tuesday quietly shows two dinners. So a write fetches the Plan immediately
first and reconciles on the slot — the date and the meal type — rather than
trusting what the Mirror last saw.
"""

from __future__ import annotations

import uuid
from typing import Any

from paprika_core.errors import Code, PaprikaError
from paprika_core.http import PaprikaClient
from paprika_core.log import log_event
from paprika_core.sync import MEALS_PATH
from paprika_core.undo import Run

#: What she calls each slot, and what Paprika numbers it.
SLOTS: dict[str, int] = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}

#: The kind this writes, for the envelope's `changed` map.
KIND = "plan"

#: Paprika stores a space-separated stamp rather than ISO 8601, and is strict.
DAY_START = " 00:00:00"


def slot_number(slot: str) -> int:
    """Turn a slot she named into the number Paprika stores.

    Args:
        slot: ``breakfast``, ``lunch``, ``dinner`` or ``snack``.

    Returns:
        int: The slot number.

    Raises:
        PaprikaError: When it is not one of the four.
    """
    found = SLOTS.get(slot.strip().casefold())
    if found is None:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            "A meal goes in breakfast, lunch, dinner or supper.",
            detail=f"unknown slot {slot!r}",
        )
    return found


def _fetch(client: PaprikaClient) -> list[dict[str, Any]]:
    """Read the Plan as it stands right now.

    Immediately before writing, deliberately. The Mirror may be seconds old and
    still miss the meal she added on her phone while this was being drafted.

    Args:
        client: A signed-in client.

    Returns:
        list[dict[str, Any]]: Every meal Paprika currently holds.
    """
    fetched = client.get(MEALS_PATH, "reading your plan")
    if not isinstance(fetched, list):
        return []
    return [meal for meal in fetched if isinstance(meal, dict)]


def _occupying(
    meals: list[dict[str, Any]], date: str, meal_type: int
) -> dict[str, Any] | None:
    """Return whatever already sits in a slot.

    Args:
        meals: The Plan as just fetched.
        date: ``YYYY-MM-DD``.
        meal_type: The slot number.

    Returns:
        dict[str, Any] | None: The meal there, or ``None`` when it is free.
    """
    for meal in meals:
        if meal.get("deleted"):
            continue
        if str(meal.get("date") or "")[:10] != date:
            continue
        if int(meal.get("type") or 0) == meal_type:
            return meal
    return None


def _post(client: PaprikaClient, entries: list[dict[str, Any]], attempted: str) -> None:
    """Send meal entries, which the API takes as an array.

    Args:
        client: A signed-in client.
        entries: The entries to upsert.
        attempted: What is being done, for the log.
    """
    client._post_object(MEALS_PATH, entries, attempted)


def set_slot(
    client: PaprikaClient,
    *,
    date: str,
    slot: str,
    name: str,
    recipe_uid: str | None,
    run: Run,
) -> str:
    """Put one meal on one date, replacing whatever was there.

    Args:
        client: A signed-in client.
        date: ``YYYY-MM-DD``.
        slot: Which meal of the day.
        name: What it says on the plan.
        recipe_uid: The recipe, or ``None`` when she planned something that is
            not a recipe at all — which is an ordinary case, not an edge one.
        run: The Run to capture the Pre-image into.

    Returns:
        str: What the slot now says, for reporting back.

    Raises:
        PaprikaError: On anything the wire says.
    """
    meal_type = slot_number(slot)
    current = _occupying(_fetch(client), date, meal_type)

    if current is None:
        # Nothing was there, so the Pre-image is the fact that nothing was: a
        # removal, which is exactly what undoing a newly filled slot has to do.
        entry: dict[str, Any] = {
            "uid": str(uuid.uuid4()).upper(),
            "recipe_uid": recipe_uid,
            "date": f"{date}{DAY_START}",
            "type": meal_type,
            "name": name,
            "order_flag": 0,
            "type_uid": "",
            "scale": None,
            "is_ingredient": False,
        }
        before = dict(entry, deleted=True)
    else:
        # Echo every key it already had, so anything Paprika keeps here that we
        # have never heard of survives the write.
        before = dict(current)
        entry = dict(current)
        entry["recipe_uid"] = recipe_uid
        entry["name"] = name
        entry["date"] = f"{date}{DAY_START}"
        entry["type"] = meal_type

    run.capture(KIND, str(entry["uid"]), f"{date} {slot}", before)
    _post(client, [entry], "saving your plan")
    run.mark_landed(KIND, str(entry["uid"]))
    log_event("plan_set", date=date, slot=slot, replaced=current is not None)
    return name


def clear_slot(client: PaprikaClient, *, date: str, slot: str, run: Run) -> str | None:
    """Empty one slot.

    Args:
        client: A signed-in client.
        date: ``YYYY-MM-DD``.
        slot: Which meal of the day.
        run: The Run to capture the Pre-image into.

    Returns:
        str | None: What was there, or ``None`` when it was already empty.

    Raises:
        PaprikaError: On anything the wire says.
    """
    meal_type = slot_number(slot)
    current = _occupying(_fetch(client), date, meal_type)
    if current is None:
        return None

    run.capture(KIND, str(current["uid"]), f"{date} {slot}", dict(current))
    _post(client, [dict(current, deleted=True)], "clearing your plan")
    run.mark_landed(KIND, str(current["uid"]))
    log_event("plan_clear", date=date, slot=slot)
    return str(current.get("name") or "")


def restore(client: PaprikaClient, body: dict[str, Any]) -> None:
    """Put a meal back exactly as it was.

    Undoing a slot that was filled from empty means posting the removal that its
    Pre-image records, which is why the Pre-image of a created meal is that
    removal rather than nothing at all.

    Args:
        client: A signed-in client.
        body: The Pre-image.
    """
    _post(client, [dict(body)], "putting your plan back")


def notify(client: PaprikaClient) -> None:
    """Tell her other devices to pull, so a saved Plan reaches her phone.

    Fire-and-forget by design: her plan is already saved, and a failure to
    announce it is not a failure to do it.

    Fired at a resting point — the end of a finished piece of work — and never
    per write, so saving seven nights does not buzz her phone seven times. The
    caller says when that point is; nothing here can tell from one command
    whether more are coming.

    Args:
        client: A signed-in client.
    """
    try:
        client._post_object("/api/v2/sync/notify/", {}, "telling your phone")
    except PaprikaError as unheard:
        log_event("notify_failed", reason=unheard.detail)
