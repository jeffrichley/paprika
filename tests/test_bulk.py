"""A Run that starts failing stops, and says by name what did not go through.

One bad write must not become two hundred and fifty. And when it stops, a count
is something to be reassured by while a list is something she can act on — so
the things that did not land are named.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paprika_core import bulk, undo
from paprika_core.session import sign_in
from tests.fake_paprika import FakePaprika


def _targets(fake: FakePaprika) -> list[tuple[str, str, Any]]:
    """Build one target per recipe in her Library.

    Args:
        fake: The seeded fake account.

    Returns:
        list: ``(uid, name, mutation)`` for each.
    """

    def rate(recipe: dict[str, Any]) -> None:
        recipe["rating"] = 3

    return [
        (uid, str(recipe["name"]), rate)
        for uid, recipe in fake.recipes.items()
        if not recipe["in_trash"]
    ]


def test_a_whole_run_lands(signed_in: Path, seeded: FakePaprika) -> None:
    targets = _targets(seeded)

    with undo.open_run() as run:
        outcome = bulk.apply_all(sign_in(), targets, run=run)

    assert outcome.complete is True
    assert outcome.changed == {"recipes": len(targets)}
    assert sorted(outcome.landed) == sorted(name for _, name, _ in targets)
    assert outcome.missing == []


def test_a_run_that_starts_failing_stops(signed_in: Path, seeded: FakePaprika) -> None:
    """Two writes land, then Paprika refuses. The rest are never attempted."""
    targets = _targets(seeded)
    assert len(targets) > 3, "the fixture must have more targets than land"
    seeded.fail_writes_after = 2
    seeded.requests.clear()

    with undo.open_run() as run:
        outcome = bulk.apply_all(sign_in(), targets, run=run)

    assert outcome.complete is False
    assert outcome.error is not None
    assert outcome.changed == {"recipes": 2}
    assert len(seeded.writes) == 2
    # Two landed, the third was refused, and nothing after it was even tried.
    posts = [p for m, p in seeded.requests if m == "POST" and "/sync/recipe/" in p]
    assert len(posts) == 3


def test_a_stopped_run_names_what_did_not_go_through(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A list she can act on, rather than a count she can only be reassured by."""
    targets = _targets(seeded)
    seeded.fail_writes_after = 1

    with undo.open_run() as run:
        outcome = bulk.apply_all(sign_in(), targets, run=run)

    expected = [name for _, name, _ in targets[1:]]
    assert outcome.missing == expected
    assert outcome.landed == [targets[0][1]]


def test_a_stopped_run_is_still_one_run(signed_in: Path, seeded: FakePaprika) -> None:
    """Reported as one Run, so undo reverses exactly what it managed to do."""
    targets = _targets(seeded)
    seeded.fail_writes_after = 2

    with undo.open_run() as run:
        bulk.apply_all(sign_in(), targets, run=run)
        run_id = run.id

    listed = undo.recent_runs()
    assert len(listed) == 1
    assert listed[0].run_id == run_id
    assert listed[0].changed == {"recipes": 2}


def test_a_bulk_run_verifies_itself_in_one_request(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """We choose the marker we write, so the whole account's markers confirm it."""
    targets = _targets(seeded)
    seeded.requests.clear()

    with undo.open_run() as run:
        bulk.apply_all(sign_in(), targets, run=run)

    index_calls = [p for m, p in seeded.requests if p == "/api/v2/sync/recipes/"]
    assert len(index_calls) == 1


def test_verification_notices_a_write_that_did_not_stick(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The failure mode a status code would never have revealed."""
    targets = _targets(seeded)
    seeded.silently_discard = {targets[0][0]}

    with undo.open_run() as run:
        outcome = bulk.apply_all(sign_in(), targets, run=run)

    assert targets[0][1] in outcome.missing
    assert outcome.complete is False


def test_a_single_write_is_not_verified(signed_in: Path, seeded: FakePaprika) -> None:
    """Its read was milliseconds before its post, and its failure would be loud."""
    targets = _targets(seeded)[:1]
    seeded.requests.clear()

    with undo.open_run() as run:
        bulk.apply_all(sign_in(), targets, run=run)

    assert [p for m, p in seeded.requests if p == "/api/v2/sync/recipes/"] == []


def test_failing_to_verify_does_not_claim_a_write_was_lost(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Not knowing is not the same as knowing it did not land."""
    targets = _targets(seeded)
    seeded.fail_index_after_write = True

    with undo.open_run() as run:
        outcome = bulk.apply_all(sign_in(), targets, run=run)

    assert outcome.missing == []
    assert len(outcome.landed) == len(targets)
