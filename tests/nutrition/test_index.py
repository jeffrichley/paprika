"""The materialised index — built once per machine, and rebuildable at will."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from paprika_core import store
from paprika_core.errors import Code, PaprikaError
from paprika_core.nutrition import ALLOWED_DATA_TYPES
from paprika_core.nutrition.index import (
    UsdaIndex,
    bundle_signature,
    data_dir,
    materialise,
    open_index,
    tokenise,
)
from paprika_core.nutrition.matching import SIGNIFICANT_QUALIFIERS
from paprika_core.nutrition.portions import PortionKind

#: SR Legacy `Onions, raw` and FNDDS `Onions, raw`, both verified in the doc.
SR_ONION = 170000
FNDDS_ONION = 2709795


class TestItIsBuiltOncePerMachine:
    def test_it_lands_in_the_store_rather_than_beside_the_package(self) -> None:
        """The plugin's own directory changes on upgrade; the store does not."""
        assert store.usda_index_path() == store.home() / "usda.sqlite3"
        assert not str(store.usda_index_path()).startswith(str(data_dir()))

    def test_a_second_call_does_not_rebuild(self, paprika_home: Path) -> None:
        first = materialise()
        assert first.parent == paprika_home
        stamp = first.stat().st_mtime_ns

        assert materialise().stat().st_mtime_ns == stamp

    def test_a_bundle_it_does_not_recognise_forces_a_rebuild(
        self, paprika_home: Path
    ) -> None:
        path = materialise()
        assert path.parent == paprika_home
        database = sqlite3.connect(path)
        database.execute("UPDATE meta SET value = 'from some other release'")
        database.commit()
        database.close()

        materialise()

        assert _signature(path) == bundle_signature()

    def test_a_damaged_index_is_rebuilt_rather_than_raised_over(
        self, paprika_home: Path
    ) -> None:
        path = store.usda_index_path()
        assert path.parent == paprika_home
        path.write_text("this is not a database", encoding="utf-8")

        materialise()

        assert _signature(path) == bundle_signature()

    def test_it_is_a_different_file_from_the_memos(self) -> None:
        """A routine index rebuild must not be able to touch the memos."""
        assert store.usda_index_path() != store.memo_path()

    def test_a_missing_bundle_is_a_failure_she_can_read(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "paprika_core.nutrition.index.data_dir", lambda: tmp_path / "gone"
        )

        with pytest.raises(PaprikaError) as caught:
            bundle_signature()

        assert caught.value.code is Code.NUTRITION_DATA_MISSING
        assert "sqlite" not in caught.value.message.lower()


class TestWhatGetsIndexed:
    def test_only_the_three_data_types_we_trust(self, index: UsdaIndex) -> None:
        """Branded is 97% of FoodData Central and is not downloaded at all."""
        rows = index._db.execute("SELECT DISTINCT data_type FROM foods")  # noqa: SLF001

        assert {row["data_type"] for row in rows} == set(ALLOWED_DATA_TYPES)

    def test_every_indexed_food_can_answer_all_four_nutrients(
        self, index: UsdaIndex
    ) -> None:
        """Half a food is a way to publish a number with a hole in it."""
        rows = index._db.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS n FROM foods WHERE energy IS NULL OR protein IS NULL"
            " OR carbs IS NULL OR fat IS NULL"
        ).fetchone()

        assert rows["n"] == 0

    def test_energy_falls_back_to_the_atwater_figures(self, index: UsdaIndex) -> None:
        """Newer Foundation records carry no nutrient 1008 at all."""
        rows = index._db.execute(  # noqa: SLF001
            "SELECT COUNT(*) AS n FROM foods WHERE data_type = 'foundation_food'"
        ).fetchone()

        assert rows["n"] > 300

    def test_it_holds_the_whole_of_all_three_releases(self, index: UsdaIndex) -> None:
        assert index.count() > 13000


class TestSearching:
    def test_the_head_word_is_required(self, index: UsdaIndex) -> None:
        assert index.candidates(("onion",))
        assert index.candidates(("frobnicated", "wibble")) == []

    def test_nothing_at_all_finds_nothing(self, index: UsdaIndex) -> None:
        assert index.candidates(()) == []

    def test_a_record_carries_its_own_words(self, index: UsdaIndex) -> None:
        found = [r for r in index.candidates(("onion",)) if r.fdc_id == SR_ONION]

        assert found and found[0].tokens == tokenise(found[0].description)


class TestPortions:
    def test_usdas_own_sequence_is_not_preserved(self, index: UsdaIndex) -> None:
        """Nothing may take `foodPortions[0]`, so nothing is offered it."""
        portions = index.portions(FNDDS_ONION)
        weights = [portion.grams for portion in portions]

        assert weights == sorted(weights)

    def test_the_sizes_usda_actually_records(self, index: UsdaIndex) -> None:
        sizes = {
            portion.size: portion.grams
            for portion in index.portions(SR_ONION)
            if portion.kind is PortionKind.SIZE
        }

        assert sizes == {"small": 70.0, "medium": 110.0, "large": 150.0}

    def test_the_same_cup_two_ways(self, index: UsdaIndex) -> None:
        """39% apart, for the same food, in USDA's own table."""
        cups = {
            portion.qualifier: portion.grams
            for portion in index.portions(SR_ONION)
            if portion.unit == "cup"
        }

        assert cups == {"chopped": 160.0, "sliced": 115.0}

    def test_quantity_not_specified_survives_as_itself(self, index: UsdaIndex) -> None:
        kinds = {portion.kind for portion in index.portions(FNDDS_ONION)}

        assert PortionKind.UNSPECIFIED in kinds


class TestBorrowingAPortionFromASiblingRecord:
    def test_it_answers_what_the_matched_record_cannot(self, index: UsdaIndex) -> None:
        """Foundation's yellow onion has no size gradation; SR Legacy's does."""
        borrowed = index.borrow(
            ("yellow", "onion"), PortionKind.SIZE, "large", frozenset()
        )

        assert borrowed is not None
        assert borrowed.grams == 150.0

    def test_it_does_not_borrow_from_a_food_that_merely_mentions_the_word(
        self, index: UsdaIndex
    ) -> None:
        """`Bagels, egg` shares a word with `3 large eggs` and is not an egg."""
        borrowed = index.borrow(
            ("egg",), PortionKind.SIZE, "large", SIGNIFICANT_QUALIFIERS
        )

        assert borrowed is not None
        assert borrowed.grams == 50.0

    def test_there_is_nothing_to_borrow_for_a_measure_nobody_records(
        self, index: UsdaIndex
    ) -> None:
        assert (
            index.borrow(("onion",), PortionKind.MEASURE, "furlong", frozenset())
            is None
        )

    def test_it_refuses_a_kind_that_has_no_column(self, index: UsdaIndex) -> None:
        assert (
            index.borrow(("onion",), PortionKind.UNSPECIFIED, "", frozenset()) is None
        )

    def test_it_refuses_when_there_are_no_words(self, index: UsdaIndex) -> None:
        assert index.borrow((), PortionKind.SIZE, "large", frozenset()) is None


def test_opening_the_index_materialises_it_first(paprika_home: Path) -> None:
    assert not store.usda_index_path().exists()

    with open_index() as index:
        assert index.count() > 0


def _signature(path: Path) -> str:
    """Read an index's stored signature.

    Args:
        path: The index.

    Returns:
        str: The signature.
    """
    database = sqlite3.connect(path)
    try:
        row = database.execute(
            "SELECT value FROM meta WHERE key = 'signature'"
        ).fetchone()
    finally:
        database.close()
    return str(row[0])
