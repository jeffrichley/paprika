"""Building ``usda.sqlite3`` out of the bundled subset, once per machine.

It lands in ``~/.paprika`` rather than beside the installed package on purpose:
the plugin lives in a versioned directory that changes on every upgrade, so a
package-relative index would be rebuilt once per installed version instead of
once per machine.

It is also a different file from the memos in ``nutrition.sqlite3``. This one is
disposable — delete it and it rebuilds from the bundle in about a second. The
memos are not, and a routine rebuild must not be able to touch them.

Only foods carrying all four nutrients are indexed. A record that cannot answer
energy, protein, carbohydrate and fat cannot answer the question at all, and
half a food is a way to publish a number with a hole in it.
"""

from __future__ import annotations

import csv
import gzip
import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path

from paprika_core import store
from paprika_core.errors import Code, PaprikaError
from paprika_core.nutrition.bundle import (
    FOODS_FILE,
    MANIFEST_FILE,
    NUTRIENTS_FILE,
    PORTIONS_FILE,
)
from paprika_core.nutrition.portions import parse_portion
from paprika_core.nutrition.tiers import Amounts
from paprika_core.nutrition.tokens import tokenise

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
