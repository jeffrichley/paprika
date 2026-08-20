"""``usda.sqlite3`` — the bundled data, materialised once per machine.

It lands in ``~/.paprika`` rather than beside the installed package on purpose:
the plugin lives in a versioned directory that changes on every upgrade, so a
package-relative index would be rebuilt once per installed version instead of
once per machine.

It is also a different file from the memos in ``nutrition.sqlite3``. This one is
disposable — delete it and it rebuilds from the bundle in a couple of seconds.
The memos are not, and a routine rebuild must not be able to touch them.

Only foods carrying all four nutrients are indexed. A record that cannot answer
energy, protein, carbohydrate and fat cannot answer the question at all, and
half a food is a way to publish a number with a hole in it.
"""

from __future__ import annotations

import csv
import gzip
import re
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import final

from paprika_core import store
from paprika_core.errors import Code, PaprikaError
from paprika_core.nutrition.bundle import (
    FOODS_FILE,
    MANIFEST_FILE,
    NUTRIENTS_FILE,
    PORTIONS_FILE,
)
from paprika_core.nutrition.portions import Portion, PortionKind, parse_portion
from paprika_core.nutrition.tiers import Amounts
from paprika_core.nutrition.units import singular

#: Bumped whenever the meaning of anything in this file changes. It is part of
#: the index's signature, so a change rebuilds every machine's index rather than
#: leaving stale rows behind a matching manifest.
INDEX_SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS foods (
    fdc_id      INTEGER PRIMARY KEY,
    data_type   TEXT NOT NULL,
    description TEXT NOT NULL,
    tokens      TEXT NOT NULL,
    energy      REAL NOT NULL,
    protein     REAL NOT NULL,
    carbs       REAL NOT NULL,
    fat         REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    token  TEXT NOT NULL,
    fdc_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS portions (
    fdc_id    INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    unit      TEXT NOT NULL,
    size      TEXT NOT NULL,
    piece     TEXT NOT NULL,
    qualifier TEXT NOT NULL,
    grams     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tokens ON tokens (token);
CREATE INDEX IF NOT EXISTS ix_portions ON portions (fdc_id);
"""

SIGNATURE = "signature"

#: Energy, most-direct first. Newer Foundation records carry only the Atwater
#: figures, so preferring 1008 and stopping would drop 242 foods on the floor.
_ENERGY_IDS = ("1008", "208", "2048", "958", "2047", "957")
_PROTEIN_IDS = ("1003", "203")
_CARB_IDS = ("1005", "205")
_FAT_IDS = ("1004", "204")

_WORD = re.compile(r"[a-z0-9%]+")

#: Words that carry no identity in a food description or an ingredient line.
STOPWORDS = frozenset(
    {"a", "an", "and", "as", "for", "in", "of", "or", "the", "to", "with", "without"}
)


@final
@dataclass(frozen=True, slots=True)
class FoodRecord:
    """One indexed food.

    Attributes:
        fdc_id: FoodData Central's identifier for it.
        data_type: Which of the three data types it came from.
        description: USDA's own description, verbatim.
        tokens: The description's meaningful words, normalised the same way an
            ingredient line's are.
        amounts: The four nutrients, per 100 g.
    """

    fdc_id: int
    data_type: str
    description: str
    tokens: tuple[str, ...]
    amounts: Amounts


def tokenise(text: str) -> tuple[str, ...]:
    """Reduce a description or an ingredient name to comparable words.

    Args:
        text: The text.

    Returns:
        tuple[str, ...]: Its words, lowercased, singularised, stopwords removed,
            duplicates removed, in order.
    """
    seen: list[str] = []
    for raw in _WORD.findall(text.lower()):
        word = singular(raw)
        if word in STOPWORDS or word in seen:
            continue
        seen.append(word)
    return tuple(seen)


def data_dir() -> Path:
    """Return the directory holding the bundled USDA subset.

    Returns:
        Path: The package's ``data`` directory.
    """
    return Path(__file__).parent / "data"


def bundle_signature() -> str:
    """Return a string identifying exactly which bundle is installed.

    Returns:
        str: The schema version and the manifest, together.

    Raises:
        PaprikaError: ``nutrition_data_missing`` when the bundle is not there.
    """
    manifest = data_dir() / MANIFEST_FILE
    if not manifest.is_file():
        raise PaprikaError(
            Code.NUTRITION_DATA_MISSING,
            "The nutrition data that ships with this plugin is missing, so I "
            "can't work anything out.",
            detail=f"no bundle manifest at {manifest}",
        )
    return f"{INDEX_SCHEMA_VERSION}\n{manifest.read_text(encoding='utf-8')}"


def _bundled_rows(name: str) -> Iterator[dict[str, str]]:
    """Read one gzipped file of the bundle.

    Args:
        name: The file's name.

    Yields:
        dict[str, str]: One row per record.

    Raises:
        PaprikaError: ``nutrition_data_missing`` when the file is not there.
    """
    path = data_dir() / name
    if not path.is_file():
        raise PaprikaError(
            Code.NUTRITION_DATA_MISSING,
            "The nutrition data that ships with this plugin is missing, so I "
            "can't work anything out.",
            detail=f"no bundled {name} at {path}",
        )
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def _amounts_by_food() -> dict[int, Amounts]:
    """Read the bundle's nutrients, resolving energy and dropping partial foods.

    Returns:
        dict[int, Amounts]: Per-100-gram amounts, only for foods carrying all
            four.
    """
    collected: dict[int, dict[str, float]] = {}
    for row in _bundled_rows(NUTRIENTS_FILE):
        try:
            amount = float(row["amount"])
        except ValueError:
            continue
        collected.setdefault(int(row["fdc_id"]), {})[row["nutrient_id"]] = amount

    resolved: dict[int, Amounts] = {}
    for fdc_id, values in collected.items():
        energy = _first(values, _ENERGY_IDS)
        protein = _first(values, _PROTEIN_IDS)
        carbs = _first(values, _CARB_IDS)
        fat = _first(values, _FAT_IDS)
        if None in (energy, protein, carbs, fat):
            continue
        resolved[fdc_id] = Amounts(
            energy_kcal=float(energy or 0.0),
            protein_g=float(protein or 0.0),
            carbohydrate_g=float(carbs or 0.0),
            fat_g=float(fat or 0.0),
        )
    return resolved


def _first(values: dict[str, float], ids: Sequence[str]) -> float | None:
    """Return the first of several nutrient identifiers that is present.

    Args:
        values: The food's nutrients.
        ids: The identifiers, in order of preference.

    Returns:
        float | None: The amount, or ``None`` when none of them is present.
    """
    for identifier in ids:
        if identifier in values:
            return values[identifier]
    return None


def _build(path: Path) -> None:
    """Materialise the bundle into a fresh database at ``path``.

    Args:
        path: Where to write. Anything already there is replaced.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".building")
    partial.unlink(missing_ok=True)
    database = sqlite3.connect(partial)
    try:
        database.executescript(SCHEMA)
        amounts = _amounts_by_food()
        kept: dict[int, str] = {}
        foods: list[tuple[object, ...]] = []
        tokens: list[tuple[str, int]] = []
        for row in _bundled_rows(FOODS_FILE):
            fdc_id = int(row["fdc_id"])
            found = amounts.get(fdc_id)
            if found is None:
                continue
            kept[fdc_id] = row["data_type"]
            words = tokenise(row["description"])
            foods.append(
                (
                    fdc_id,
                    row["data_type"],
                    row["description"],
                    " ".join(words),
                    found.energy_kcal,
                    found.protein_g,
                    found.carbohydrate_g,
                    found.fat_g,
                )
            )
            tokens.extend((word, fdc_id) for word in words)
        database.executemany(
            "INSERT INTO foods (fdc_id, data_type, description, tokens, energy,"
            " protein, carbs, fat) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            foods,
        )
        database.executemany("INSERT INTO tokens (token, fdc_id) VALUES (?, ?)", tokens)

        database.executemany(
            "INSERT INTO portions (fdc_id, kind, unit, size, piece, qualifier,"
            " grams) VALUES (?, ?, ?, ?, ?, ?, ?)",
            _portion_rows(kept),
        )
        database.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (SIGNATURE, bundle_signature()),
        )
        database.commit()
    finally:
        database.close()
    partial.replace(path)


