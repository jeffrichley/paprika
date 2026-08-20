"""Reading the materialised index.

Two things it will never do, both of them lessons from
``docs/research/usda-nutrition-matching.md``. It does not widen a search until
something comes back — the head word is required, and no candidates is a
refusal. And it does not hand anybody ``foodPortions[0]``: 24% of FNDDS portion
rows are code 90000, "Quantity not specified", they frequently sort first, and
for raw onion that row is 15 g where a whole onion is 148 g.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import final

from paprika_core.nutrition.materialise import materialise
from paprika_core.nutrition.portions import Portion, PortionKind
from paprika_core.nutrition.tiers import Amounts


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
