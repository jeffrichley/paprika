"""Pre-images and Runs — ``~/.paprika/undo.sqlite3``.

Deliberately **not** ``cache.sqlite3``. The Mirror is disposable and gets thrown
away whenever it is easier to rebuild than to reason about; an undo history is
not disposable, and the two must not share a fate.

A Pre-image is the **whole object**, never a diff, because only a whole object
can be re-posted — and re-posting a Pre-image through the same chokepoint is the
entire undo mechanism. It is captured *before* the write and committed
immediately, so a Run that dies partway holds exactly what it touched.

A Walk contains Runs rather than being one: each confirmed group, or each yes,
is its own Run, so undo reverses what she just did rather than the whole evening.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from paprika_core import store
from paprika_core.log import log_event

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id         TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at   REAL
);
CREATE TABLE IF NOT EXISTS pre_images (
    run_id      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    uid         TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL,
    captured_at REAL NOT NULL,
    landed      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, kind, uid)
);
"""

#: Retention: the last ten Runs, plus anything from the last seven days.
KEEP_RUNS = 10
KEEP_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class PreImage:
    """One object exactly as it stood before we touched it.

    Attributes:
        kind: What kind of thing it is — ``recipes``, ``plan``, and so on.
        uid: Its identifier. Stays inside the core.
        name: What she would call it, for saying which things did not land.
        body: The whole object.
    """

    kind: str
    uid: str
    name: str
    body: dict[str, Any]


@dataclass(frozen=True)
class RunSummary:
    """One past Run, described by what it moved rather than by its id.

    She never sees a Run id, so a summary is phrased in what changed and when.

    Attributes:
        run_id: The id, for a caller to pass back. Never shown to her.
        changed: What moved, by kind.
        names: What the things were called.
        ended_at: When the Run finished, as a Unix timestamp.
    """

    run_id: str
    changed: dict[str, int]
    names: list[str]
    ended_at: float | None


class Run:
    """One unit of work that can be undone as a whole.

    Args:
        run_id: The Run's id.
        db: The open undo database.
    """

    def __init__(self, run_id: str, db: sqlite3.Connection) -> None:
        self.id = run_id
        self._db = db

    def capture(self, kind: str, uid: str, name: str, body: dict[str, Any]) -> None:
        """Record what an object looked like before it was written.

        Committed immediately. A Run that dies partway must hold exactly what it
        touched, and no more.

        An object already captured in this Run keeps its **first** Pre-image:
        undoing a Run should return things to how they were when it started, not
        to how they were midway through it.

        Args:
            kind: What kind of thing it is.
            uid: Its identifier.
            name: What she would call it.
            body: The whole object, as fetched.
        """
        self._db.execute(
            "INSERT OR IGNORE INTO pre_images"
            " (run_id, kind, uid, name, body, captured_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (self.id, kind, uid, name, json.dumps(body), time.time()),
        )
        self._db.commit()

    def mark_landed(self, kind: str, uid: str) -> None:
        """Record that a write actually reached Paprika.

        Args:
            kind: What kind of thing it is.
            uid: Its identifier.
        """
        self._db.execute(
            "UPDATE pre_images SET landed = 1"
            " WHERE run_id = ? AND kind = ? AND uid = ?",
            (self.id, kind, uid),
        )
        self._db.commit()

    def pre_image(self, kind: str, uid: str) -> PreImage | None:
        """Return one captured Pre-image.

        Args:
            kind: What kind of thing it is.
            uid: Its identifier.

        Returns:
            PreImage | None: The Pre-image, or ``None`` if this Run has none.
        """
        row = self._db.execute(
            "SELECT kind, uid, name, body FROM pre_images"
            " WHERE run_id = ? AND kind = ? AND uid = ?",
            (self.id, kind, uid),
        ).fetchone()
        return _as_pre_image(row) if row else None

    def pre_images(self) -> list[PreImage]:
        """Return every Pre-image this Run captured, newest first.

        Undo re-posts them in reverse order of capture, so a Run that touched
        the same thing twice still ends where it began.

        Returns:
            list[PreImage]: The Pre-images.
        """
        rows = self._db.execute(
            "SELECT kind, uid, name, body FROM pre_images"
            " WHERE run_id = ? ORDER BY captured_at DESC",
            (self.id,),
        )
        return [_as_pre_image(row) for row in rows]

    def changed(self) -> dict[str, int]:
        """Return what actually moved in this Run, by kind.

        Counts only writes that landed, because the envelope's ``changed`` is
        the fact that decides whether retrying is safe.

        Returns:
            dict[str, int]: Kind to how many of them moved.
        """
        rows = self._db.execute(
            "SELECT kind, COUNT(*) AS n FROM pre_images"
            " WHERE run_id = ? AND landed = 1 GROUP BY kind",
            (self.id,),
        )
        return {row["kind"]: int(row["n"]) for row in rows}

    def landed_names(self) -> list[str]:
        """Return what she would call the things that moved.

        Returns:
            list[str]: Names, in the order they landed.
        """
        rows = self._db.execute(
            "SELECT name FROM pre_images"
            " WHERE run_id = ? AND landed = 1 ORDER BY captured_at",
            (self.id,),
        )
        return [row["name"] for row in rows]


