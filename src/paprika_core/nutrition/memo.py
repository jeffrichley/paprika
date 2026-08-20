"""``nutrition.sqlite3`` — what it cost to work one ingredient line out.

Keyed on the **ingredient line**, never on the recipe. Two recipes that both say
`2 tbsp olive oil` are the same question, and a memo keyed on a recipe would ask
it twice and then throw both answers away the moment either recipe was edited.

A memo stores the Tier and the structural evidence beside the number, not the
number alone — a cached figure without its provenance is exactly the object this
package exists to make unconstructable. It stores the tier *and* re-derives it on
the way out: if the two disagree, the rules changed since the memo was written
and the memo is a miss rather than an answer.

This is a separate database from ``usda.sqlite3`` on purpose. That one is
disposable and rebuilds in a second. This one is not.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from types import TracebackType
from typing import Any, final

from paprika_core.nutrition.tiers import (
    Amounts,
    Evidence,
    GramsBasis,
    Provenance,
    Quantified,
    Tier,
    Unquantified,
    Value,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS memos (
    line_key   TEXT PRIMARY KEY,
    line       TEXT NOT NULL,
    signature  TEXT NOT NULL,
    tier       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    written_at REAL NOT NULL
);
"""


def memo_key(line: str) -> str:
    """Reduce an ingredient line to the key two recipes would share.

    Args:
        line: The line as she wrote it.

    Returns:
        str: The key.
    """
    return " ".join(line.lower().split())


def _encode(value: Value) -> dict[str, Any]:
    """Turn a value into something JSON holds.

    Args:
        value: The value.

    Returns:
        dict[str, Any]: Its fields, evidence included.
    """
    evidence = asdict(value.provenance.evidence)
    if isinstance(value, Quantified):
        return {"amounts": asdict(value.amounts), "evidence": evidence}
    return {
        "evidence": evidence,
        "reason": value.reason,
        "line": value.line,
        "quantity_stated": value.quantity_stated,
    }


def _decode(payload: dict[str, Any]) -> Value:
    """Rebuild a value from storage.

    The tier is not read back — it is derived again from the evidence, so a
    memo can never smuggle in a grade the current rules would not give it.

    Args:
        payload: What :func:`_encode` wrote.

    Returns:
        Value: The value.
    """
    stored = dict(payload["evidence"])
    stored["grams_basis"] = GramsBasis(stored["grams_basis"])
    for name in (
        "dropped_descriptors",
        "unrequested_qualifiers",
        "unaccounted_words",
        "ambiguities",
        "omitted_lines",
        "omitted_measured_lines",
    ):
        stored[name] = tuple(stored[name])
    provenance = Provenance(Evidence(**stored))
    if "amounts" in payload:
        return Quantified(Amounts(**payload["amounts"]), provenance)
    return Unquantified(
        provenance,
        reason=payload["reason"],
        line=payload["line"],
        quantity_stated=payload["quantity_stated"],
    )


@final
class Memos:
    """The memo store, opened against one SQLite file.

    Args:
        path: Where the database lives.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()

    def __enter__(self) -> Memos:
        """Enter the context manager.

        Returns:
            Memos: This store.
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

    def recall(self, line: str, signature: str) -> Value | None:
        """Return what this line worked out to last time, if it still holds.

        Args:
            line: The ingredient line.
            signature: The index signature the answer must have come from.

        Returns:
            Value | None: The remembered value, or ``None`` when there is none,
                when it came from a different index, or when the tier it was
                written with is not the tier the current rules derive.
        """
        row = self._db.execute(
            "SELECT signature, tier, payload FROM memos WHERE line_key = ?",
            (memo_key(line),),
        ).fetchone()
        if row is None or row["signature"] != signature:
            return None
        try:
            value = _decode(json.loads(row["payload"]))
        except (KeyError, TypeError, ValueError):
            return None
        if value.provenance.tier.name != row["tier"]:
            return None
        return value

    def remember(self, line: str, value: Value, signature: str) -> None:
        """Store what this line worked out to.

        Args:
            line: The ingredient line.
            value: What it worked out to, provenance and all.
            signature: The index signature it came from.
        """
        self._db.execute(
            "INSERT OR REPLACE INTO memos (line_key, line, signature, tier,"
            " payload, written_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                memo_key(line),
                line,
                signature,
                Tier(value.provenance.tier).name,
                json.dumps(_encode(value)),
                time.time(),
            ),
        )
        self._db.commit()

    def count(self) -> int:
        """Return how many memos are stored.

        Returns:
            int: The count.
        """
        return int(self._db.execute("SELECT COUNT(*) FROM memos").fetchone()[0])
