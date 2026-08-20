"""Turning USDA's bulk CSVs into the subset this package ships.

Run at development time, never in a session. It reads directories extracted from
the FoodData Central bulk CSV downloads and writes a small gzipped subset into
``paprika_core/nutrition/data``, which :mod:`paprika_core.nutrition.index`
materialises into ``usda.sqlite3``.

Three deliberate properties:

* **The subset is a faithful projection, not an interpretation.** It drops
  columns and rows, and it resolves ``measure_unit_id`` to its name because that
  is a join rather than a judgement. Everything else — which energy nutrient to
  prefer, what USDA's portion prose means, which records to deprioritise — is
  code in the modules that read it, so a fix does not need a data rebuild.
* **Branded is not downloaded and is not representable here.** It is 97% of the
  database, its top hits outrank real food, and it would be 428 MB.
* **The bundle names its own sources.** The manifest carries each dataset's
  release and row counts, and the index refuses to serve data built from a
  manifest it does not recognise.

The data are US Government works released as CC0 1.0 Universal. USDA requests,
but does not require, the citation carried in ``data/CITATION.txt``.
"""

from __future__ import annotations

import csv
import gzip
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

#: The data types worth having. FNDDS is ten times thinner on raw commodities
#: than SR Legacy, and Foundation is 394 foods with no portion record on most of
#: them — so all three are needed and none of them is sufficient.
KEPT_DATA_TYPES = frozenset({"sr_legacy_food", "survey_fndds_food", "foundation_food"})

#: Nutrient identifiers worth keeping, in both of the two schemes FoodData
#: Central actually uses. Foundation and SR Legacy reference ``nutrient.id``
#: (1008, 1003…); the Survey/FNDDS download references ``nutrient.nutrient_nbr``
#: (208, 203…) in the same column. A parser that assumes one scheme silently
#: keeps nothing from the other, which is how a whole data type goes missing.
KEPT_NUTRIENT_IDS = frozenset(
    {
        "1008",  # Energy, kcal
        "2047",  # Energy (Atwater General Factors)
        "2048",  # Energy (Atwater Specific Factors)
        "1003",  # Protein
        "1004",  # Total lipid (fat)
        "1005",  # Carbohydrate, by difference
        "208",  # Energy, by nutrient_nbr
        "957",  # Energy (Atwater General Factors), by nutrient_nbr
        "958",  # Energy (Atwater Specific Factors), by nutrient_nbr
        "203",  # Protein, by nutrient_nbr
        "204",  # Total lipid (fat), by nutrient_nbr
        "205",  # Carbohydrate, by difference, by nutrient_nbr
    }
)

FOODS_FILE = "foods.csv.gz"
NUTRIENTS_FILE = "food_nutrient.csv.gz"
PORTIONS_FILE = "food_portion.csv.gz"
MANIFEST_FILE = "manifest.csv"

FOOD_COLUMNS = ("fdc_id", "data_type", "description")
NUTRIENT_COLUMNS = ("fdc_id", "nutrient_id", "amount")
PORTION_COLUMNS = (
    "fdc_id",
    "seq_num",
    "amount",
    "measure_unit",
    "portion_description",
    "modifier",
    "gram_weight",
)


def _rows(path: Path) -> Iterator[dict[str, str]]:
    """Read one FoodData Central CSV.

    Args:
        path: The file to read.

    Yields:
        dict[str, str]: One row per record.
    """
    with path.open(newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle)


def _write(path: Path, columns: Sequence[str], rows: Iterable[Sequence[str]]) -> int:
    """Write one gzipped CSV.

    Args:
        path: Where to write.
        columns: The header.
        rows: The rows.

    Returns:
        int: How many rows were written.
    """
    written = 0
    with gzip.open(path, "wt", newline="", encoding="utf-8", compresslevel=9) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
            written += 1
    return written


