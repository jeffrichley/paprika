"""Small utilities shared by more than one test module."""

from __future__ import annotations

from paprika_core.mirror import Mirror


def a_while_later(mirror: Mirror) -> None:
    """Expire the Mirror's validation stamp, so the next read has to ask again.

    A sync has just asked Paprika everything, so it stamps the Mirror and a read
    seconds later correctly costs nothing. A test about the read that happens
    *later* says so here, rather than depending on wall-clock time passing.

    Args:
        mirror: The Mirror whose stamp should be treated as expired.
    """
    mirror.set_meta("checked_at", 0.0)
