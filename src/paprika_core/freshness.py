"""Freshness is established by asking, never by a clock.

A read serves the Mirror, but only after one request at ``/sync/status/`` proves
the Mirror current. **This is not a TTL optimisation.** Deletions leave no
tombstone: a recipe she removed on her phone simply stops appearing in the
collection, and nothing anywhere announces that it went. A Mirror trusted because
it merely *looks* recent would keep serving that recipe forever and never learn
otherwise. A moved counter is the only signal that exists.

Costs, per :doc:`ADR 0006 <../../docs/adr/0006-the-cli-splits-on-determinism>`:
one request when nothing changed, two plus however many recipes actually differ
when something did.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from paprika_core.http import STATUS_PATH, PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.sync import refresh_categories, refresh_recipes

#: How long one answer about freshness stays good for. It exists so a burst of
#: reads inside a single conversation costs one request rather than a dozen —
#: not to let the Mirror age quietly, which is what a TTL would do.
STAMP_SECONDS = 60.0


@dataclass(frozen=True)
class Freshness:
    """What establishing freshness cost and what it found.

    Attributes:
        asked: Whether Paprika was actually asked, or a recent answer was reused.
        refreshed: What was refetched, by kind. Empty when nothing had moved.
        age_seconds: How long ago the Mirror was last filled, or ``None`` if it
            never has been.
    """

    asked: bool
    refreshed: dict[str, int] = field(default_factory=dict)
    age_seconds: float | None = None


def ensure_current(
    client: PaprikaClient,
    mirror: Mirror,
    *,
    force: bool = False,
) -> Freshness:
    """Make the Mirror current, or prove that it already is.

    An empty Mirror is left alone: filling one is what ``sync`` is for, and a
    read that silently triggered a hundred-second cold sync would be a surprise
    rather than a service.

    Args:
        client: A signed-in client.
        mirror: The Mirror to establish freshness for.
        force: Ask even if a recent answer is still in hand. This is what
            ``--fresh`` opts into; it is never the default.

    Returns:
        Freshness: What it cost and what it found.

    Raises:
        PaprikaError: On anything the wire says.
    """
    age = mirror.age_seconds()
    if age is None:
        return Freshness(asked=False, age_seconds=None)

    if not force and mirror.checked_within(STAMP_SECONDS):
        return Freshness(asked=False, age_seconds=age)

    seen = mirror.counters()
    current = client.get(STATUS_PATH, "checking what Paprika has")
    counters = current if isinstance(current, dict) else {}
    mirror.mark_checked()

    refreshed: dict[str, int] = {}
    if _moved(seen, counters, "recipes"):
        changed = refresh_recipes(client, mirror)
        if changed:
            refreshed["recipes"] = changed
    if _moved(seen, counters, "categories"):
        refreshed["categories"] = refresh_categories(client, mirror)

    mirror.mark_synced(counters)
    log_event("freshness", refreshed=refreshed, forced=force)
    return Freshness(asked=True, refreshed=refreshed, age_seconds=mirror.age_seconds())


def _moved(seen: dict[str, int], current: dict[str, int], kind: str) -> bool:
    """Say whether one change counter has moved since we last looked.

    A counter is a monotonic change marker, never a count — how far it moved
    means nothing, only that it moved at all. A kind missing from either side is
    treated as moved, because not knowing is not the same as knowing it is
    unchanged.

    Args:
        seen: The counters stored at the last check.
        current: The counters Paprika just reported.
        kind: Which entity's counter to compare.

    Returns:
        bool: Whether that kind needs refetching.
    """
    if kind not in seen or kind not in current:
        return True
    return seen[kind] != current[kind]
