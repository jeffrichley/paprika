"""Provenance and Tier — the part of this feature that is not about accuracy.

The rules under test come from ``docs/research/usda-nutrition-matching.md``:
a Tier is derived from structural evidence only, a dropped descriptor is an
automatic demotion, and a total inherits the Provenance of its worst ingredient.
"""

from __future__ import annotations

import dataclasses

import pytest

from paprika_core.errors import Code, PaprikaError
from paprika_core.nutrition import (
    Amounts,
    Evidence,
    GramsBasis,
    Provenance,
    Quantified,
    Tier,
    Unquantified,
    total,
)

ONION = Amounts(energy_kcal=40.0, protein_g=1.1, carbohydrate_g=9.3, fat_g=0.1)


def clean(**overrides: object) -> Evidence:
    """Build the evidence of an ingredient that earned everything it got.

    Args:
        **overrides: Fields to change from the clean case.

    Returns:
        Evidence: A fully-supported match.
    """
    fields: dict[str, object] = {
        "grams_basis": GramsBasis.STATED_MASS,
        "fdc_id": 170000,
        "data_type": "sr_legacy_food",
        "matched_description": "Onions, raw",
    }
    fields.update(overrides)
    return Evidence(**fields)  # type: ignore[arg-type]


def test_a_stated_mass_and_a_clean_match_is_the_only_way_to_reach_measured() -> None:
    assert Provenance(clean()).tier is Tier.MEASURED


def test_a_unit_that_matched_a_real_portion_also_reaches_measured() -> None:
    """Tier A wants an exact ``foodPortion`` unit match, not a plausible one."""
    assert Provenance(clean(grams_basis=GramsBasis.PORTION_EXACT)).tier is Tier.MEASURED


def test_grams_from_a_size_word_can_only_be_derived() -> None:
    """USDA's own table: small 70 g, medium 110 g, large 150 g."""
    assert Provenance(clean(grams_basis=GramsBasis.PORTION_SIZE)).tier is Tier.DERIVED


def test_a_converted_volume_can_only_be_derived() -> None:
    assert (
        Provenance(clean(grams_basis=GramsBasis.PORTION_CONVERTED)).tier is Tier.DERIVED
    )


def test_a_portion_borrowed_from_another_record_can_only_be_estimated() -> None:
    assert (
        Provenance(clean(grams_basis=GramsBasis.PORTION_SIBLING)).tier is Tier.ESTIMATED
    )


def test_a_dropped_descriptor_demotes_however_good_the_rest_was() -> None:
    """`yellow onions` matched to `Onions, raw` dropped a word we were given."""
    provenance = Provenance(clean(dropped_descriptors=("yellow",)))

    assert provenance.tier is Tier.DERIVED
    assert any("yellow" in note for note in provenance.notes)


def test_a_qualifier_we_never_asked_for_demotes() -> None:
    """`butter` -> `Butter, stick, unsalted` at confidence 1.0 is the case in point."""
    provenance = Provenance(
        clean(
            matched_description="Butter, stick, unsalted",
            unrequested_qualifiers=("unsalted",),
        )
    )

    assert provenance.tier is Tier.DERIVED
    assert any("unsalted" in note for note in provenance.notes)


def test_two_demotions_stack() -> None:
    assert (
        Provenance(
            clean(dropped_descriptors=("yellow",), unrequested_qualifiers=("iodized",))
        ).tier
        is Tier.ESTIMATED
    )


def test_a_word_we_could_not_account_for_demotes() -> None:
    """ "plus more for greasing" is information, and dropping it silently is the bug."""
    assert Provenance(clean(unaccounted_words=("greasing",))).tier is Tier.DERIVED


def test_a_quantity_not_specified_portion_demotes() -> None:
    """FNDDS code 90000 is 15 g where the whole onion is 148 g."""
    assert (
        Provenance(
            clean(grams_basis=GramsBasis.PORTION_SIZE, quantity_not_specified=True)
        ).tier
        is Tier.ESTIMATED
    )


def test_demotion_never_reaches_unquantified() -> None:
    """A number that exists is at worst an estimate; Tier D means no number."""
    provenance = Provenance(
        clean(
            grams_basis=GramsBasis.PORTION_SIBLING,
            dropped_descriptors=("smoked",),
            unrequested_qualifiers=("canned",),
            unaccounted_words=("drained",),
            quantity_not_specified=True,
        )
    )

    assert provenance.tier is Tier.ESTIMATED


def test_no_grams_means_no_number() -> None:
    assert Provenance(clean(grams_basis=GramsBasis.NONE)).tier is Tier.UNQUANTIFIED


def test_no_matched_record_means_no_number() -> None:
    assert (
        Provenance(clean(fdc_id=None, matched_description=None)).tier
        is Tier.UNQUANTIFIED
    )


