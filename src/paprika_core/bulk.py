"""Running many writes as one Run, and knowing afterwards which ones landed.

Two rules shape this, and both come from what a failure costs her:

**A Run that starts failing stops.** One bad write must not become two hundred
and fifty. When it stops, the envelope says what was attempted, what did not
happen, and which kinds of thing moved — and it names the ones that did not go
through, because a count is something to be reassured by while a list is
something she can act on.

**A bulk Run verifies itself in one request.** We choose the change marker we
write, so we know what every touched recipe should be carrying afterwards, and
``GET /sync/recipes/`` returns the whole account's markers in a single call.
Three hundred writes are verified for the price of one request. A single write
is not verified: its read happened milliseconds before its post, and its failure
would have been loud.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from paprika_core.errors import PaprikaError
from paprika_core.http import RECIPE_INDEX_PATH, PaprikaClient
from paprika_core.log import log_event
from paprika_core.undo import Run
from paprika_core.write import Mutation, write

#: One thing to change: which recipe, what she calls it, and how to change it.
Target = tuple[str, str, Mutation]


@dataclass
class Outcome:
    """What a Run did, phrased the way a failure has to be reported.

    Attributes:
        changed: What moved, by kind.
        landed: What she calls the things that went through.
        missing: What she calls the things that did not.
        complete: Whether every target was attempted and landed.
        error: Why it stopped, when it stopped early.
    """

    changed: dict[str, int] = field(default_factory=dict)
    landed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    complete: bool = True
    error: PaprikaError | None = None


def apply_all(
    client: PaprikaClient,
    targets: Sequence[Target],
    *,
    run: Run,
    kind: str = "recipes",
    progress: Callable[[int, int], None] | None = None,
) -> Outcome:
    """Write every target as one Run, stopping at the first failure.

    Args:
        client: A signed-in client.
        targets: What to change, as ``(uid, name, mutation)``.
        run: The Run to capture Pre-images into.
        kind: What kind of thing these are, for the ``changed`` map.
        progress: Called with ``(done, total)`` after each write lands.

    Returns:
        Outcome: What moved, what did not, and why it stopped.
    """
    expected: dict[str, str] = {}
    stopped_at: int | None = None
    failure: PaprikaError | None = None

    for index, (uid, _name, mutate) in enumerate(targets):
        try:
            expected[uid] = write(client, uid, mutate, run=run, kind=kind)
        except PaprikaError as error:
            # Stop rather than continue. One bad write is not two hundred.
            failure = error
            stopped_at = index
            log_event("run_stopped", at=index, of=len(targets), reason=error.detail)
            break
        if progress is not None:
            progress(index + 1, len(targets))

    attempted_names = [name for _, name, _ in targets]
    if stopped_at is None:
        unattempted: list[str] = []
    else:
        unattempted = attempted_names[stopped_at:]

    landed, missing = _verify(client, expected, targets)
    missing.extend(unattempted)

    return Outcome(
        changed=run.changed(),
        landed=landed,
        missing=missing,
        complete=stopped_at is None and not missing,
        error=failure,
    )


def _verify(
    client: PaprikaClient,
    expected: dict[str, str],
    targets: Sequence[Target],
) -> tuple[list[str], list[str]]:
    """Check what actually landed, in one request.

    Only worth doing in bulk: for a single write the read happened milliseconds
    before the post, so a separate confirmation buys nothing.

    Args:
        client: A signed-in client.
        expected: uid to the change marker we wrote for it.
        targets: What was being changed, for turning uids back into names.

    Returns:
        tuple[list[str], list[str]]: What landed and what did not, by name.
    """
    names = {uid: name for uid, name, _ in targets}
    if len(expected) < 2:
        return [names[uid] for uid in expected], []

    try:
        stubs = client.get(RECIPE_INDEX_PATH, "checking which changes were saved")
    except PaprikaError as error:
        # Failing to verify is not the same as failing to write. Say nothing
        # rather than claim something did not land when it may well have.
        log_event("run_unverified", reason=error.detail)
        return [names[uid] for uid in expected], []

    live: dict[str, Any] = {
        str(stub.get("uid", "")): stub.get("hash")
        for stub in (stubs if isinstance(stubs, list) else [])
        if isinstance(stub, dict)
    }
    landed = [names[uid] for uid, marker in expected.items() if live.get(uid) == marker]
    missing = [
        names[uid] for uid, marker in expected.items() if live.get(uid) != marker
    ]
    log_event("run_verified", landed=len(landed), missing=len(missing))
    return landed, missing
