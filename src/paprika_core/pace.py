"""How long a wait is likely to be, measured rather than assumed.

There are no timeouts and no budgets anywhere in this plugin. Long work is
resumable because it commits incrementally, not because a clock cuts it off —
cutting work off to satisfy a timer is the wrong reason to stop.

What remains is the **silence**, and the answer to silence is to say how long it
will last before it starts. The number comes from the per-request durations
already in her own log, so it calibrates to her connection rather than to a
figure in a research document. The published ~200 ms is used exactly once: on a
first run, before there is anything to measure.
"""

from __future__ import annotations

import json
from statistics import median

from paprika_core.log import log_path

#: The published figure, used only until this machine has measured its own.
FALLBACK_SECONDS = 0.2

#: How many recent requests the estimate is drawn from. Enough to be stable,
#: few enough that a connection that got slower last week does not haunt it.
SAMPLE = 200

__all__ = ["FALLBACK_SECONDS", "cold_sync_seconds", "typical_request_seconds"]


def _recent_durations(limit: int = SAMPLE) -> list[float]:
    """Read recent per-request durations out of the log.

    A malformed line is skipped rather than fatal: the log is diagnostic, and an
    estimate is not worth failing a command over.

    Args:
        limit: How many of the most recent requests to consider.

    Returns:
        list[float]: Durations in milliseconds, oldest first. Empty when the log
            is absent, unreadable, or holds no timed request.
    """
    path = log_path()
    try:
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-(limit * 2) :]
    except OSError:
        return []

    durations: list[float] = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("event") != "request":
            continue
        value = record.get("ms")
        if isinstance(value, (int, float)):
            durations.append(float(value))
    return durations[-limit:]


def typical_request_seconds() -> float:
    """Return how long one request to Paprika usually takes on this machine.

    The **median**, not the mean: one request that stalled for a minute must not
    turn a two-minute estimate into an hour.

    Returns:
        float: Seconds per request, falling back to the published figure only
            when this machine has never measured one.
    """
    durations = _recent_durations()
    if not durations:
        return FALLBACK_SECONDS
    return median(durations) / 1000.0


def cold_sync_seconds(recipe_count: int) -> float:
    """Estimate how long downloading the whole Library will take.

    One request for the index plus one per recipe — there is no bulk recipe
    download, and that is the dominant cost in the whole API.

    Args:
        recipe_count: How many recipes are expected.

    Returns:
        float: Estimated seconds. A skill turns 103 into "about two minutes".
    """
    return typical_request_seconds() * (max(0, recipe_count) + 1)