def _measure_units(source: Path) -> dict[str, str]:
    """Read one release's measure-unit lookup.

    Args:
        source: An extracted FoodData Central CSV directory.

    Returns:
        dict[str, str]: Unit id to unit name.
    """
    path = source / "measure_unit.csv"
    if not path.is_file():
        return {}
    return {row["id"]: row["name"] for row in _rows(path)}


def _foods(sources: Sequence[Path]) -> list[tuple[str, ...]]:
    """Collect the foods worth keeping.

    Args:
        sources: Extracted FoodData Central CSV directories.

    Returns:
        list[tuple[str, ...]]: One row per food, ordered by identifier.
    """
    foods = [
        (row["fdc_id"], row["data_type"], row["description"])
        for source in sources
        for row in _rows(source / "food.csv")
        if row["data_type"] in KEPT_DATA_TYPES
    ]
    return sorted(foods, key=lambda row: int(row[0]))


def _nutrients(sources: Sequence[Path], kept: set[str]) -> list[tuple[str, ...]]:
    """Collect the four nutrients for the foods worth keeping.

    Args:
        sources: Extracted FoodData Central CSV directories.
        kept: The foods that survived.

    Returns:
        list[tuple[str, ...]]: One row per nutrient.
    """
    nutrients = [
        (row["fdc_id"], row["nutrient_id"], row["amount"])
        for source in sources
        for row in _rows(source / "food_nutrient.csv")
        if row["fdc_id"] in kept and row["nutrient_id"] in KEPT_NUTRIENT_IDS
    ]
    return sorted(nutrients, key=lambda row: (int(row[0]), row[1]))


def _portions(sources: Sequence[Path], kept: set[str]) -> list[tuple[str, ...]]:
    """Collect the portions for the foods worth keeping.

    Args:
        sources: Extracted FoodData Central CSV directories.
        kept: The foods that survived.

    Returns:
        list[tuple[str, ...]]: One row per portion, its unit id resolved to a
            name and everything else verbatim.
    """
    portions: list[tuple[str, ...]] = []
    for source in sources:
        path = source / "food_portion.csv"
        if not path.is_file():
            continue
        units = _measure_units(source)
        portions.extend(
            (
                row["fdc_id"],
                row["seq_num"],
                row["amount"],
                units.get(row["measure_unit_id"], ""),
                row["portion_description"],
                row["modifier"],
                row["gram_weight"],
            )
            for row in _rows(path)
            if row["fdc_id"] in kept
        )
    return sorted(portions, key=lambda row: (int(row[0]), row[1]))


def build_bundle(sources: Sequence[Path], destination: Path) -> list[tuple[str, int]]:
    """Build the shipped subset from extracted bulk CSV directories.

    Args:
        sources: Extracted FoodData Central CSV directories, each holding
            ``food.csv``, ``food_nutrient.csv`` and usually ``food_portion.csv``.
        destination: The directory to write the bundle into.

    Returns:
        list[tuple[str, int]]: The manifest — each source directory's name and
            each written file's row count, in the order they were produced.
    """
    destination.mkdir(parents=True, exist_ok=True)
    foods = _foods(sources)
    kept = {row[0] for row in foods}
    food_rows = _write(destination / FOODS_FILE, FOOD_COLUMNS, foods)
    nutrient_rows = _write(
        destination / NUTRIENTS_FILE, NUTRIENT_COLUMNS, _nutrients(sources, kept)
    )
    portion_rows = _write(
        destination / PORTIONS_FILE, PORTION_COLUMNS, _portions(sources, kept)
    )

    manifest = [(source.name, 0) for source in sources] + [
        (FOODS_FILE, food_rows),
        (NUTRIENTS_FILE, nutrient_rows),
        (PORTIONS_FILE, portion_rows),
    ]
    with (destination / MANIFEST_FILE).open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        # A newline the same on every platform, because the manifest is read back
        # as text and its exact bytes are part of the index signature.
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("item", "rows"))
        writer.writerows(manifest)
    return manifest
