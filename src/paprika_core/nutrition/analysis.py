"""One ingredient line in, one number-with-its-provenance out — or no number.

The stages in order, each of which can end the line's journey honestly:

* **parse** — if the author never said how much, there is no number to have;
* **match** — if nothing in the index carries the food's head word, we stop
  rather than widen the search until something comes back;
* **weigh** — if USDA has nothing that turns the stated quantity into grams, we
  stop rather than invent one;
* **label** — everything that survived carries what it cost to get here.

Nothing in this module renders anything, and nothing decides whether an omitted
ingredient was the main event. That is cooking judgement, and it lives on the
far side of the CLI.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import final

from paprika_core import store
from paprika_core.nutrition.index import UsdaIndex, open_index
from paprika_core.nutrition.matching import match, query_words
from paprika_core.nutrition.materialise import bundle_signature
from paprika_core.nutrition.memo import Memos
from paprika_core.nutrition.parsing import parse_line
from paprika_core.nutrition.quantify import weigh
from paprika_core.nutrition.tiers import (
    Evidence,
    GramsBasis,
    Provenance,
    Quantified,
    Unquantified,
    Value,
)
from paprika_core.nutrition.tiers import total as sum_values


@final
@dataclass(frozen=True, slots=True)
class Analysis:
    """A recipe's ingredients, and their total.

    Attributes:
        values: One value per line, in the order the lines were given.
        total: The sum, carrying the provenance of its worst ingredient and
            naming everything it had to leave out.
    """

    values: tuple[Value, ...]
    total: Value


def _refusal(
    reason: str,
    line: str,
    *,
    quantity_stated: bool,
    fdc_id: int | None = None,
    data_type: str | None = None,
    description: str | None = None,
) -> Unquantified:
    """Build the "no number" answer, saying which record it got as far as.

    Args:
        reason: Why there is no number.
        line: The ingredient line.
        quantity_stated: Whether the author said how much.
        fdc_id: The record we reached, when we reached one.
        data_type: That record's data type.
        description: That record's description.

    Returns:
        Unquantified: The refusal.
    """
    evidence = Evidence(
        grams_basis=GramsBasis.NONE,
        fdc_id=fdc_id,
        data_type=data_type,
        matched_description=description,
    )
    return Unquantified(
        Provenance(evidence),
        reason=reason,
        line=line,
        quantity_stated=quantity_stated,
    )


def analyse_line(line: str, index: UsdaIndex, memos: Memos | None = None) -> Value:
    """Work out one ingredient line.

    Args:
        line: The line as she wrote it.
        index: The USDA index.
        memos: Where to remember the answer, when there is somewhere.

    Returns:
        Value: The number and its provenance, or the refusal and its reason.
    """
    signature = bundle_signature()
    if memos is not None:
        remembered = memos.recall(line, signature)
        if remembered is not None:
            return remembered
    value = _work_out(line, index)
    if memos is not None:
        memos.remember(line, value, signature)
    return value


def _work_out(line: str, index: UsdaIndex) -> Value:
    """Work one line out from scratch.

    Args:
        line: The line.
        index: The USDA index.

    Returns:
        Value: The number and its provenance, or the refusal and its reason.
    """
    parsed = parse_line(line)
    if not parsed.name:
        return _refusal("there is no food in this line", line, quantity_stated=False)

    found = match(parsed, index)
    if found is None:
        return _refusal(
            "nothing in the USDA data matches this",
            line,
            quantity_stated=not parsed.open_ended,
        )
    record = found.record

    if parsed.open_ended:
        return _refusal(
            "the recipe doesn't say how much",
            line,
            quantity_stated=False,
            fdc_id=record.fdc_id,
            data_type=record.data_type,
            description=record.description,
        )

    words = query_words(parsed)
    weight = weigh(parsed, record, index, words)
    if weight is None:
        return _refusal(
            "there is no way to turn that into a weight",
            line,
            quantity_stated=True,
            fdc_id=record.fdc_id,
            data_type=record.data_type,
            description=record.description,
        )

    unaccounted = (
        parsed.unaccounted
        + tuple(word for word in weight.unaccounted if word)
        + tuple(f"or {name}" for name in parsed.alternatives)
    )
    evidence = Evidence(
        grams_basis=weight.basis,
        fdc_id=record.fdc_id,
        data_type=record.data_type,
        matched_description=record.description,
        dropped_descriptors=found.dropped,
        unrequested_qualifiers=found.unrequested,
        unaccounted_words=unaccounted,
        ambiguities=weight.ambiguities,
        quantity_is_range=parsed.is_range,
        quantity_not_specified=weight.quantity_not_specified,
    )
    return Quantified(record.amounts.scaled_to(weight.grams), Provenance(evidence))


def analyse(
    lines: Iterable[str], index: UsdaIndex, memos: Memos | None = None
) -> Analysis:
    """Work out a whole ingredient list.

    Args:
        lines: The ingredient lines, in the order she wrote them.
        index: The USDA index.
        memos: Where to remember the answers, when there is somewhere.

    Returns:
        Analysis: One value per line, and the total.
    """
    values = tuple(analyse_line(line, index, memos) for line in lines)
    return Analysis(values=values, total=sum_values(values))


@contextmanager
def opened() -> Iterator[tuple[UsdaIndex, Memos]]:
    """Open the index and the memos against this machine's store.

    The index is materialised first if this machine has no current one, which
    costs about a second and happens once per machine rather than once per
    installed version.

    Yields:
        tuple[UsdaIndex, Memos]: Both, closed again on the way out.
    """
    index = open_index()
    try:
        with Memos(store.memo_path()) as memos:
            yield index, memos
    finally:
        index.close()
