"""The wait estimate — measured on her machine, not read out of a research doc.

There are no timeouts and no budgets anywhere. Long work is resumable because it
commits incrementally, not because it is timed. The only number here is an
*estimate shown before a wait*, so that silence has an explanation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paprika_core import pace
from paprika_core.log import log_event


def test_a_first_run_falls_back_to_the_published_figure(paprika_home: Path) -> None:
    """~200 ms is what the research says. It is used exactly once — before we know."""
    assert pace.typical_request_seconds() == pytest.approx(0.2)


def test_the_estimate_is_measured_from_her_own_machine(paprika_home: Path) -> None:
    for ms in (500.0, 520.0, 480.0, 510.0, 490.0):
        log_event("request", method="GET", path="/api/v2/sync/recipe/X/", ms=ms)

    assert pace.typical_request_seconds() == pytest.approx(0.5, abs=0.02)


def test_the_median_ignores_one_outlier(paprika_home: Path) -> None:
    """A single stalled request must not turn a two-minute wait into an hour."""
    for ms in (200.0, 210.0, 190.0, 205.0, 600_000.0):
        log_event("request", method="GET", path="/api/v2/sync/recipe/X/", ms=ms)

    assert pace.typical_request_seconds() == pytest.approx(0.205, abs=0.02)


def test_a_cold_sync_estimate_is_one_request_per_recipe(paprika_home: Path) -> None:
    """1 + N, because there is no bulk recipe download."""
    for _ in range(5):
        log_event("request", method="GET", path="/api/v2/sync/recipe/X/", ms=200.0)

    assert pace.cold_sync_seconds(500) == pytest.approx(0.2 * 501, abs=1.0)


def test_an_empty_library_needs_no_wait(paprika_home: Path) -> None:
    assert pace.cold_sync_seconds(0) == pytest.approx(0.2)


def test_records_without_a_duration_are_ignored(paprika_home: Path) -> None:
    log_event("command", attempted="reading your recipes")
    log_event("request", method="GET", path="/api/v2/sync/status/", ms=800.0)

    assert pace.typical_request_seconds() == pytest.approx(0.8, abs=0.02)


def test_a_corrupt_log_line_does_not_break_the_estimate(paprika_home: Path) -> None:
    log_event("request", method="GET", path="/x/", ms=300.0)
    log = paprika_home / "logs" / "paprika.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write("{not json at all\n")

    assert pace.typical_request_seconds() == pytest.approx(0.3, abs=0.02)


def test_an_unreadable_log_falls_back_rather_than_failing(
    paprika_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAPRIKA_HOME", "/dev/null/nowhere")

    assert pace.typical_request_seconds() == pytest.approx(0.2)