def test_a_data_type_we_do_not_allow_can_never_be_better_than_estimated() -> None:
    """Branded is 97% of the database and outranks real food; it is never a match."""
    assert Provenance(clean(data_type="branded_food")).tier is Tier.ESTIMATED


def test_an_inherited_tier_can_lower_a_provenance_but_never_raise_it() -> None:
    earned = clean()

    assert Provenance(earned, inherited=Tier.ESTIMATED).tier is Tier.ESTIMATED
    assert Provenance(earned, inherited=Tier.MEASURED).tier is Tier.MEASURED
    assert (
        Provenance(
            clean(grams_basis=GramsBasis.PORTION_SIZE), inherited=Tier.MEASURED
        ).tier
        is Tier.DERIVED
    )


def test_a_tier_cannot_be_asserted_by_hand() -> None:
    """The tier is derived, so there is no field to set it with."""
    names = {field.name for field in dataclasses.fields(Provenance)}

    assert "tier" not in names


class TestANumberCannotExistWithoutItsProvenance:
    def test_a_quantified_value_will_not_be_built_without_one(self) -> None:
        with pytest.raises(TypeError):
            Quantified(ONION)  # type: ignore[call-arg]

    def test_a_quantified_value_refuses_an_unquantified_provenance(self) -> None:
        with pytest.raises(ValueError, match="no number"):
            Quantified(ONION, Provenance(clean(grams_basis=GramsBasis.NONE)))

    def test_an_unquantified_value_refuses_a_provenance_that_earned_a_number(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="carries a number"):
            Unquantified(Provenance(clean()), reason="to taste")

    def test_neither_can_be_mutated_after_the_fact(self) -> None:
        value = Quantified(ONION, Provenance(clean()))

        with pytest.raises(dataclasses.FrozenInstanceError):
            value.amounts = ONION  # type: ignore[misc]


class TestFourNutrientsAndThereIsNoFifth:
    def test_the_four_are_reachable_by_name(self) -> None:
        assert ONION.get("energy") == 40.0
        assert ONION.get("protein") == 1.1
        assert ONION.get("carbs") == 9.3
        assert ONION.get("fat") == 0.1

    def test_a_micronutrient_is_refused_rather_than_degraded(self) -> None:
        with pytest.raises(PaprikaError) as caught:
            ONION.get("sodium")

        assert caught.value.code is Code.NUTRIENT_UNSUPPORTED
        assert caught.value.message.endswith(".")
        assert "nutrient_id" not in caught.value.message

    def test_scaling_is_per_hundred_grams(self) -> None:
        scaled = ONION.scaled_to(150.0)

        assert scaled.energy_kcal == pytest.approx(60.0)
        assert scaled.fat_g == pytest.approx(0.15)


class TestATotalInheritsItsWorstIngredient:
    def measured(self) -> Quantified:
        return Quantified(ONION, Provenance(clean()))

    def estimated(self) -> Quantified:
        return Quantified(
            ONION, Provenance(clean(grams_basis=GramsBasis.PORTION_SIBLING))
        )

    def test_the_worst_wins_rather_than_the_average(self) -> None:
        summed = total([self.measured(), self.measured(), self.estimated()])

        assert isinstance(summed, Quantified)
        assert summed.provenance.tier is Tier.ESTIMATED

    def test_the_amounts_are_summed(self) -> None:
        summed = total([self.measured(), self.measured()])

        assert isinstance(summed, Quantified)
        assert summed.amounts.energy_kcal == pytest.approx(80.0)

    def test_nothing_quantified_means_no_total_at_all(self) -> None:
        summed = total([Unquantified(Provenance(clean(fdc_id=None)), "no match")])

        assert isinstance(summed, Unquantified)

    def test_an_omitted_line_that_stated_a_quantity_caps_the_total(self) -> None:
        """A hole of known size in the sum is not a measurement of anything."""
        omitted = Unquantified(
            Provenance(clean(fdc_id=None, matched_description=None)),
            reason="no match",
            line="1 lb meat of your choice",
            quantity_stated=True,
        )

        summed = total([self.measured(), omitted])

        assert isinstance(summed, Quantified)
        assert summed.provenance.tier is Tier.ESTIMATED
        assert summed.provenance.evidence.omitted_measured_lines == (
            "1 lb meat of your choice",
        )

    def test_a_to_taste_omission_is_named_but_does_not_cap_the_total(self) -> None:
        omitted = Unquantified(
            Provenance(clean(grams_basis=GramsBasis.NONE)),
            reason="to taste",
            line="salt to taste",
            quantity_stated=False,
        )

        summed = total([self.measured(), omitted])

        assert isinstance(summed, Quantified)
        assert summed.provenance.tier is Tier.MEASURED
        assert summed.provenance.evidence.omitted_lines == ("salt to taste",)

    def test_an_empty_recipe_has_no_total(self) -> None:
        assert isinstance(total([]), Unquantified)
