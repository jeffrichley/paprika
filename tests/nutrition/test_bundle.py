"""Projecting USDA's bulk CSVs into the subset this package ships.

Run at development time rather than in a session, but its output is what every
number downstream is made of, so its selection rules are worth pinning: which
data types survive, which nutrient identifiers survive in *both* of the two
schemes FoodData Central uses, and that nothing is interpreted on the way
through.
"""

from __future__ import annotations

import csv
import gzip
from collections.abc import Sequence
from pathlib import Path

from paprika_core.nutrition.bundle import (
    FOODS_FILE,
    MANIFEST_FILE,
    NUTRIENTS_FILE,
    PORTIONS_FILE,
    build_bundle,
)
from paprika_core.nutrition.materialise import data_dir

FOODS = [
    ("fdc_id", "data_type", "description", "food_category_id", "publication_date"),
    ("170000", "sr_legacy_food", "Onions, raw", "11", "2019-04-01"),
    ("2709795", "survey_fndds_food", "Onions, raw", "6", "2022-10-28"),
    ("999999", "branded_food", "YELLOW ONION", "9", "2024-01-01"),
]
NUTRIENTS = [
    ("id", "fdc_id", "nutrient_id", "amount"),
    ("1", "170000", "1008", "40.0"),
    ("2", "170000", "1003", "1.1"),
    # FNDDS references nutrient_nbr in the same column. Dropping this row is how
    # a whole data type silently goes missing.
    ("3", "2709795", "208", "38.0"),
    ("4", "170000", "1093", "4.0"),
    ("5", "999999", "1008", "40.0"),
]
PORTIONS = [
    (
        "id",
        "fdc_id",
        "seq_num",
        "amount",
        "measure_unit_id",
        "portion_description",
        "modifier",
        "gram_weight",
    ),
    ("1", "170000", "4", "1", "9999", "", "large", "150"),
    ("2", "2709795", "2", "", "9999", "1 cup", "10205", "160.0"),
    ("3", "999999", "1", "1", "1000", "", "", "85"),
]
MEASURE_UNITS = [("id", "name"), ("1000", "cup"), ("9999", "undetermined")]


def _write(path: Path, rows: Sequence[Sequence[str]]) -> None:
    """Write one source CSV.

    Args:
        path: Where to write.
        rows: Its rows, header first.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


def _read(path: Path) -> list[dict[str, str]]:
    """Read one bundled file back.

    Args:
        path: The gzipped CSV.

    Returns:
        list[dict[str, str]]: Its rows.
    """
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def a_release(tmp_path: Path) -> Path:
    """Build a directory shaped like an extracted FoodData Central download.

    Args:
        tmp_path: pytest's per-test directory.

    Returns:
        Path: The directory.
    """
    source = tmp_path / "release"
    source.mkdir()
    _write(source / "food.csv", FOODS)
    _write(source / "food_nutrient.csv", NUTRIENTS)
    _write(source / "food_portion.csv", PORTIONS)
    _write(source / "measure_unit.csv", MEASURE_UNITS)
    return source


class TestWhatSurvivesTheProjection:
    def test_branded_is_not_representable(self, tmp_path: Path) -> None:
        """97% of the database, and its records outrank real food."""
        build_bundle([a_release(tmp_path)], tmp_path / "out")

        foods = _read(tmp_path / "out" / FOODS_FILE)

        assert {row["data_type"] for row in foods} == {
            "sr_legacy_food",
            "survey_fndds_food",
        }

    def test_both_nutrient_numbering_schemes_are_kept(self, tmp_path: Path) -> None:
        build_bundle([a_release(tmp_path)], tmp_path / "out")

        kept = {row["nutrient_id"] for row in _read(tmp_path / "out" / NUTRIENTS_FILE)}

        assert kept == {"1008", "1003", "208"}

    def test_a_micronutrient_is_not_even_carried(self, tmp_path: Path) -> None:
        """Nutrient 1093 is sodium. It is refused here, not later."""
        build_bundle([a_release(tmp_path)], tmp_path / "out")

        kept = {row["nutrient_id"] for row in _read(tmp_path / "out" / NUTRIENTS_FILE)}

        assert "1093" not in kept

    def test_portions_follow_their_foods(self, tmp_path: Path) -> None:
        build_bundle([a_release(tmp_path)], tmp_path / "out")

        portions = _read(tmp_path / "out" / PORTIONS_FILE)

        assert {row["fdc_id"] for row in portions} == {"170000", "2709795"}

    def test_the_unit_id_is_resolved_but_nothing_is_interpreted(
        self, tmp_path: Path
    ) -> None:
        """A join, not a judgement. The prose stays prose."""
        build_bundle([a_release(tmp_path)], tmp_path / "out")

        portions = {
            row["fdc_id"]: row for row in _read(tmp_path / "out" / PORTIONS_FILE)
        }

        assert portions["170000"]["modifier"] == "large"
        assert portions["2709795"]["portion_description"] == "1 cup"

    def test_a_release_without_portions_is_not_a_failure(self, tmp_path: Path) -> None:
        source = a_release(tmp_path)
        (source / "food_portion.csv").unlink()
        (source / "measure_unit.csv").unlink()

        manifest = build_bundle([source], tmp_path / "out")

        assert (PORTIONS_FILE, 0) in manifest


class TestTheBundleThatIsActuallyShipped:
    def test_it_names_its_own_sources(self) -> None:
        rows = list(csv.DictReader((data_dir() / MANIFEST_FILE).open(encoding="utf-8")))
        items = [row["item"] for row in rows]

        assert any("sr_legacy" in item for item in items)
        assert any("foundation" in item for item in items)
        assert any("survey" in item for item in items)

    def test_it_carries_usdas_requested_citation(self) -> None:
        citation = (data_dir() / "CITATION.txt").read_text(encoding="utf-8")

        assert "FoodData Central" in citation
        assert "CC0" in citation

    def test_it_is_small_enough_to_ship(self) -> None:
        """The spec budgeted about 14 MB. Three data types compress to under one."""
        total = sum(path.stat().st_size for path in data_dir().glob("*.csv.gz"))

        assert total < 2_000_000
