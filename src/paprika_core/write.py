"""The one place a write can happen, and it never accepts a payload.

Every write to Paprika is a **full-object POST**: any field absent from what you
send is destroyed on the server and propagated to her phone. There is no partial
update and no concurrency control — a stale change marker is accepted and stored,
so the server will not catch a mistake for you.

Two facts make "just be careful" untenable. The recipe object carries thirty-five
fields, seven of them undocumented and currently ``null``, which is exactly what
makes them cheap to omit and expensive to lose. And the obvious safe-looking rule
— *echo back every key you received* — is itself a bug when applied to ``hash``,
because sync is driven by hash **inequality**: echoing the fetched one produces a
write the server accepts and no other device ever pulls.

So there is one function. It fetches the object, hands the caller the fetched
dict to modify, and posts the result. **A caller may change keys; a caller may
never choose the key set.** The two exceptions to echo-everything —
regenerating ``hash``, stripping ``photo_url`` — look like inconsistencies in an
otherwise uniform rule. They are the two places where uniformity is the bug, and
they should not be flattened away by anyone who finds this verbose.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from paprika_core.errors import Code, PaprikaError
from paprika_core.http import PaprikaClient
from paprika_core.log import log_event
from paprika_core.undo import PreImage, Run

RECIPE_PATH = "/api/v2/sync/recipe/{uid}/"

#: What the caller is handed: the fetched object, to modify in place.
Mutation = Callable[[dict[str, Any]], None]

#: Response-only. Expires within hours, and sending it back is a malformed write.
STRIPPED = "photo_url"

#: An outgoing change marker, not incoming data.
CHANGE_MARKER = "hash"

#: Removal, and reserved for objects the plugin created and is cleaning up. What
#: she calls deleting is `in_trash`, so her recovery is the app's own trash and
#: never depends on our snapshot surviving.
REMOVAL = "deleted"

#: Must be null when absent, never `""`, or Paprika answers a bare 500.
PHOTO_FIELDS = ("photo", "photo_hash", "photo_large")

_REFUSED = "That change didn't look right, so nothing was sent to Paprika."


def new_change_marker() -> str:
    """Mint a change marker for an outgoing write.

    Any 64-hex value is accepted; the server neither derives nor validates it
    beyond the format. It must be **new** on every write, because a value equal
    to the stored one is a change no other device will ever pull.

    Returns:
        str: Sixty-four hex characters, never seen before.
    """
    return secrets.token_hex(32)


def _prepare(fetched: dict[str, Any], mutated: dict[str, Any]) -> dict[str, Any]:
    """Turn a mutated object into exactly what may go on the wire.

    Args:
        fetched: The object as Paprika returned it, for comparison.
        mutated: The same object after the caller changed it.

    Returns:
        dict[str, Any]: The payload.

    Raises:
        PaprikaError: When the mutation changed the key set, or left a photo
            field blank. Validation is client-side because a rejected write
            names no field and gives nothing to repair from.
    """
    allowed = (set(fetched) | {REMOVAL}) - {STRIPPED}
    present = set(mutated) - {STRIPPED}

    invented = present - allowed
    if invented:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            _REFUSED,
            detail=f"mutation added unknown fields: {sorted(invented)}",
        )
    dropped = (set(fetched) - {STRIPPED}) - present
    if dropped:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            _REFUSED,
            detail=f"mutation dropped fields: {sorted(dropped)}",
        )
    blank = [f for f in PHOTO_FIELDS if mutated.get(f) == ""]
    if blank:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            _REFUSED,
            detail=f"photo fields must be null, not empty: {blank}",
        )

    payload = dict(mutated)
    payload.pop(STRIPPED, None)
    payload[CHANGE_MARKER] = new_change_marker()
    return payload


def write(
    client: PaprikaClient,
    uid: str,
    mutate: Mutation,
    *,
    run: Run,
    kind: str = "recipes",
) -> str:
    """Change one recipe, and keep what it was.

    Fetches it, captures the Pre-image, hands ``mutate`` the fetched dict, and
    posts the result whole. The fetch happens milliseconds before the post, which
    is what collapses "the Mirror disagrees with Paprika" into "the Mirror is
    stale" and deletes the merge problem rather than solving it.

    Args:
        client: A signed-in client.
        uid: Which recipe. Resolved from a handle before it gets here.
        mutate: Called with the fetched object, to modify in place. It must
            return nothing; what it returns is ignored on purpose, so a caller
            cannot substitute an object of its own.
        run: The Run to capture the Pre-image into.
        kind: What kind of thing this is, for the envelope's ``changed`` map.

    Returns:
        str: The change marker written, so a bulk Run can verify itself later.

    Raises:
        PaprikaError: If the mutation is invalid, or on anything the wire says.
    """
    fetched = client.get(RECIPE_PATH.format(uid=uid), "reading a recipe")
    if not isinstance(fetched, dict):
        raise PaprikaError(
            Code.PAPRIKA_REFUSED,
            "Paprika couldn't find that recipe.",
            detail=f"no object at {uid}",
        )

    run.capture(kind, uid, str(fetched.get("name") or ""), deepcopy(fetched))

    mutated = deepcopy(fetched)
    mutate(mutated)
    payload = _prepare(fetched, mutated)

    client._post_object(RECIPE_PATH.format(uid=uid), payload, "saving a recipe")
    run.mark_landed(kind, uid)
    log_event("write", kind=kind, fields=sorted(payload))
    return str(payload[CHANGE_MARKER])


def restore(client: PaprikaClient, pre_image: PreImage, *, run: Run) -> str:
    """Put an object back exactly as it was.

    Undo is not a special mechanism: because writes are full-object and
    idempotent, restoring is re-posting the Pre-image through this same
    chokepoint. That is what makes it work even for an object removed with
    ``deleted`` — verified live against a real account, fully resurrected.

    Args:
        client: A signed-in client.
        pre_image: What the object looked like before.
        run: The Run recording this restoration, so an undo is itself undoable.

    Returns:
        str: The change marker written.

    Raises:
        PaprikaError: On anything the wire says.
    """
    if pre_image.kind != "recipes":
        # Meals and pantry items are posted as arrays and their Pre-images may
        # themselves be removals, so each goes back the way it came rather than
        # through the recipe path.
        from paprika_core import groceries, pantry, plan

        collection = {
            "plan": plan.restore,
            "pantry": pantry.restore,
            "groceries": groceries.restore,
        }
        collection[pre_image.kind](client, pre_image.body)
        run.capture(
            pre_image.kind, pre_image.uid, pre_image.name, deepcopy(pre_image.body)
        )
        run.mark_landed(pre_image.kind, pre_image.uid)
        log_event("restore", kind=pre_image.kind)
        return ""

    body = deepcopy(pre_image.body)
    # Re-posting must not carry the removal flag that put it away.
    body.pop(REMOVAL, None)
    payload = _prepare(body, body)

    run.capture(pre_image.kind, pre_image.uid, pre_image.name, deepcopy(pre_image.body))
    client._post_object(
        RECIPE_PATH.format(uid=pre_image.uid), payload, "putting a recipe back"
    )
    run.mark_landed(pre_image.kind, pre_image.uid)
    log_event("restore", kind=pre_image.kind)
    return str(payload[CHANGE_MARKER])
