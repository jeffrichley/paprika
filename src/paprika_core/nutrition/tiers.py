"""Provenance, Tier, and the four nutrients there is no fifth of.

The point of this module is not accuracy. Accuracy is not available: the honest
ceiling for whole-recipe macros from free text is roughly ±20-25%, and the error
is contributed by the recipe author and by cooking, upstream of anything we do.
The point is that the uncertainty is *carried*.

Two rules are load-bearing, and both come from
``docs/research/usda-nutrition-matching.md``:

* **A Tier is derived, never asserted.** :class:`Provenance` has no ``tier``
  field — the tier is a property computed from :class:`Evidence`, which holds
  only structural facts we checked ourselves. A matcher's own confidence score
  is not one of those facts and appears nowhere in this module: matchers report
  ~1.0 while inventing specificity (`butter` → `Butter, stick, unsalted`), so a
  score is evidence about nothing.
* **A number cannot exist without its Provenance.** :class:`Quantified` takes a
  :class:`Provenance` as a required argument, and refuses one that did not earn
  a number. Tier D is not a number that renders differently — it is
  :class:`Unquantified`, which has no amounts to render at all.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import final

from paprika_core.errors import Code, PaprikaError

#: The data types a match may come from. Branded is 97% of FoodData Central and
#: outranks real food in relevance ranking, so it is not in the index at all;
#: this set is the second fence rather than the first.
ALLOWED_DATA_TYPES = frozenset(
    {"sr_legacy_food", "survey_fndds_food", "foundation_food"}
)

#: The four, by the names a caller may ask for.
NUTRIENTS = ("energy", "protein", "carbs", "fat")


class Tier(IntEnum):
    """How far a number can be trusted.

    Ordered worst-first so that ``min`` over a recipe's tiers is the pessimistic
    propagation the research doc requires — a total is only as trustworthy as its
    worst ingredient, and averaging confidence is exactly the mistake.

    Internal vocabulary. The tier decides whether a number renders as a value, a
    range, or not at all, and the renderer is the only thing that reads it; the
    grade itself is never shown to her.
    """

    UNQUANTIFIED = 0
    ESTIMATED = 1
    DERIVED = 2
    MEASURED = 3


class GramsBasis(StrEnum):
    """How the gram weight behind a number was arrived at.

    The ladder in the research doc's stage 4, in order. Every rung below the top
    is a degradation that is *recorded* rather than swallowed — a silent fallback
    is how an estimate becomes a measurement.
    """

    #: The line stated a mass. Nothing was converted.
    STATED_MASS = "stated_mass"
    #: The parsed unit matched an actual ``foodPortion`` on the matched record.
    PORTION_EXACT = "portion_exact"
    #: A count or size portion on the matched record — `1 large` → 150 g.
    PORTION_SIZE = "portion_size"
    #: Converted from a different portion of the same dimension on the record.
    PORTION_CONVERTED = "portion_converted"
    #: Borrowed from a sibling record, because this one had no usable portion.
    PORTION_SIBLING = "portion_sibling"
    #: Nothing structural supported it.
    ESTIMATED = "estimated"
    #: There are no grams, so there is no number.
    NONE = "none"


_BASE_TIER = {
    GramsBasis.STATED_MASS: Tier.MEASURED,
    GramsBasis.PORTION_EXACT: Tier.MEASURED,
    GramsBasis.PORTION_SIZE: Tier.DERIVED,
    GramsBasis.PORTION_CONVERTED: Tier.DERIVED,
    GramsBasis.PORTION_SIBLING: Tier.ESTIMATED,
    GramsBasis.ESTIMATED: Tier.ESTIMATED,
}


@final
@dataclass(frozen=True, slots=True)
class Evidence:
    """The structural facts behind one number, all of them checkable by us.

    Attributes:
        grams_basis: Which rung of the gram-weight ladder was used.
        fdc_id: The matched record, so the number is inspectable rather than
            merely badged. ``None`` when nothing matched.
        data_type: The matched record's FoodData Central data type.
        matched_description: The matched record's description, so she can see we
            matched `Onions, raw` when she wrote `yellow onion`.
        dropped_descriptors: Words the line gave us that the matched record does
            not carry. An automatic demotion, regardless of any score.
        unrequested_qualifiers: Nutritionally significant words the record adds
            that the line never asked for — the `unsalted`, `iodized`, `1% fat`
            specificity matchers invent at full confidence.
        unaccounted_words: Words of the line we could not account for at all.
        ambiguities: Choices USDA offered that the line did not settle — `1 cup
            chopped` is 160 g and `1 cup sliced` is 115 g for the same onion.
        quantity_is_range: The author wrote a range and we took its midpoint.
        quantity_not_specified: The only portion available was FNDDS code 90000,
            "Quantity not specified", which USDA warns should not be read as an
            average amount.
        omitted_lines: On a total only — lines that produced no number.
        omitted_measured_lines: On a total only — omitted lines that stated a
            quantity, so the sum has a hole of known size in it.
        aggregate: Whether this is a total rather than one ingredient. A total
            has no single matched record, so the absence of one is not the
            failure it would be for an ingredient.
    """

    grams_basis: GramsBasis
    fdc_id: int | None
    data_type: str | None = None
    matched_description: str | None = None
    dropped_descriptors: tuple[str, ...] = ()
    unrequested_qualifiers: tuple[str, ...] = ()
    unaccounted_words: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    quantity_is_range: bool = False
    quantity_not_specified: bool = False
    omitted_lines: tuple[str, ...] = ()
    omitted_measured_lines: tuple[str, ...] = ()
    aggregate: bool = False


def _demotions(evidence: Evidence) -> tuple[str, ...]:
    """Return every structural reason this number is worth less than it looks.

    Args:
        evidence: The facts behind the number.

    Returns:
        tuple[str, ...]: One note per demotion, in a fixed order.
    """
    notes: list[str] = []
    for word in evidence.dropped_descriptors:
        notes.append(f"the match dropped '{word}'")
    for word in evidence.unrequested_qualifiers:
        notes.append(f"the match added '{word}', which the line did not ask for")
    for word in evidence.unaccounted_words:
        notes.append(f"'{word}' in the line was not accounted for")
    notes.extend(evidence.ambiguities)
    if evidence.quantity_is_range:
        notes.append("the line gave a range, and the midpoint was used")
    if evidence.quantity_not_specified:
        notes.append("the only portion available was 'quantity not specified'")
    if evidence.data_type is not None and evidence.data_type not in ALLOWED_DATA_TYPES:
        notes.append(f"the record is {evidence.data_type}, which we do not trust here")
    if evidence.omitted_measured_lines:
        notes.append(
            f"{len(evidence.omitted_measured_lines)} measured ingredient(s) could "
            "not be matched and are missing from the total"
        )
    return tuple(notes)


def _tier_for(evidence: Evidence) -> Tier:
    """Derive the tier from structural evidence alone.

    Args:
        evidence: The facts behind the number.

    Returns:
        Tier: The best tier this evidence earns. Demotions stack, and they floor
            at ``ESTIMATED`` — a demotion may make a number worth less, but it
            cannot turn an existing number into no number, which is what
            ``UNQUANTIFIED`` means.
    """
    if evidence.grams_basis is GramsBasis.NONE:
        return Tier.UNQUANTIFIED
    if evidence.fdc_id is None and not evidence.aggregate:
        return Tier.UNQUANTIFIED
    tier = _BASE_TIER[evidence.grams_basis]
    steps = len(_demotions(evidence))
    tier = Tier(max(Tier.ESTIMATED, tier - steps))
    if evidence.data_type is not None and evidence.data_type not in ALLOWED_DATA_TYPES:
        # A hard cap rather than one more demotion: a record outside these three
        # data types is label accuracy at best, and no amount of clean structure
        # around it earns more than an estimate.
        tier = min(tier, Tier.ESTIMATED)
    if evidence.omitted_measured_lines:
        # A total missing an ingredient whose quantity the author stated has a
        # hole of known size in it, and a sum with a hole is not a measurement.
        tier = min(tier, Tier.ESTIMATED)
    return tier


@final
@dataclass(frozen=True, slots=True)
class Provenance:
    """The labelled origin of a number and how far it can be trusted.

    There is deliberately no ``tier`` field. The tier is derived from
    :attr:`evidence`, so no call site can hand a number a grade it did not earn.

    Args:
        evidence: The structural facts behind the number.
        inherited: A tier propagated from elsewhere — the worst ingredient of a
            total. It can only lower the result, never raise it, so inheriting
            is safe in the one direction that matters.
    """

    evidence: Evidence
    inherited: Tier | None = None

    @property
    def tier(self) -> Tier:
        """Return the tier this number earned.

        Returns:
            Tier: The derived tier, lowered by anything inherited.
        """
        earned = _tier_for(self.evidence)
        if self.inherited is None:
            return earned
        return min(earned, self.inherited)

    @property
    def notes(self) -> tuple[str, ...]:
        """Return every degradation recorded on this number.

        Returns:
            tuple[str, ...]: The structural reasons, in a fixed order. Empty when
                nothing was given up.
        """
        return _demotions(self.evidence)


@final
@dataclass(frozen=True, slots=True)
class Amounts:
    """The four nutrients, and there is no fifth.

    Micronutrients are refused outright rather than degraded: shipping apps show
    sodium 51% low, cholesterol 77% low and an iron correlation of roughly zero,
    and a flat no beats an unpredictable yes.

    Attributes:
        energy_kcal: Energy, in kilocalories.
        protein_g: Protein, in grams.
        carbohydrate_g: Carbohydrate by difference, in grams.
        fat_g: Total lipid, in grams.
    """

    energy_kcal: float
    protein_g: float
    carbohydrate_g: float
    fat_g: float

    def get(self, nutrient: str) -> float:
        """Return one nutrient by name.

        Args:
            nutrient: One of ``energy``, ``protein``, ``carbs``, ``fat``.

        Returns:
            float: The amount.

        Raises:
            PaprikaError: ``nutrient_unsupported`` for anything else. This is the
                refusal, and it is deliberately not a fallback.
        """
        try:
            return {
                "energy": self.energy_kcal,
                "protein": self.protein_g,
                "carbs": self.carbohydrate_g,
                "fat": self.fat_g,
            }[nutrient]
        except KeyError:
            raise PaprikaError(
                Code.NUTRIENT_UNSUPPORTED,
                "I only work out energy, protein, carbohydrate and fat, and "
                f"{nutrient} isn't one of them.",
                detail=f"unsupported nutrient {nutrient!r}",
            ) from None

    def scaled_to(self, grams: float) -> Amounts:
        """Scale these per-100-gram amounts to a gram weight.

        Args:
            grams: The weight to scale to.

        Returns:
            Amounts: The scaled amounts.
        """
        factor = grams / 100.0
        return Amounts(
            energy_kcal=self.energy_kcal * factor,
            protein_g=self.protein_g * factor,
            carbohydrate_g=self.carbohydrate_g * factor,
            fat_g=self.fat_g * factor,
        )

    def __add__(self, other: Amounts) -> Amounts:
        """Add two sets of amounts.

        Args:
            other: The amounts to add.

        Returns:
            Amounts: The sum.
        """
        return Amounts(
            energy_kcal=self.energy_kcal + other.energy_kcal,
            protein_g=self.protein_g + other.protein_g,
            carbohydrate_g=self.carbohydrate_g + other.carbohydrate_g,
            fat_g=self.fat_g + other.fat_g,
        )


@final
@dataclass(frozen=True, slots=True)
class Quantified:
    """Amounts that cannot be constructed without their Provenance.

    Args:
        amounts: The four nutrients.
        provenance: Where they came from and how far they can be trusted.
            Required, positional, and no default — a call site cannot forget it,
            because forgetting it is a ``TypeError``.

    Raises:
        ValueError: When the provenance did not earn a number at all. A Tier D
            value is :class:`Unquantified`; it is not a number that renders
            quietly.
    """

    amounts: Amounts
    provenance: Provenance

    def __post_init__(self) -> None:
        """Refuse a provenance that earned no number."""
        if self.provenance.tier is Tier.UNQUANTIFIED:
            raise ValueError(
                "this provenance earned no number, so there is nothing to carry"
            )


@final
@dataclass(frozen=True, slots=True)
class Unquantified:
    """An ingredient that gets no number at all, and says why.

    Tier D existing is the honest part. The temptation is to make everything a
    number; refusing to is what separates this from the tools that quietly guess.

    Args:
        provenance: Its provenance, whose tier must be ``UNQUANTIFIED``.
        reason: Why there is no number, in one short phrase.
        line: The ingredient line, so a total can name what it left out.
        quantity_stated: Whether the line said how much. ``1 lb meat of your
            choice`` did; ``salt to taste`` did not, and the difference decides
            whether a total containing it has a hole of known size.

    Raises:
        ValueError: When the provenance did earn a number.
    """

    provenance: Provenance
    reason: str
    line: str = ""
    quantity_stated: bool = False

    def __post_init__(self) -> None:
        """Refuse a provenance that earned a number."""
        if self.provenance.tier is not Tier.UNQUANTIFIED:
            raise ValueError(
                "this provenance carries a number, so it is not unquantified"
            )


#: One ingredient's nutrition, or its refusal. There is no third state, and no
#: way to hold amounts outside of one of these two.
Value = Quantified | Unquantified


def total(values: Iterable[Value]) -> Value:
    """Sum a recipe's ingredients, pessimistically.

    The total inherits the tier of its *worst* quantified ingredient — the
    minimum, never an average, because a mean hides exactly the spread that
    signals a matching problem.

    Omitted ingredients are named on the result rather than dropped. An omission
    that stated a quantity caps the total at ``ESTIMATED``: the sum is then
    missing a known amount of food. An omission that stated no quantity — `salt
    to taste`, `for serving` — is recorded but does not cap, because whether it
    mattered is cooking judgement rather than a structural fact.

    Args:
        values: The ingredients' values, quantified or not.

    Returns:
        Value: The total, or :class:`Unquantified` when nothing could be
            quantified at all.
    """
    amounts: Amounts | None = None
    worst: Tier | None = None
    basis = GramsBasis.STATED_MASS
    omitted: list[str] = []
    omitted_measured: list[str] = []
    for value in values:
        if isinstance(value, Unquantified):
            omitted.append(value.line or value.reason)
            if value.quantity_stated:
                omitted_measured.append(value.line or value.reason)
            continue
        amounts = value.amounts if amounts is None else amounts + value.amounts
        tier = value.provenance.tier
        worst = tier if worst is None else min(worst, tier)
        basis = _worse_basis(basis, value.provenance.evidence.grams_basis)

    if amounts is None or worst is None:
        return Unquantified(
            Provenance(Evidence(grams_basis=GramsBasis.NONE, fdc_id=None)),
            reason="nothing in this recipe could be matched",
        )
    evidence = Evidence(
        grams_basis=basis,
        fdc_id=None,
        omitted_lines=tuple(omitted),
        omitted_measured_lines=tuple(omitted_measured),
        aggregate=True,
    )
    return Quantified(amounts, Provenance(evidence, inherited=worst))


def _worse_basis(left: GramsBasis, right: GramsBasis) -> GramsBasis:
    """Return whichever of two gram bases is further down the ladder.

    Args:
        left: One basis.
        right: The other.

    Returns:
        GramsBasis: The worse of the two.
    """
    order = list(GramsBasis)
    return left if order.index(left) >= order.index(right) else right
