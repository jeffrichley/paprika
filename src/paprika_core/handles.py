"""Handles — how a recipe is named in the session, since its uid never is.

Five hundred UUIDs is about ten thousand tokens of exactly the mechanic that must
not cross the fence. A handle is the first few hex characters of the uid,
lengthened only for the recipes that would otherwise collide. Being derived, it
needs no mapping table and is stable as long as the uid is.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

SHORTEST = 6
LONGEST = 32


def _hex_of(uid: str) -> str:
    """Return the uid's hex characters, lowercased and undashed.

    Args:
        uid: A Paprika uid.

    Returns:
        str: Just the hex, e.g. ``4a7f...``.
    """
    return "".join(c for c in uid.lower() if c in "0123456789abcdef")


def derive_handles(uids: Iterable[str]) -> dict[str, str]:
    """Derive one handle per uid, lengthening only where they would collide.

    Args:
        uids: Every uid in the Library. The whole set is needed, because
            uniqueness is a property of the set rather than of any one uid.

    Returns:
        dict[str, str]: uid to handle. A uid with no hex at all falls back to
            itself, so nothing is ever silently dropped.
    """
    handles: dict[str, str] = {}
    remaining = sorted(set(uids))
    length = SHORTEST

    while remaining and length <= LONGEST:
        grouped: dict[str, list[str]] = defaultdict(list)
        for uid in remaining:
            digits = _hex_of(uid)
            if not digits:
                handles[uid] = uid.lower()
                continue
            grouped[digits[:length]].append(uid)

        still_colliding: list[str] = []
        for candidate, owners in grouped.items():
            if len(owners) == 1:
                handles[owners[0]] = candidate
            else:
                still_colliding.extend(owners)

        remaining = still_colliding
        length += 2

    # Anything still colliding at full length shares its every hex digit; the uid
    # itself is then the only thing left that distinguishes them.
    for uid in remaining:
        handles[uid] = uid.lower()
    return handles
