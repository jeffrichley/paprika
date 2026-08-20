"""Pre-images, Runs and undo — what makes damage recoverable when it happens.

A Pre-image is the whole object and never a diff, because only a whole object
can be re-posted. It is captured before the write and committed immediately, so
a Run that dies partway holds exactly what it touched.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from paprika_core import store, undo, write
from paprika_core.session import sign_in
from tests.fake_paprika import FakePaprika


def _a_recipe(fake: FakePaprika) -> str:
    """Return the uid of a recipe that is in her Library.

    Args:
        fake: The seeded fake account.

    Returns:
        str: A uid.
    """
    return next(uid for uid, r in fake.recipes.items() if not r["in_trash"])


def _seed_runs(count: int, started_at: float | None = None) -> list[str]:
    """Insert bare Runs directly, to exercise retention without writing.

    Args:
        count: How many to insert.
        started_at: When they started, or ``None`` for now.

    Returns:
        list[str]: The ids inserted, oldest first.
    """
    ids = []
    db = sqlite3.connect(store.undo_path())
    db.executescript(undo.SCHEMA)
    for index in range(count):
        run_id = f"seeded-{index:03d}"
        db.execute(
            "INSERT INTO runs (id, started_at) VALUES (?, ?)",
            (run_id, started_at if started_at is not None else time.time()),
        )
        db.execute(
            "INSERT INTO pre_images"
            " (run_id, kind, uid, name, body, captured_at, landed)"
            " VALUES (?, 'recipes', ?, 'Something', '{}', ?, 1)",
            (run_id, f"uid-{index}", time.time()),
        )
        ids.append(run_id)
    db.commit()
    db.close()
    return ids


def test_the_pre_image_store_is_not_the_mirror(paprika_home: Path) -> None:
    """The Mirror is disposable; an undo history is not. Different files."""
    assert store.undo_path() != store.mirror_path()
    assert store.undo_path().name == "undo.sqlite3"


def test_a_pre_image_is_the_whole_object(signed_in: Path, seeded: FakePaprika) -> None:
    uid = _a_recipe(seeded)
    before = dict(seeded.recipes[uid])

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("rating", 1), run=run)
        captured = run.pre_image("recipes", uid)

    assert captured is not None
    assert captured.body == before


def test_a_pre_image_is_committed_before_the_write_reaches_paprika(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A Run that dies partway must hold exactly what it touched."""
    uid = _a_recipe(seeded)
    seeded.fail_writes = True

    run_id = ""
    try:
        with undo.open_run() as run:
            run_id = run.id
            write.write(sign_in(), uid, lambda r: r.__setitem__("rating", 1), run=run)
    except Exception:
        pass

    kept = undo.pre_images_of(run_id)
    assert len(kept) == 1
    # Captured, but never marked as landed — nothing actually moved.
    assert undo.recent_runs() == []


def test_undo_puts_a_change_back(signed_in: Path, seeded: FakePaprika) -> None:
    uid = _a_recipe(seeded)
    before = dict(seeded.recipes[uid])

    with undo.open_run() as first:
        write.write(
            sign_in(), uid, lambda r: r.__setitem__("name", "Wrong Name"), run=first
        )
        run_id = first.id

    assert seeded.recipes[uid]["name"] == "Wrong Name"

    with undo.open_run() as second:
        for pre_image in undo.pre_images_of(run_id):
            write.restore(sign_in(), pre_image, run=second)

    assert seeded.recipes[uid]["name"] == before["name"]


def test_undoing_a_run_returns_things_to_how_they_started(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Two edits to one recipe in one Run still undo to where the Run began."""
    uid = _a_recipe(seeded)
    original = seeded.recipes[uid]["name"]

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("name", "First"), run=run)
        write.write(sign_in(), uid, lambda r: r.__setitem__("name", "Second"), run=run)
        run_id = run.id

    with undo.open_run() as second:
        for pre_image in undo.pre_images_of(run_id):
            write.restore(sign_in(), pre_image, run=second)

    assert seeded.recipes[uid]["name"] == original


def test_a_run_reports_what_moved_by_kind(signed_in: Path, seeded: FakePaprika) -> None:
    uids = [uid for uid, r in seeded.recipes.items() if not r["in_trash"]][:2]

    with undo.open_run() as run:
        for uid in uids:
            write.write(sign_in(), uid, lambda r: r.__setitem__("rating", 3), run=run)
        assert run.changed() == {"recipes": 2}


def test_a_later_write_joins_an_open_run(signed_in: Path, seeded: FakePaprika) -> None:
    uid = _a_recipe(seeded)

    with undo.open_run() as first:
        write.write(sign_in(), uid, lambda r: r.__setitem__("rating", 1), run=first)
        run_id = first.id

    other = next(u for u, r in seeded.recipes.items() if not r["in_trash"] and u != uid)
    with undo.open_run(run_id) as joined:
        assert joined.id == run_id
        write.write(sign_in(), other, lambda r: r.__setitem__("rating", 2), run=joined)

    assert len(undo.pre_images_of(run_id)) == 2


def test_a_stale_run_id_is_inert_rather_than_an_error(paprika_home: Path) -> None:
    """Resume re-proposes rather than replays, so a stale id must not resurrect."""
    with undo.open_run("a-run-that-never-existed") as run:
        assert run.id != "a-run-that-never-existed"


def test_undo_is_offered_by_what_moved_never_by_an_id(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """She never sees a Run id, so the listing is phrased in what changed."""
    uid = _a_recipe(seeded)
    name = seeded.recipes[uid]["name"]

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("rating", 5), run=run)

    listed = undo.recent_runs()
    assert len(listed) == 1
    assert listed[0].changed == {"recipes": 1}
    assert listed[0].names == [name]


def test_a_run_that_moved_nothing_is_not_something_she_did(
    paprika_home: Path,
) -> None:
    with undo.open_run():
        pass

    assert undo.recent_runs() == []


def test_retention_keeps_the_last_ten_runs(paprika_home: Path) -> None:
    _seed_runs(15, started_at=time.time() - undo.KEEP_SECONDS - 60)

    # Opening a Run prunes, so the eleventh-oldest and beyond should go.
    with undo.open_run():
        pass

    assert len(undo.recent_runs(limit=100)) == undo.KEEP_RUNS


def test_retention_keeps_anything_from_the_last_week(paprika_home: Path) -> None:
    """Ten Runs *plus* seven days — whichever keeps more."""
    _seed_runs(15, started_at=time.time() - 60)

    with undo.open_run():
        pass

    assert len(undo.recent_runs(limit=100)) == 15


def test_pre_images_of_a_forgotten_run_are_simply_empty(paprika_home: Path) -> None:
    assert undo.pre_images_of("long-gone") == []
