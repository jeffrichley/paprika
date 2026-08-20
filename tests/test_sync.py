"""The cold sync — one request, then one per recipe, committing as it goes."""

from __future__ import annotations

from pathlib import Path

import pytest

from paprika_core import freshness, store, sync
from paprika_core.mirror import Mirror
from paprika_core.session import sign_in
from tests.fake_paprika import FakePaprika
from tests.helpers import a_while_later
from tests.library import LIBRARY_SIZE, sync_hash


def test_a_cold_sync_costs_one_request_per_recipe(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """There is no bulk recipe download, and no way round it."""
    sync.cold_sync(sign_in(), mirror)

    fetches = [p for m, p in seeded.requests if m == "GET" and "/sync/recipe/" in p]
    assert len(fetches) == len(seeded.recipes)


def test_a_cold_sync_fills_the_library_and_the_tree(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    assert sync.cold_sync(sign_in(), mirror) == LIBRARY_SIZE
    assert len(mirror.categories()) == 7


def test_a_cold_sync_records_the_counters_it_saw(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """Kept so a later read can establish freshness by asking, not by a clock."""
    sync.cold_sync(sign_in(), mirror)

    assert mirror.get_meta("counters") == seeded.counters
    assert mirror.age_seconds() is not None


def test_an_interrupted_sync_keeps_what_landed(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A cold sync commits incrementally, so a crash costs a slice, not the run."""

    def stop_after_two(done: int, total: int) -> None:
        if done == 2:
            raise KeyboardInterrupt

    with Mirror(store.mirror_path()) as first, pytest.raises(KeyboardInterrupt):
        sync.cold_sync(sign_in(), first, progress=stop_after_two)

    with Mirror(store.mirror_path()) as second:
        assert second.count_recipes() == 2


def test_a_renewal_mid_sync_does_not_discard_what_landed(
    credentials_present: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """The retry is around one request. Re-running the run would empty the Mirror."""
    store.save_token("stale")

    assert sync.cold_sync(sign_in(), mirror) == LIBRARY_SIZE


def test_a_stub_with_no_identity_is_skipped(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    seeded.recipes[""] = {"uid": "", "hash": "0" * 64}

    sync.cold_sync(sign_in(), mirror)

    assert mirror.count_recipes() == LIBRARY_SIZE


def test_trashed_recipes_arrive_and_are_filtered_here(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    """`in_trash` is not removal, so the Mirror filters rather than expects absence."""
    trashed = next(uid for uid, r in seeded.recipes.items() if r["in_trash"])

    sync.cold_sync(sign_in(), mirror)

    # It was downloaded — one request per recipe, trashed ones included.
    assert any(trashed in path for _, path in seeded.requests)
    # And it is held, so a later un-trash costs nothing and undo has something.
    assert trashed in mirror.recipe_tokens()
    # But it is not in her Library.
    assert mirror.count_recipes() == LIBRARY_SIZE


def test_a_recipe_she_trashed_on_her_phone_leaves_the_library(
    signed_in: Path, seeded: FakePaprika, mirror: Mirror
) -> None:
    sync.cold_sync(sign_in(), mirror)
    a_while_later(mirror)
    victim = next(uid for uid, r in seeded.recipes.items() if not r["in_trash"])
    seeded.recipes[victim]["in_trash"] = True
    seeded.recipes[victim]["hash"] = sync_hash("trashed-now")
    seeded.counters["recipes"] += 1

    freshness.ensure_current(sign_in(), mirror)

    assert mirror.count_recipes() == LIBRARY_SIZE - 1


def test_an_interrupted_sync_resumes_rather_than_restarting(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Stopping is cheap. Re-running must not re-download what already landed."""

    def stop_after_two(done: int, total: int) -> None:
        if done == 2:
            raise KeyboardInterrupt

    with Mirror(store.mirror_path()) as first, pytest.raises(KeyboardInterrupt):
        sync.cold_sync(sign_in(), first, progress=stop_after_two)

    seeded.requests.clear()
    with Mirror(store.mirror_path()) as second:
        assert sync.cold_sync(sign_in(), second) == LIBRARY_SIZE

    fetched = [p for m, p in seeded.requests if m == "GET" and "/sync/recipe/" in p]
    # Five recipes in the account, two already held: three left to fetch.
    assert len(fetched) == len(seeded.recipes) - 2
