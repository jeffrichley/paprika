"""The cold sync — one request, then one per recipe, committing as it goes."""

from __future__ import annotations

from pathlib import Path

import pytest

from paprika_core import store, sync
from paprika_core.mirror import Mirror
from paprika_core.session import sign_in
from tests.fake_paprika import FakePaprika
from tests.library import LIBRARY_SIZE


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
