"""The Pantry — what she has in the house, and how old that belief is.

Two asymmetries decide everything here.

**Only she can say something is gone.** Anything else — a photograph, a planned
day passing, an item not mentioned after a shop — is evidence that something *is*
there, never evidence that something is not. A jar behind the cereal is not a jar
that is gone. So intake is **merge-only**: nothing is ever removed for failing to
be mentioned, and the fix for a stale item is to ask about it rather than to
infer it away.

**The age is part of the fact.** "You have cumin" and "you had cumin three weeks
ago" are different claims, and a caller that could read the first without the
second would subtract confidently from a belief nobody has checked since.

Names only. ``in_stock`` is the single field the grocery subtraction reads, and
her own vocabulary is already binary — *"the soy sauce is nearly empty"* means it
is off the list. A quantity read off a shelf is invented specificity in a field
nothing consumes, wrong within a week.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from paprika_core import store
from paprika_core.http import PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.sync import PANTRY_PATH
from paprika_core.undo import Run

#: The kind this writes, for the envelope's `changed` map.
KIND = "pantry"

#: Where the age of the belief is kept. Machine state, not hers.
CHECKED_AT = "pantry_checked_at"


def _fetch(client: PaprikaClient) -> list[dict[str, Any]]:
    """Read the Pantry as it stands right now.

    Args:
        client: A signed-in client.

    Returns:
        list[dict[str, Any]]: Every pantry item Paprika currently holds.
    """
    fetched = client.get(PANTRY_PATH, "reading your pantry")
    if not isinstance(fetched, list):
        return []
    return [item for item in fetched if isinstance(item, dict)]


def _existing(items: list[dict[str, Any]], ingredient: str) -> dict[str, Any] | None:
    """Return the item she already has for an ingredient, if any.

    Args:
        items: The Pantry as just fetched.
        ingredient: What she called it.

    Returns:
        dict[str, Any] | None: The item, or ``None``.
    """
    wanted = ingredient.strip().casefold()
    for item in items:
        if str(item.get("ingredient") or "").strip().casefold() == wanted:
            return item
    return None


def _new_item(ingredient: str, in_stock: bool, mirror: Mirror) -> dict[str, Any]:
    """Build a pantry entry for something she has not had before.

    The aisle is looked up in her own account and never invented; no match means
    no aisle, which degrades the entry rather than blocking the write.

    ``purchase_date`` is deliberately absent. Nothing here knows when she bought
    something, and a date we made up would look exactly like one she gave us.
    There is no ``name`` field on a pantry item at all — groceries and pantry are
    not symmetric, whatever the shape of one suggests about the other.

    Args:
        ingredient: What it is, in her words.
        in_stock: Whether she has it.
        mirror: The Mirror, for her ingredient-to-aisle scheme.

    Returns:
        dict[str, Any]: The entry.
    """
    aisle, aisle_uid = mirror.aisle_for(ingredient)
    return {
        "uid": str(uuid.uuid4()).upper(),
        "ingredient": ingredient.strip(),
        "aisle": aisle,
        "aisle_uid": aisle_uid,
        "quantity": "",
        "in_stock": in_stock,
        "has_expiration": False,
        "expiration_date": None,
    }


def set_stock(
    client: PaprikaClient,
    ingredients: list[str],
    *,
    in_stock: bool,
    mirror: Mirror,
    run: Run,
) -> list[str]:
    """Record that she has, or no longer has, each of these.

    An ingredient she already has is a **read-modify-write on the fetched
    object** — fetch it, flip the one field, post it back whole. Creating a fresh
    entry instead would orphan the aisle her account had learned for it and lose
    whatever else it carried.

    Args:
        client: A signed-in client.
        ingredients: What she named.
        in_stock: Whether she has them.
        mirror: The Mirror, for her ingredient-to-aisle scheme.
        run: The Run to capture Pre-images into.

    Returns:
        list[str]: What was recorded, in the order she said it.

    Raises:
        PaprikaError: On anything the wire says.
    """
    current = _fetch(client)
    entries: list[dict[str, Any]] = []
    recorded: list[str] = []

    for raw in ingredients:
        ingredient = raw.strip()
        if not ingredient:
            continue
        found = _existing(current, ingredient)
        if found is None:
            if not in_stock:
                # Nothing to mark gone. Inventing an out-of-stock entry for
                # something she never had would put a fact where there was none.
                continue
            entry = _new_item(ingredient, in_stock, mirror)
            before = dict(entry, deleted=True)
        else:
            before = dict(found)
            entry = dict(found)
            entry["in_stock"] = in_stock
        run.capture(KIND, str(entry["uid"]), ingredient, before)
        entries.append(entry)
        recorded.append(ingredient)

    if entries:
        client._post_object(PANTRY_PATH, entries, "saving your pantry")
        for entry in entries:
            run.mark_landed(KIND, str(entry["uid"]))
    log_event("pantry_write", count=len(entries), in_stock=in_stock)
    return recorded


def restore(client: PaprikaClient, body: dict[str, Any]) -> None:
    """Put a pantry entry back exactly as it was.

    Args:
        client: A signed-in client.
        body: The Pre-image.
    """
    client._post_object(PANTRY_PATH, [dict(body)], "putting your pantry back")


def mark_checked() -> None:
    """Record that the Pantry was just looked at.

    Any interaction counts — confirming, adding after a shop, saying something
    has run out. What is being recorded is when the belief was last touched by
    her, which is the only thing that makes its age meaningful.
    """
    document = store.read_state()
    document[CHECKED_AT] = time.time()
    store.write_state(document)


def age_days() -> float | None:
    """Return how long ago the Pantry was last confirmed.

    Returns:
        float | None: Days since she last touched it, or ``None`` when she never
            has — which is not the same as zero and must not be shown as it.
    """
    stamp = store.read_state().get(CHECKED_AT)
    if not isinstance(stamp, (int, float)):
        return None
    return max(0.0, (time.time() - float(stamp)) / 86400.0)
