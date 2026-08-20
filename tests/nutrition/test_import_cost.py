"""The session-start budget, defended by a test rather than by good intentions.

There is a measured ~54 ms budget on starting a session, and the ingredient
parser costs about ten times that to import on its own — it pulls numpy and
nltk. So it is imported inside the function that needs it, and this pins that:
an accidental module-scope import would be invisible in every other test and
would quietly spend the whole budget.
"""

from __future__ import annotations

import subprocess
import sys

PROGRAM = """
import sys
import {module}
loaded = [name for name in sys.modules if name.startswith(("{watched}",))]
print(",".join(sorted(loaded)))
"""


def loaded_by(module: str, watched: str) -> set[str]:
    """Import a module in a fresh interpreter and report what came with it.

    Args:
        module: The module to import.
        watched: The prefix to report on.

    Returns:
        set[str]: The modules loaded whose names start with ``watched``.
    """
    result = subprocess.run(
        [sys.executable, "-c", PROGRAM.format(module=module, watched=watched)],
        capture_output=True,
        text=True,
        check=True,
    )
    return {name for name in result.stdout.strip().split(",") if name}


def test_the_session_does_not_pay_for_nutrition_at_all() -> None:
    assert loaded_by("paprika_core", "paprika_core.nutrition") == set()


def test_importing_nutrition_does_not_pay_for_the_parser() -> None:
    """It is half a second, an order of magnitude over the whole budget."""
    assert loaded_by("paprika_core.nutrition", "ingredient_parser") == set()


def test_importing_nutrition_does_not_pay_for_numpy_either() -> None:
    assert loaded_by("paprika_core.nutrition", "numpy") == set()