def _portion_rows(kept: dict[int, str]) -> Iterator[tuple[object, ...]]:
    """Read the bundle's portions, each according to the data type that wrote it.

    Args:
        kept: The foods that made it into the index, and their data types.

    Yields:
        tuple[object, ...]: One row per usable portion.
    """
    for row in _bundled_rows(PORTIONS_FILE):
        fdc_id = int(row["fdc_id"])
        if fdc_id not in kept:
            continue
        portion = parse_portion(
            kept[fdc_id],
            row["amount"],
            row["measure_unit"],
            row["portion_description"],
            row["modifier"],
            row["gram_weight"],
        )
        if portion is None:
            continue
        yield (
            fdc_id,
            str(portion.kind),
            portion.unit,
            portion.size,
            portion.piece,
            portion.qualifier,
            portion.grams,
        )


def materialise(path: Path | None = None, *, force: bool = False) -> Path:
    """Build the index if this machine does not already have a current one.

    Args:
        path: Where the index lives. Defaults to the store's own path.
        force: Rebuild even when the signature already matches.

    Returns:
        Path: The index's path, which now holds a current index.
    """
    target = path or store.usda_index_path()
    if not force and target.is_file() and _signature_of(target) == bundle_signature():
        return target
    _build(target)
    return target


def _signature_of(path: Path) -> str | None:
    """Return the signature of an existing index.

    Args:
        path: The index.

    Returns:
        str | None: Its signature, or ``None`` when it has none or cannot be
            read — a damaged index is a thing to rebuild, not to fail on.
    """
    try:
        database = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = database.execute(
            "SELECT value FROM meta WHERE key = ?", (SIGNATURE,)
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        database.close()
    return None if row is None else str(row[0])


@final
class UsdaIndex:
    """The materialised index, opened against one SQLite file.

    Args:
        path: Where the database lives.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row

    def __enter__(self) -> UsdaIndex:
        """Enter the context manager.

        Returns:
            UsdaIndex: This index.
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

    def candidates(self, words: Sequence[str], limit: int = 120) -> list[FoodRecord]:
        """Return records worth considering for a set of ingredient words.

        The head word — the last one, which in English is the noun — must be
        present. Everything else only helps a record rank.

        Args:
            words: The ingredient's normalised words.
            limit: How many records to return.

        Returns:
            list[FoodRecord]: The candidates, most words matched first. Empty
                when nothing carries the head word, which is a refusal rather
                than a reason to widen the search.
        """
        if not words:
            return []
        head = words[-1]
        placeholders = ",".join("?" for _ in words)
        rows = self._db.execute(
            "SELECT f.fdc_id, f.data_type, f.description, f.tokens, f.energy,"
            " f.protein, f.carbs, f.fat, COUNT(*) AS hits"
            " FROM tokens t JOIN foods f ON f.fdc_id = t.fdc_id"
            f" WHERE t.token IN ({placeholders})"
            " GROUP BY f.fdc_id"
            " HAVING SUM(CASE WHEN t.token = ? THEN 1 ELSE 0 END) > 0"
            # The cut has to agree with how the matcher will rank, or the right
            # record is discarded before ranking ever sees it: there are more
            # than 120 foods whose description merely contains the word `egg`.
            " ORDER BY hits DESC, INSTR(' ' || f.tokens, ' ' || ?) ASC,"
            " LENGTH(f.description) ASC"
            " LIMIT ?",
            (*words, head, head, limit),
        ).fetchall()
        return [_record(row) for row in rows]

    def portions(self, fdc_id: int) -> list[Portion]:
        """Return every usable portion on one record.

        Args:
            fdc_id: The record.

        Returns:
            list[Portion]: Its portions. Never ordered by USDA's sequence, so no
                caller can accidentally take the first one.
        """
        rows = self._db.execute(
            "SELECT kind, unit, size, piece, qualifier, grams FROM portions"
            " WHERE fdc_id = ? ORDER BY grams",
            (fdc_id,),
        ).fetchall()
        return [
            Portion(
                kind=PortionKind(row["kind"]),
                unit=row["unit"],
                size=row["size"],
                piece=row["piece"],
                qualifier=row["qualifier"],
                grams=row["grams"],
            )
            for row in rows
        ]

    def borrow(
        self,
        words: Sequence[str],
        kind: PortionKind,
        key: str,
        avoid: frozenset[str],
    ) -> Portion | None:
        """Find the same measure on a different record for the same food.

        The rung of the gram-weight ladder that exists because of Part A's
        central finding: the data type with the best nutrient values has the
        worst portion data. Foundation's `Onions, yellow, raw` has no size
        gradation at all, and only SR Legacy — frozen since 2018 — knows that a
        large onion is 150 g. Joining across them answers the question, and the
        caller must record that it did so by borrowing.

        Which record to borrow from is chosen the way the matcher chooses one —
        the sibling sharing the most of the line's words, then the plainest
        description — and never by which portion weighs least, which would pick
        a spring onion's `large` over a yellow onion's.

        Args:
            words: The ingredient's words, head word last.
            kind: Which sort of portion is wanted.
            key: The unit, size or piece wanted, according to ``kind``.
            avoid: Words a sibling should not carry — the specificity the line
                never asked for. Required rather than defaulted: without it,
                `Egg white sandwich` is a shorter description than `Egg, whole,
                raw, fresh` and would win, and a caller that forgot would get a
                quietly worse answer rather than an error.

        Returns:
            Portion | None: A portion from another record for the same food, or
                ``None``.
        """
        column = {
            PortionKind.MEASURE: "unit",
            PortionKind.SIZE: "size",
            PortionKind.COUNT: "piece",
        }.get(kind)
        if column is None or not words:
            return None
        rows = self._db.execute(
            "SELECT f.fdc_id, f.tokens, p.kind, p.unit, p.size, p.piece,"
            " p.qualifier, p.grams"
            " FROM portions p JOIN foods f ON f.fdc_id = p.fdc_id"
            " WHERE f.fdc_id IN (SELECT fdc_id FROM tokens WHERE token = ?)"
            f" AND p.{column} = ? AND p.kind = ?",
            (words[-1], key, str(kind)),
        ).fetchall()
        if not rows:
            return None
        wanted = set(words)
        head = words[-1]

        def rank(row: sqlite3.Row) -> tuple[int, ...]:
            tokens = row["tokens"].split()
            return (
                len(wanted & set(tokens)),
                # `Bagels, egg` shares a word with `3 large eggs` and is not an
                # egg, so where the head word sits matters here for the same
                # reason it matters in the matcher.
                -tokens.index(head),
                -len(avoid & set(tokens)),
                -len(tokens),
                -int(row["fdc_id"]),
            )

        best = max(rows, key=rank)
        return Portion(
            kind=PortionKind(best["kind"]),
            unit=best["unit"],
            size=best["size"],
            piece=best["piece"],
            qualifier=best["qualifier"],
            grams=best["grams"],
        )

    def count(self) -> int:
        """Return how many foods are indexed.

        Returns:
            int: The count.
        """
        return int(self._db.execute("SELECT COUNT(*) FROM foods").fetchone()[0])


def _record(row: sqlite3.Row) -> FoodRecord:
    """Build a record from an index row.

    Args:
        row: The row.

    Returns:
        FoodRecord: The record.
    """
    return FoodRecord(
        fdc_id=int(row["fdc_id"]),
        data_type=row["data_type"],
        description=row["description"],
        tokens=tuple(row["tokens"].split()),
        amounts=Amounts(
            energy_kcal=row["energy"],
            protein_g=row["protein"],
            carbohydrate_g=row["carbs"],
            fat_g=row["fat"],
        ),
    )


def open_index(path: Path | None = None) -> UsdaIndex:
    """Open the index, materialising it first if this machine has no current one.

    Args:
        path: Where the index lives. Defaults to the store's own path.

    Returns:
        UsdaIndex: The open index.
    """
    return UsdaIndex(materialise(path))
