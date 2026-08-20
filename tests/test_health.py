"""The library health report — arithmetic, so the question is free to ask.

No agent is dispatched to answer it. It is instant, deterministic, and incapable
of being wrong in an interesting way — which is what makes re-asking next week a
progress signal rather than another judgement.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core import health, store
from paprika_core.cli import app
from paprika_core.mirror import Mirror
from tests.fake_paprika import FakePaprika
from tests.library import CATEGORY_TREE, make_recipe
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()


def _library(mirror: Mirror, *recipes: dict) -> Mirror:
    """Fill a Mirror with her category tree and some recipes.

    Args:
        mirror: An empty Mirror.
        *recipes: The recipes.

    Returns:
        Mirror: The same Mirror, filled.
    """
    mirror.put_categories(CATEGORY_TREE)
    for recipe in recipes:
        mirror.put_recipe(recipe)
    mirror.assign_handles()
    return mirror


def _uid(number: int) -> str:
    """Return a distinct uid.

    Args:
        number: Which one.

    Returns:
        str: A uid.
    """
    return f"{number:08X}-0000-4000-8000-000000000000"


def test_a_tidy_library_finds_nothing(mirror: Mirror) -> None:
    """A report that always finds something is one she stops believing."""
    _library(
        mirror,
        make_recipe(_uid(1), "Roast Chicken", categories=["CAT-ROAST"]),
        make_recipe(_uid(2), "Sourdough", categories=["CAT-SOURDOUGH"]),
    )

    assert health.is_tidy(health.report(mirror))
    assert health.jobs(health.report(mirror)) == []


def test_recipes_with_no_category_are_counted(mirror: Mirror) -> None:
    _library(
        mirror,
        make_recipe(_uid(1), "Nowhere", categories=[]),
        make_recipe(_uid(2), "Also Nowhere", categories=[]),
        make_recipe(_uid(3), "Filed", categories=["CAT-ROAST"]),
    )

    found = {f.kind: f.recipes for f in health.report(mirror)}
    assert found["uncategorised"] == 2


def test_filed_only_at_a_root_is_a_different_problem(mirror: Mirror) -> None:
    """Uncategorised is a hole; filed loosely may well have been deliberate."""
    _library(
        mirror,
        make_recipe(_uid(1), "Loose", categories=["CAT-MAINS"]),
        make_recipe(_uid(2), "Snug", categories=["CAT-ROAST"]),
    )

    found = {f.kind: f.recipes for f in health.report(mirror)}
    assert found["filed_loosely"] == 1
    assert "uncategorised" not in found


def test_a_leaf_category_is_not_loose_just_because_it_is_top_level(
    mirror: Mirror,
) -> None:
    """A root with no children below it is where a recipe belongs, not above it."""
    mirror.put_categories(
        [{"uid": "CAT-FLAT", "name": "Odds", "parent_uid": None, "order_flag": 0}]
    )
    mirror.put_recipe(make_recipe(_uid(1), "Fine", categories=["CAT-FLAT"]))
    mirror.assign_handles()

    assert health.is_tidy(health.report(mirror))


def test_a_hole_beats_a_preference_on_a_tie(mirror: Mirror) -> None:
    """Same count, so uncategorised has to come first."""
    _library(
        mirror,
        make_recipe(_uid(1), "A", categories=[]),
        make_recipe(_uid(2), "B", categories=["CAT-MAINS"]),
    )

    assert [f.kind for f in health.jobs(health.report(mirror))] == [
        "uncategorised",
        "filed_loosely",
    ]


def test_the_biggest_job_comes_first(mirror: Mirror) -> None:
    _library(
        mirror,
        make_recipe(_uid(1), "A", categories=["CAT-MAINS"]),
        make_recipe(_uid(2), "B", categories=["CAT-MAINS"]),
        make_recipe(_uid(3), "C", categories=[]),
    )

    assert health.jobs(health.report(mirror))[0].kind == "filed_loosely"


def test_only_two_jobs_are_offered(mirror: Mirror) -> None:
    """Three lines, not a dashboard."""
    _library(
        mirror,
        make_recipe(_uid(1), "A", categories=[]),
        make_recipe(_uid(2), "Same Name", categories=["CAT-MAINS"]),
        make_recipe(_uid(3), "same name", categories=["CAT-ROAST"]),
    )

    assert len(health.jobs(health.report(mirror))) <= health.SHOWN


def test_near_identical_titles_are_surfaced(mirror: Mirror) -> None:
    _library(
        mirror,
        make_recipe(_uid(1), "Mum's Lasagne", categories=["CAT-ROAST"]),
        make_recipe(_uid(2), "mums lasagne", categories=["CAT-ROAST"]),
    )

    found = {f.kind: f.recipes for f in health.report(mirror)}
    assert found["possible_duplicates"] == 2


def test_thin_categories_are_information_never_a_job(mirror: Mirror) -> None:
    """An empty category is a fact about her scheme, not a mistake to fix.

    And a library whose only finding is one of these is tidy: information does
    not make work.
    """
    _library(mirror, make_recipe(_uid(1), "One", categories=["CAT-ROAST"]))

    findings = health.report(mirror)
    thin = next(f for f in findings if f.kind == "thin_categories")
    assert thin.actionable is False
    assert thin.kind not in {job.kind for job in health.jobs(findings)}
    assert health.is_tidy(findings)


def test_the_report_is_instant_and_dispatches_nothing(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Only clustering needs the agent, and only once she has picked a job."""
    runner.invoke(app, ["sync"])
    seeded.requests.clear()

    result = runner.invoke(app, ["health"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert result.exit_code == 0
    # No recipe bodies fetched: it read what was already downloaded.
    assert not [p for _m, p in seeded.requests if "/sync/recipe/" in p]


def test_the_report_says_when_there_is_nothing_to_do(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    envelope = envelope_of(runner.invoke(app, ["health"]).stdout)

    # The seeded library has an uncategorised recipe, so this is not tidy —
    # what matters is that `tidy` is a fact the skill can act on.
    assert envelope["data"]["tidy"] is False
    assert envelope["data"]["jobs"]


def test_a_trashed_recipe_is_not_untidiness(mirror: Mirror) -> None:
    """She threw it out; it is not a hole in her library."""
    _library(
        mirror,
        make_recipe(_uid(1), "Kept", categories=["CAT-ROAST"]),
        make_recipe(_uid(2), "Thrown Out", categories=[], in_trash=True),
    )

    assert health.is_tidy(health.report(mirror))


def test_nothing_the_report_found_goes_unsaid(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A finding in neither list would vanish, and the third line closes on it."""
    runner.invoke(app, ["sync"])

    data = envelope_of(runner.invoke(app, ["health"]).stdout)["data"]

    said = {job["kind"] for job in data["jobs"]} | {
        also["kind"] for also in data["also"]
    }
    with Mirror(store.mirror_path()) as mirror:
        found = {finding.kind for finding in health.report(mirror)}
    assert found == said


def test_a_job_beyond_the_top_two_is_still_mentioned(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Three lines is what is *offered*, not what is admitted to existing."""
    runner.invoke(app, ["sync"])

    data = envelope_of(runner.invoke(app, ["health"]).stdout)["data"]

    beyond = [also for also in data["also"] if also["actionable"]]
    assert all("recipes" in entry for entry in beyond)
