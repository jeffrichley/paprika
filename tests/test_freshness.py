"""Freshness is established by asking, never by a clock.

This is not a caching optimisation. Deletions leave **no tombstone**, so a
Mirror that merely looks recent can still be serving a recipe she deleted on her
phone, and would never learn otherwise. A moved counter is the only signal that
exists.
"""

from __future__ import annotations

from pathlib import Path

from paprika_core import freshness, sync
from paprika_core.mirror import Mirror
from paprika_core.session import sign_in
from tests.fake_paprika import FakePaprika
from tests.helpers import a_while_later
from tests.library import LIBRARY_SIZE, make_recipe, sync_hash


def _status_calls(fake: FakePaprika) -> int:
    """Count the requests that hit ``/sync/status/``.

    Args:
        fake: The fake account.

    Returns:
        int: How many times freshness was asked about.
    """
    return sum(1 for _, path in fake.requests if path == "/api/v2/sync/status/")


def _recipe_fetches(fake: FakePaprika) -> list[str]:
    """Return the paths of every whole-recipe fetch.

    Args:
        fake: The fake account.

    Returns:
        list[str]: One entry per body actually downloaded.
    """
    return [p for m, p in fake.requests if m == "GET" and "/sync/recipe/" in p]


def test_a_read_asks_before_it_serves(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """One request, and the Mirror has proved itself rather than assumed itself."""
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    seeded.requests.clear()

    result = freshness.ensure_current(sign_in(), mirror)

    assert result.asked is True
    assert _status_calls(seeded) == 1


def test_unchanged_counters_cost_exactly_one_request(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    seeded.requests.clear()

    result = freshness.ensure_current(sign_in(), mirror)

    assert result.refreshed == {}
    assert len(seeded.requests) == 1
    assert _recipe_fetches(seeded) == []


def test_a_moved_counter_refetches_only_what_differs(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """Warm cost is one request; changed is two plus however many actually differ."""
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    changed = next(iter(seeded.recipes))
    seeded.recipes[changed]["name"] = "Renamed On Her Phone"
    seeded.recipes[changed]["hash"] = sync_hash("moved")
    seeded.counters["recipes"] += 1
    seeded.requests.clear()

    result = freshness.ensure_current(sign_in(), mirror)

    assert result.refreshed == {"recipes": 1}
    assert len(_recipe_fetches(seeded)) == 1
    assert any(r.name == "Renamed On Her Phone" for r in mirror.recipes())


def test_a_recipe_she_deleted_is_dropped_from_the_mirror(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """The whole reason freshness is asked rather than timed: there is no tombstone."""
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    gone = next(uid for uid, r in seeded.recipes.items() if not r["in_trash"])
    gone_name = seeded.recipes[gone]["name"]
    del seeded.recipes[gone]
    seeded.counters["recipes"] += 1

    freshness.ensure_current(sign_in(), mirror)

    assert all(r.name != gone_name for r in mirror.recipes())
    assert mirror.count_recipes() == LIBRARY_SIZE - 1


def test_a_new_recipe_arrives(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    fresh_uid = "0A1B2C3D-4E5F-4A6B-8C7D-9E0F1A2B3C4D"
    seeded.recipes[fresh_uid] = make_recipe(fresh_uid, "Added On Her Phone")
    seeded.counters["recipes"] += 1

    result = freshness.ensure_current(sign_in(), mirror)

    assert result.refreshed == {"recipes": 1}
    assert any(r.name == "Added On Her Phone" for r in mirror.recipes())


def test_a_burst_of_reads_asks_once(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """A short validation stamp collapses one conversation's reads into one check."""
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    seeded.requests.clear()

    first = freshness.ensure_current(sign_in(), mirror)
    second = freshness.ensure_current(sign_in(), mirror)
    third = freshness.ensure_current(sign_in(), mirror)

    assert first.asked is True
    assert (second.asked, third.asked) == (False, False)
    assert _status_calls(seeded) == 1


def test_the_stamp_expires(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror, monkeypatch: object
) -> None:
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    freshness.ensure_current(sign_in(), mirror)
    seeded.requests.clear()
    a_while_later(mirror)

    assert freshness.ensure_current(sign_in(), mirror).asked is True
    assert _status_calls(seeded) == 1


def test_fresh_is_an_explicit_opt_in_that_ignores_the_stamp(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    freshness.ensure_current(sign_in(), mirror)
    seeded.requests.clear()

    result = freshness.ensure_current(sign_in(), mirror, force=True)

    assert result.asked is True
    assert _status_calls(seeded) == 1


def test_counters_are_change_markers_rather_than_counts(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """A counter that moved says something changed. It never says how many there are."""
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    # A counter that leaps by a hundred still means exactly "something changed".
    seeded.counters["recipes"] += 100
    seeded.requests.clear()

    result = freshness.ensure_current(sign_in(), mirror)

    assert result.refreshed == {}
    assert mirror.count_recipes() == LIBRARY_SIZE


def test_a_moved_category_counter_refetches_the_tree(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    seeded.categories.append(
        {
            "uid": "CAT-NEW",
            "name": "Weeknight",
            "parent_uid": "CAT-MAINS",
            "order_flag": 2,
        }
    )
    seeded.counters["categories"] += 1

    result = freshness.ensure_current(sign_in(), mirror)

    assert result.refreshed == {"categories": 8}
    assert "CAT-NEW" in mirror.category_names()


def test_an_unsynced_mirror_is_not_refreshed_into_existence(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """A Mirror that was never filled is a job for `sync`, not for a freshness check."""
    result = freshness.ensure_current(sign_in(), mirror)

    assert result.age_seconds is None
    assert mirror.count_recipes() == 0
