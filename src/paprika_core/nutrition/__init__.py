"""Nutrition — four numbers, each carrying how far it can be trusted.

The library and data layer only. Nothing here renders anything, and nothing here
is reachable from the session: the skill and the CLI command that read this are
a separate piece of work.

Importing this package is cheap. The ingredient parser is heavy — it pulls numpy
and nltk and costs about half a second to import — so every use of it is behind a
lazy import inside :mod:`paprika_core.nutrition.parsing`, and a test pins that
importing this package does not pay for it.
"""

from __future__ import annotations

from paprika_core.nutrition.analysis import Analysis, analyse, analyse_line, opened
from paprika_core.nutrition.tiers import (
    ALLOWED_DATA_TYPES,
    NUTRIENTS,
    Amounts,
    Evidence,
    GramsBasis,
    Provenance,
    Quantified,
    Tier,
    Unquantified,
    Value,
    total,
)

__all__ = [
    "ALLOWED_DATA_TYPES",
    "Analysis",
    "NUTRIENTS",
    "Amounts",
    "Evidence",
    "GramsBasis",
    "Provenance",
    "Quantified",
    "Tier",
    "Unquantified",
    "Value",
    "analyse",
    "analyse_line",
    "opened",
    "total",
]
