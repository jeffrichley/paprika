"""The Mirror — our local copy of what Paprika stores.

Never authoritative, never a write buffer, so it is only ever fresh or stale and
never in conflict. It is rebuilt rather than merged.

Every recipe is committed as it arrives. That is what makes a cold sync
resumable: an interrupted download costs the slice that was in flight rather than
the whole run, and no timer is involved in making that true.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from paprika_core.handles import derive_handles

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    uid        TEXT PRIMARY KEY,
    handle     TEXT,
    name       TEXT NOT NULL DEFAULT '',
    rating     INTEGER NOT NULL DEFAULT 0,
    total_time TEXT NOT NULL DEFAULT '',
    categories TEXT NOT NULL DEFAULT '[]',
    trashed    INTEGER NOT NULL DEFAULT 0,
    -- Paprika's opaque change token for this recipe. Not a content digest and
    -- not reproducible here; useful only for equality against what we saw last
    -- time, which is exactly what a refetch diff needs.
    sync_token TEXT NOT NULL DEFAULT '',
    body       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    uid        TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    parent_uid TEXT,
    order_flag INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meals (
    uid        TEXT PRIMARY KEY,
    date       TEXT NOT NULL DEFAULT '',
    meal_type  INTEGER NOT NULL DEFAULT 2,
    recipe_uid TEXT,
    name       TEXT NOT NULL DEFAULT '',
    body       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SYNCED_AT = "synced_at"
CHECKED_AT = "checked_at"
COUNTERS = "counters"


@dataclass(frozen=True)
class MirroredRecipe:
    """One recipe as the Mirror holds it, minus everything the session can't see.

    Attributes:
        handle: How the session names this recipe.
        name: Its title.
        rating: Zero to five; zero means unrated.
        total_time: Free text, exactly as Paprika holds it.
        categories: Category uids, resolved to names at the point of display.
    """

    handle: str
    name: str
    rating: int
    total_time: str
    categories: tuple[str, ...]


@dataclass(frozen=True)
class Meal:
    """One meal on one date in one slot.

    Attributes:
        uid: Its identifier, which stays inside the core.
        date: The day it falls on, as ``YYYY-MM-DD``.
        meal_type: 0 breakfast, 1 lunch, 2 dinner, 3 snack.
        recipe_handle: How the session names the recipe, when it is one of hers.
        name: What it says on the plan — the recipe's title, or free text when
            she planned something that is not a recipe at all.
    """

    uid: str
    date: str
    meal_type: int
    recipe_handle: str | None
    name: str


@dataclass(frozen=True)
class Category:
    """One node of her category tree.

    Attributes:
        uid: The category's identifier, which stays inside the core.
        name: Its name.
        parent_uid: Its parent, or ``None`` for a root.
        order_flag: Her ordering.
    """

    uid: str
    name: str
    parent_uid: str | None
    order_flag: int


class Mirror:
    """The Mirror's storage, opened against one SQLite file.

    Args:
        path: Where the database lives.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()

    def __enter__(self) -> Mirror:
        """Enter the context manager.

        Returns:
            Mirror: This Mirror.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the database."""
        self.close()

    def close(self) -> None:
        """Close the database."""
        self._db.close()

    def put_recipe(self, recipe: dict[str, Any]) -> None:
        """Store one whole recipe, committing immediately.

        The full body is kept verbatim — all thirty-five fields, including the
        seven that are undocumented — because a field we drop here is a field a
        later write cannot echo back.

        Args:
            recipe: The full recipe object as Paprika returned it.
        """
        uid = str(recipe.get("uid", ""))
        if not uid:
            return
        categories = recipe.get("categories") or []
        self._db.execute(
            "INSERT INTO recipes (uid, handle, name, rating, total_time, categories,"
            " trashed, sync_token, body) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(uid) DO UPDATE SET name=excluded.name,"
            " rating=excluded.rating, total_time=excluded.total_time,"
            " categories=excluded.categories, trashed=excluded.trashed,"
            " sync_token=excluded.sync_token, body=excluded.body",
            (
                uid,
                str(recipe.get("name") or ""),
                int(recipe.get("rating") or 0),
                str(recipe.get("total_time") or ""),
                json.dumps(list(categories)),
                # What she called deleting. The recipe is still on the wire and
                # still readable, but it is no longer part of her Library.
                int(bool(recipe.get("in_trash"))),
                str(recipe.get("hash") or ""),
                json.dumps(recipe),
            ),
        )
        self._db.commit()

    def put_meals(self, meals: Iterable[dict[str, Any]]) -> None:
        """Store the Plan as Paprika holds it.

        The whole object is kept, not just the fields we read, because a write
        has to echo back everything it was given.

        Args:
            meals: The meal objects as Paprika returned them.
        """
        rows = [
            (
                str(meal.get("uid", "")),
                str(meal.get("date") or "")[:10],
                int(meal.get("type") or 0),
                meal.get("recipe_uid") or None,
                str(meal.get("name") or ""),
                json.dumps(meal),
            )
            for meal in meals
            if meal.get("uid") and not meal.get("deleted")
        ]
        self._db.execute("DELETE FROM meals")
        self._db.executemany(
            "INSERT OR REPLACE INTO meals (uid, date, meal_type, recipe_uid, name,"
            " body) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._db.commit()

    def meals(self, since: str = "", until: str = "") -> list[Meal]:
        """Return the Plan between two dates, inclusive.

        Args:
            since: The first date, as ``YYYY-MM-DD``. Empty for no lower bound.
            until: The last date, as ``YYYY-MM-DD``. Empty for no upper bound.

        Returns:
            list[Meal]: The meals, by date then slot.
        """
        handles = {
            row["uid"]: row["handle"]
            for row in self._db.execute("SELECT uid, handle FROM recipes")
        }
        rows = self._db.execute(
            "SELECT uid, date, meal_type, recipe_uid, name FROM meals"
            " WHERE (? = '' OR date >= ?) AND (? = '' OR date <= ?)"
            " ORDER BY date, meal_type",
            (since, since, until, until),
        )
        return [
            Meal(
                uid=row["uid"],
                date=row["date"],
                meal_type=row["meal_type"],
                recipe_handle=handles.get(row["recipe_uid"] or ""),
                name=row["name"],
            )
            for row in rows
        ]

    def put_categories(self, categories: Iterable[dict[str, Any]]) -> None:
        """Store the whole category tree.

        Args:
            categories: The category objects as Paprika returned them.
        """
        rows = [
            (
                str(category.get("uid", "")),
                str(category.get("name") or ""),
                category.get("parent_uid") or None,
                int(category.get("order_flag") or 0),
            )
            for category in categories
            if category.get("uid")
        ]
        self._db.executemany(
            "INSERT OR REPLACE INTO categories (uid, name, parent_uid, order_flag)"
            " VALUES (?, ?, ?, ?)",
            rows,
        )
        self._db.commit()

    def assign_handles(self) -> None:
        """Derive a handle for every mirrored recipe.

        Deferred to the end of a sync because collision-checking is a property of
        the whole Library, not of one recipe.
        """
        uids = [row["uid"] for row in self._db.execute("SELECT uid FROM recipes")]
        handles = derive_handles(uids)
        self._db.executemany(
            "UPDATE recipes SET handle = ? WHERE uid = ?",
            [(handle, uid) for uid, handle in handles.items()],
        )
        self._db.commit()

    def recipe_tokens(self) -> dict[str, str]:
        """Return every mirrored recipe's change token.

        Trashed recipes are included: they are still on the wire, so leaving
        them out would make the diff refetch them on every single read.

        Returns:
            dict[str, str]: uid to the token we last saw for it.
        """
        return {
            row["uid"]: row["sync_token"]
            for row in self._db.execute("SELECT uid, sync_token FROM recipes")
        }

    def forget_recipes(self, uids: Iterable[str]) -> int:
        """Drop recipes that have vanished from Paprika.

        Deletion leaves no tombstone — a removed recipe is simply absent from
        the collection — so absence is the only evidence there will ever be.

        Args:
            uids: The uids to drop.

        Returns:
            int: How many rows were dropped.
        """
        rows = [(uid,) for uid in uids]
        if not rows:
            return 0
        cursor = self._db.executemany("DELETE FROM recipes WHERE uid = ?", rows)
        self._db.commit()
        return int(cursor.rowcount)

    def recipes(self) -> list[MirroredRecipe]:
        """Return the whole Library, ordered by name.

        Trashed recipes are mirrored but excluded here: she deleted them, and
        Paprika's own trash is where they live until she empties it.

        Returns:
            list[MirroredRecipe]: Every recipe still in her Library.
        """
        rows = self._db.execute(
            "SELECT handle, name, rating, total_time, categories FROM recipes"
            " WHERE trashed = 0"
            " ORDER BY name COLLATE NOCASE, handle"
        )
        return [
            MirroredRecipe(
                handle=row["handle"] or "",
                name=row["name"],
                rating=row["rating"],
                total_time=row["total_time"],
                categories=tuple(json.loads(row["categories"])),
            )
            for row in rows
        ]

    def uid_for(self, handle: str) -> str | None:
        """Return the identity behind a handle.

        The one place a handle turns back into the mechanic it was derived from,
        and it stays inside the core.

        Args:
            handle: The handle the session holds.

        Returns:
            str | None: The uid, or ``None`` when the handle is unknown.
        """
        row = self._db.execute(
            "SELECT uid FROM recipes WHERE handle = ?", (handle,)
        ).fetchone()
        return str(row["uid"]) if row else None

    def recipe_body(self, handle: str) -> dict[str, Any] | None:
        """Return one whole recipe by handle.

        Args:
            handle: The handle the session holds.

        Returns:
            dict[str, Any] | None: The full object, or ``None`` when unknown.
        """
        row = self._db.execute(
            "SELECT body FROM recipes WHERE handle = ?", (handle,)
        ).fetchone()
        if row is None:
            return None
        body: dict[str, Any] = json.loads(row["body"])
        return body

    def count_recipes(self) -> int:
        """Return how many recipes are in her Library.

        Returns:
            int: The count, trashed recipes excluded.
        """
        row = self._db.execute(
            "SELECT COUNT(*) AS n FROM recipes WHERE trashed = 0"
        ).fetchone()
        return int(row["n"])

    def categories(self) -> list[Category]:
        """Return her whole category tree, flat.

        Returns:
            list[Category]: Every category, ordered by her own ordering.
        """
        rows = self._db.execute(
            "SELECT uid, name, parent_uid, order_flag FROM categories"
            " ORDER BY order_flag, name COLLATE NOCASE"
        )
        return [
            Category(
                uid=row["uid"],
                name=row["name"],
                parent_uid=row["parent_uid"],
                order_flag=row["order_flag"],
            )
            for row in rows
        ]

    def category_names(self) -> dict[str, str]:
        """Return a uid-to-name lookup for the category tree.

        Returns:
            dict[str, str]: Category uid to category name.
        """
        return {category.uid: category.name for category in self.categories()}

    def set_meta(self, key: str, value: Any) -> None:
        """Store one piece of the Mirror's own bookkeeping.

        Args:
            key: The key.
            value: Anything JSON can hold.
        """
        self._db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
        self._db.commit()

    def get_meta(self, key: str) -> Any:
        """Read one piece of the Mirror's own bookkeeping.

        Args:
            key: The key.

        Returns:
            Any: The stored value, or ``None``.
        """
        row = self._db.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def mark_synced(self, counters: Sequence[tuple[str, int]] | dict[str, int]) -> None:
        """Record that the Mirror now matches what Paprika held.

        Args:
            counters: Paprika's change counters at the moment of the sync. Kept so
                a later read can establish freshness by asking rather than by a
                clock.
        """
        self.set_meta(COUNTERS, dict(counters))
        self.set_meta(SYNCED_AT, time.time())

    def counters(self) -> dict[str, int]:
        """Return Paprika's change counters as they stood at the last check.

        Returns:
            dict[str, int]: The stored counters, empty when there are none.
        """
        stored = self.get_meta(COUNTERS)
        return dict(stored) if isinstance(stored, dict) else {}

    def mark_checked(self) -> None:
        """Record that Paprika was just asked whether anything had changed."""
        self.set_meta(CHECKED_AT, time.time())

    def mark_stale(self) -> None:
        """Forget that freshness was recently established.

        Called after we ourselves change something in Paprika. The stamp exists
        to collapse a burst of *reads* into one question; it must never let a
        read serve a Plan that our own write just made out of date.
        """
        self.set_meta(CHECKED_AT, 0.0)

    def checked_within(self, seconds: float) -> bool:
        """Say whether freshness was established recently enough to reuse.

        Args:
            seconds: How long an answer stays good for.

        Returns:
            bool: Whether the last check is still inside that window.
        """
        stamp = self.get_meta(CHECKED_AT)
        if not isinstance(stamp, (int, float)):
            return False
        return (time.time() - float(stamp)) < seconds

    def age_seconds(self) -> float | None:
        """Return how long ago the Mirror was last filled.

        Returns:
            float | None: Seconds since the last sync, or ``None`` if never.
        """
        stamp = self.get_meta(SYNCED_AT)
        if not isinstance(stamp, (int, float)):
            return None
        return max(0.0, time.time() - float(stamp))
