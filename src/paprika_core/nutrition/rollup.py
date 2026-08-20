"""The week's nutrition, shaped so its uncertainty is visible without a footnote.

The week is the unit. A day inside it is context, never a verdict — one
indulgent Friday is not a judgement about anything, and rendering it as though
it were is how a meal planner turns into a calorie tracker.

**The shape carries the trust.** A range is the normal rendering, so a bare
number is rare enough that seeing one means something: it is reserved for a
total whose every ingredient was weighed and matched. Nothing here ever shows
her a grade, a letter or a score — the Tier decides the shape and then stops
existing as far as she is concerned.

**Nothing is dropped silently.** ``to taste`` is footnoted once as a class
rather than repeated per line; anything unmatched is named; and a main component
nobody could match means **no number at all**, because a total missing its meat
is not a smaller total, it is a wrong one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from paprika_core.mirror import Mirror
from paprika_core.nutrition.tiers import Amounts, Quantified, Tier, Unquantified, Value

#: How wide a range is, per tier. The honest ceiling is ±20–25% and it is
#: unfixable — it comes from the recipe's author and from what cooking does —
#: so these are not precision, they are the size of the doubt.
BANDS: dict[Tier, float] = {
    Tier.MEASURED: 0.0,
    Tier.DERIVED: 0.20,
    Tier.ESTIMATED: 0.40,
}

#: A line that says how much of something to use has a hole of known size when
#: it cannot be matched. One that does not — `salt to taste` — has a hole nobody
#: could size, and it is footnoted as a class rather than named again and again.
TO_TASTE = "to taste"


@dataclass(frozen=True)
class Nutrient:
    """One nutrient, rendered in the shape its trustworthiness earned.

    Attributes:
        name: What it is, in her words.
        low: The bottom of the range, or the value itself when it is a point.
        high: The top of the range, or the value itself when it is a point.
        exact: Whether this is a point value. Reserved for fully measured, so
            that its rarity carries meaning.
    """

    name: str
    low: float
    high: float
    exact: bool


@dataclass(frozen=True)
class Rollup:
    """What a stretch of days comes to, and what it could not account for.

    Attributes:
        nutrients: The four, and there is no fifth.
        days: How many days were covered.
        meals: How many meals contributed.
        excluded: Ingredients that got no number, named.
        to_taste: How many lines were seasoning nobody could size.
        weakest: The single worst input, phrased to be acted on.
        refused: Set when a main component could not be matched, in which case
            there are no nutrients at all.
    """

    nutrients: tuple[Nutrient, ...] = ()
    days: int = 0
    meals: int = 0
    excluded: tuple[str, ...] = ()
    to_taste: int = 0
    weakest: str | None = None
    refused: str | None = None


def _band(value: Quantified) -> float:
    """Return how wide this number's range should be.

    Args:
        value: The quantified amounts.

    Returns:
        float: A fraction, zero when the number earned a point value.
    """
    return BANDS.get(value.provenance.tier, BANDS[Tier.ESTIMATED])


def _nutrients(amounts: Amounts, band: float) -> tuple[Nutrient, ...]:
    """Render the four nutrients at a given width.

    Args:
        amounts: The four.
        band: How wide the range is, as a fraction.

    Returns:
        tuple[Nutrient, ...]: Rendered, rounded to something a person would say.
    """
    named = (
        ("energy", amounts.energy_kcal),
        ("protein", amounts.protein_g),
        ("carbs", amounts.carbohydrate_g),
        ("fat", amounts.fat_g),
    )
    return tuple(
        Nutrient(
            name=name,
            low=round(total * (1 - band)),
            high=round(total * (1 + band)),
            exact=band == 0.0,
        )
        for name, total in named
    )


def _is_main(line: str) -> bool:
    """Say whether a line looks like a main component of the dish.

    Crude on purpose. Getting this wrong in the cautious direction costs a
    number she could have had; getting it wrong the other way hands her a total
    with its meat missing, which looks exactly like a real one.

    Args:
        line: The ingredient line.

    Returns:
        bool: Whether missing it would hollow out the total.
    """
    words = line.casefold()
    mains = (
        "beef",
        "chicken",
        "pork",
        "lamb",
        "fish",
        "salmon",
        "cod",
        "tofu",
        "beans",
        "lentils",
        "pasta",
        "rice",
        "potato",
        "flour",
        "cheese",
        "egg",
        "mince",
        "steak",
        "thigh",
        "breast",
        "meat",
    )
    return any(main in words for main in mains)


def _weakest_of(values: Iterable[Value]) -> str | None:
    """Name the single worst input, so the caveat is actionable.

    One line she could go and fix beats a paragraph about uncertainty in
    general.

    Args:
        values: Every value in the stretch.

    Returns:
        str | None: One phrase, or ``None`` when nothing is weak enough to name.
    """
    unquantified = [v for v in values if isinstance(v, Unquantified)]
    sized = [v for v in unquantified if v.quantity_stated]
    if sized:
        return sized[0].line
    worst: Quantified | None = None
    for value in values:
        if isinstance(value, Quantified) and (
            worst is None or value.provenance.tier < worst.provenance.tier
        ):
            worst = value
    if worst is None or worst.provenance.tier >= Tier.DERIVED:
        return None
    return next(iter(worst.provenance.notes), None)


def over(
    mirror: Mirror,
    since: str = "",
    until: str = "",
    analyse: Any = None,
) -> Rollup:
    """Work out what a stretch of days comes to.

    Args:
        mirror: The Mirror to read the Plan and the recipes from.
        since: First day, ``YYYY-MM-DD``.
        until: Last day, ``YYYY-MM-DD``.
        analyse: How to analyse an ingredient list. Injected so the caller owns
            opening the index, which is expensive and should happen once.

    Returns:
        Rollup: The week, or a refusal naming what it could not account for.
    """
    from paprika_core.groceries import _ingredient_lines

    meals = [meal for meal in mirror.meals(since, until) if meal.recipe_handle]
    days = {meal.date for meal in meals}

    values: list[Value] = []
    for meal in meals:
        body = mirror.recipe_body(meal.recipe_handle or "")
        if body is None:
            continue
        values.extend(analyse(_ingredient_lines(body)).values)

    return _shape(values, days=len(days), meals=len(meals))


def _shape(values: list[Value], *, days: int, meals: int) -> Rollup:
    """Turn analysed values into the shape she is shown.

    Args:
        values: Every value contributing.
        days: How many days were covered.
        meals: How many meals contributed.

    Returns:
        Rollup: The rendering.
    """
    if not values:
        return Rollup(days=days, meals=meals)

    missing_main = next(
        (
            value.line
            for value in values
            if isinstance(value, Unquantified)
            and value.quantity_stated
            and _is_main(value.line)
        ),
        None,
    )
    if missing_main is not None:
        # A total missing its meat is not a smaller total. It is a wrong one,
        # and a wrong one that looks exactly like a right one.
        return Rollup(days=days, meals=meals, refused=missing_main)

    quantified = [value for value in values if isinstance(value, Quantified)]
    if not quantified:
        return Rollup(days=days, meals=meals, refused="everything in it")

    totals = Amounts(
        energy_kcal=sum(v.amounts.energy_kcal for v in quantified),
        protein_g=sum(v.amounts.protein_g for v in quantified),
        carbohydrate_g=sum(v.amounts.carbohydrate_g for v in quantified),
        fat_g=sum(v.amounts.fat_g for v in quantified),
    )
    # The total inherits the provenance of its worst ingredient, so the band is
    # the widest any of them earned.
    band = max(_band(value) for value in quantified)
    # Anything summed from raw ingredients and shown as a cooked dish is capped
    # below measured, because cooking moves energy by as much as half.
    band = max(band, BANDS[Tier.DERIVED])

    excluded = tuple(
        value.line
        for value in values
        if isinstance(value, Unquantified) and TO_TASTE not in value.line.casefold()
    )
    seasoning = sum(
        1
        for value in values
        if isinstance(value, Unquantified) and TO_TASTE in value.line.casefold()
    )

    return Rollup(
        nutrients=_nutrients(totals, band),
        days=days,
        meals=meals,
        excluded=excluded,
        to_taste=seasoning,
        weakest=_weakest_of(values),
    )


def of_lines(lines: list[str], analyse: Any) -> Rollup:
    """Work out what one ingredient list comes to.

    Shaped exactly as a week is, so a recipe and a week never disagree about
    what a number of a given trustworthiness looks like.

    Args:
        lines: The ingredient lines.
        analyse: How to analyse them.

    Returns:
        Rollup: The recipe, or a refusal naming what it could not account for.
    """
    return _shape(list(analyse(lines).values), days=0, meals=1)


def as_data(rollup: Rollup) -> dict[str, Any]:
    """Render a Rollup for the session.

    No tier, no letter, no score — the shape is what carries the trust, and a
    grade would invite exactly the precision this cannot support.

    Args:
        rollup: What was worked out.

    Returns:
        dict[str, Any]: The envelope payload.
    """
    return {
        "days": rollup.days,
        "meals": rollup.meals,
        "nutrients": [
            {
                "name": nutrient.name,
                "low": nutrient.low,
                "high": nutrient.high,
                "exact": nutrient.exact,
            }
            for nutrient in rollup.nutrients
        ],
        "excluded": list(rollup.excluded),
        "seasoning_lines": rollup.to_taste,
        "weakest": rollup.weakest,
        "no_number_because": rollup.refused,
    }


def written_back(rollup: Rollup, today: str) -> str:
    """Render a Rollup for the field that escapes to her phone.

    This string leaves the fence. It appears in Paprika, on a device where no
    skill is running and nothing can explain it, possibly years later — so the
    hedge and the date are **part of the string** rather than something a caller
    remembers to add. That is also why the hedge is composed here and not by
    whoever is doing the writing.

    Args:
        rollup: What was worked out.
        today: The date, as ``YYYY-MM-DD``.

    Returns:
        str: What to store, hedge and date inline.

    Raises:
        ValueError: When there is no number to write. Writing "we could not say"
            into her recipe would be worse than writing nothing.
    """
    if rollup.refused is not None or not rollup.nutrients:
        raise ValueError("no number was earned, so there is nothing to write back")

    units = {"energy": "kcal", "protein": "g", "carbs": "g", "fat": "g"}
    lines = []
    for nutrient in rollup.nutrients:
        unit = units[nutrient.name]
        shown = (
            f"{nutrient.low:g} {unit}"
            if nutrient.exact
            else f"{nutrient.low:g}–{nutrient.high:g} {unit}"
        )
        lines.append(f"{nutrient.name.title()}: {shown}")
    lines.append("")
    lines.append(
        f"Estimated from the ingredients on {today}. These are approximate — "
        "cooking and the way a recipe is written both move them."
    )
    if rollup.excluded:
        lines.append(f"Not counted: {', '.join(rollup.excluded)}.")
    return "\n".join(lines)
