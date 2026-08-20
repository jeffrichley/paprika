"""Memos — keyed on the ingredient line, and never a number without its tier."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from paprika_core.nutrition.memo import Memos, memo_key
from paprika_core.nutrition.tiers import (
    Amounts,
    Evidence,
    GramsBasis,
    Provenance,
    Quantified,
    Tier,
    Unquantified,
)

SIGNATURE = "1\nsome manifest"
ONION = Amounts(energy_kcal=40.0, protein_g=1.1, carbohydrate_g=9.3, fat_g=0.1)


def a_number() -> Quantified:
    """Build a memo-able number.

    Returns:
        Quantified: A measured value.
    """
    return Quantified(
        ONION,
        Provenance(
            Evidence(
                grams_basis=GramsBasis.STATED_MASS,
                fdc_id=170000,
                data_type="sr_legacy_food",
                matched_description="Onions, raw",
                dropped_descriptors=("yellow",),
            )
        ),
    )


class TestItIsKeyedOnTheLineAndNotOnTheRecipe:
    def test_two_recipes_saying_the_same_thing_are_one_question(
        self, memos: Memos
    ) -> None:
        memos.remember("2 tbsp Olive Oil", a_number(), SIGNATURE)

        assert memos.recall("  2  tbsp   olive oil ", SIGNATURE) is not None
        assert memos.count() == 1

    def test_the_key_is_the_line_itself(self) -> None:
        assert memo_key("  2 TBSP  Olive Oil ") == "2 tbsp olive oil"

    def test_nothing_remembered_is_nothing_recalled(self, memos: Memos) -> None:
        assert memos.recall("2 tbsp olive oil", SIGNATURE) is None


class TestWhatAMemoHolds:
    def test_the_tier_is_stored_beside_the_number(self, memos: Memos) -> None:
        memos.remember("1 onion", a_number(), SIGNATURE)

        with sqlite3.connect(memos.path) as database:
            row = database.execute("SELECT tier FROM memos").fetchone()
        database.close()

        assert row[0] == Tier.DERIVED.name

    def test_the_structural_evidence_comes_back_with_it(self, memos: Memos) -> None:
        memos.remember("1 yellow onion", a_number(), SIGNATURE)

        recalled = memos.recall("1 yellow onion", SIGNATURE)

        assert recalled is not None
        assert recalled.provenance.evidence.dropped_descriptors == ("yellow",)
        assert recalled.provenance.evidence.fdc_id == 170000
        assert recalled.provenance.notes != ()

    def test_a_refusal_is_remembered_too(self, memos: Memos) -> None:
        """Working out that there is no answer is as expensive as working one out."""
        refusal = Unquantified(
            Provenance(Evidence(grams_basis=GramsBasis.NONE, fdc_id=None)),
            reason="nothing in the USDA data matches this",
            line="1 lb meat of your choice",
            quantity_stated=True,
        )
        memos.remember("1 lb meat of your choice", refusal, SIGNATURE)

        recalled = memos.recall("1 lb meat of your choice", SIGNATURE)

        assert isinstance(recalled, Unquantified)
        assert recalled.quantity_stated is True

    def test_the_amounts_survive_the_round_trip(self, memos: Memos) -> None:
        memos.remember("1 onion", a_number(), SIGNATURE)

        recalled = memos.recall("1 onion", SIGNATURE)

        assert isinstance(recalled, Quantified)
        assert recalled.amounts == ONION


class TestWhenAMemoStopsBeingAnAnswer:
    def test_a_different_index_is_a_miss(self, memos: Memos) -> None:
        memos.remember("1 onion", a_number(), SIGNATURE)

        assert memos.recall("1 onion", "2\na different manifest") is None

    def test_a_tier_the_current_rules_would_not_give_is_a_miss(
        self, memos: Memos
    ) -> None:
        """The rules changed since it was written, so it is not an answer."""
        memos.remember("1 onion", a_number(), SIGNATURE)
        database = sqlite3.connect(memos.path)
        database.execute("UPDATE memos SET tier = 'MEASURED'")
        database.commit()
        database.close()

        assert memos.recall("1 onion", SIGNATURE) is None

    def test_an_unreadable_payload_is_a_miss_rather_than_a_crash(
        self, memos: Memos
    ) -> None:
        memos.remember("1 onion", a_number(), SIGNATURE)
        database = sqlite3.connect(memos.path)
        database.execute("UPDATE memos SET payload = ?", (json.dumps({"junk": 1}),))
        database.commit()
        database.close()

        assert memos.recall("1 onion", SIGNATURE) is None


def test_it_lives_in_its_own_file(tmp_path: Path, memos: Memos) -> None:
    """A routine index rebuild must not be able to reach these."""
    assert memos.path.name == "nutrition.sqlite3"
    assert memos.path.exists()