def _as_pre_image(row: sqlite3.Row) -> PreImage:
    """Build a Pre-image from a database row.

    Args:
        row: The row.

    Returns:
        PreImage: The Pre-image.
    """
    return PreImage(
        kind=row["kind"],
        uid=row["uid"],
        name=row["name"],
        body=json.loads(row["body"]),
    )


def _connect() -> sqlite3.Connection:
    """Open the undo database, creating it if it is not there.

    Returns:
        sqlite3.Connection: The open connection.
    """
    store.ensure_home()
    db = sqlite3.connect(store.undo_path())
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.commit()
    return db


@contextmanager
def open_run(run_id: str | None = None) -> Iterator[Run]:
    """Open a Run, creating one unless a caller is joining an existing one.

    The CLI mints the id and hands it back; a caller passes it to ``--run`` to
    join later writes to the same Run. A caller naming its own would put a
    durable identifier in a prompt, and a stale one must be inert rather than
    resurrectable.

    Args:
        run_id: An open Run to join, or ``None`` to start a new one. An id that
            is not recognised starts a new Run rather than failing — a stale id
            is inert, never an error she has to understand.

    Yields:
        Run: The Run to capture Pre-images into.
    """
    db = _connect()
    try:
        if run_id and _run_exists(db, run_id):
            joined = run_id
        else:
            joined = uuid.uuid4().hex
            db.execute(
                "INSERT INTO runs (id, started_at) VALUES (?, ?)",
                (joined, time.time()),
            )
            db.commit()
        run = Run(joined, db)
        try:
            yield run
        finally:
            db.execute(
                "UPDATE runs SET ended_at = ? WHERE id = ?", (time.time(), joined)
            )
            db.commit()
            _prune(db)
    finally:
        db.close()


def _run_exists(db: sqlite3.Connection, run_id: str) -> bool:
    """Say whether a Run id is one we minted.

    Args:
        db: The open undo database.
        run_id: The id to look for.

    Returns:
        bool: Whether it exists.
    """
    return (
        db.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is not None
    )


def _prune(db: sqlite3.Connection) -> None:
    """Drop Runs beyond the retention window.

    The last ten Runs that hold Pre-images, plus anything from the last seven
    days — whichever keeps more. Pre-images are precious but not permanent.

    Args:
        db: The open undo database.
    """
    cutoff = time.time() - KEEP_SECONDS
    # Count only Runs that actually hold something. An empty Run has nothing to
    # retain, so it must not spend one of the ten slots.
    keep = {
        row["id"]
        for row in db.execute(
            "SELECT r.id FROM runs r"
            " WHERE EXISTS (SELECT 1 FROM pre_images p WHERE p.run_id = r.id)"
            " ORDER BY r.started_at DESC LIMIT ?",
            (KEEP_RUNS,),
        )
    }
    # Plus everything recent, which also keeps a Run a caller just opened and
    # has not written into yet — a stale `--run` id must be inert, but one that
    # is seconds old should still be joinable.
    keep |= {
        row["id"]
        for row in db.execute("SELECT id FROM runs WHERE started_at >= ?", (cutoff,))
    }
    doomed = [
        row["id"] for row in db.execute("SELECT id FROM runs") if row["id"] not in keep
    ]
    if not doomed:
        return
    marks = ",".join("?" for _ in doomed)
    db.execute(f"DELETE FROM pre_images WHERE run_id IN ({marks})", doomed)
    db.execute(f"DELETE FROM runs WHERE id IN ({marks})", doomed)
    db.commit()
    log_event("undo_pruned", runs=len(doomed))


def recent_runs(limit: int = KEEP_RUNS) -> list[RunSummary]:
    """Return past Runs, newest first, described by what they moved.

    Args:
        limit: How many to return.

    Returns:
        list[RunSummary]: The Runs that actually moved something. A Run that
            landed nothing is not something she did, so it is not offered.
    """
    db = _connect()
    try:
        summaries: list[RunSummary] = []
        for row in db.execute(
            "SELECT id, ended_at FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ):
            run = Run(row["id"], db)
            changed = run.changed()
            if not changed:
                continue
            summaries.append(
                RunSummary(
                    run_id=row["id"],
                    changed=changed,
                    names=run.landed_names(),
                    ended_at=row["ended_at"],
                )
            )
        return summaries
    finally:
        db.close()


def pre_images_of(run_id: str) -> list[PreImage]:
    """Return the Pre-images of one past Run, newest capture first.

    Args:
        run_id: Which Run.

    Returns:
        list[PreImage]: Its Pre-images, empty when the Run is unknown or has
            aged out of the retention window.
    """
    db = _connect()
    try:
        return Run(run_id, db).pre_images()
    finally:
        db.close()
