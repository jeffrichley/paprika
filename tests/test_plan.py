"""The Plan — written where a plan can actually live, and never duplicated.

`menuitems` cannot hold a plan: it has no date, only an integer day offset, and
its recipe reference cannot be null — so falling back to it loses every date and
silently drops every meal she typed out rather than picked. `meals` is the
planner, and this is what keeps it honest.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()
MONDAY = "2026-08-31"


def _handle_of(fragment: str) -> str:
    """Return the handle of a mirrored recipe by part of its name.

    Args:
        fragment: Something in the recipe's title.

    Returns:
        str: Its handle.
    """
    envelope = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)
    return str(
        next(e for e in envelope["data"]["recipes"] if fragment in e).split(" | ")[0]
    )


def test_the_plan_is_read_back_in_her_language(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["plan", "show", "--from", "2026-08-24"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    meals = envelope["data"]["meals"]
    assert {"date": "2026-08-24", "slot": "dinner"}.items() <= meals[0].items()
    assert meals[0]["name"] == "Roast Lemon Chicken"


def test_a_meal_that_is_not_a_recipe_is_an_ordinary_case(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Free text is confirmed three ways in the research; it is not an edge case."""
    runner.invoke(app, ["sync"])

    meals = envelope_of(runner.invoke(app, ["plan", "show"]).stdout)["data"]["meals"]

    leftovers = next(m for m in meals if m["name"] == "Leftovers")
    assert leftovers["recipe"] is None


def test_a_night_is_planned_from_her_library(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")

    result = runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--recipe",
            handle,
        ],
    )

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["changed"] == {"plan": 1}
    written = seeded.meal_writes[-1][0]
    assert written["date"].startswith(MONDAY)
    assert written["type"] == 2
    assert written["name"] == "Roast Lemon Chicken"


def test_a_night_can_be_something_she_just_says(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "Takeaway",
        ],
    )

    written = seeded.meal_writes[-1][0]
    assert written["name"] == "Takeaway"
    assert written["recipe_uid"] is None


def test_a_meal_is_a_recipe_or_words_but_never_both_or_neither(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")

    both = runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--recipe",
            handle,
            "--name",
            "Takeaway",
        ],
    )
    neither = runner.invoke(
        app, ["write", "plan", "set", "--date", MONDAY, "--slot", "dinner"]
    )

    assert both.exit_code == 1
    assert neither.exit_code == 1
    assert seeded.meal_writes == []


def test_a_swap_replaces_rather_than_duplicating(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The real risk here is two dinners on Tuesday, not a lost one."""
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "First",
        ],
    )
    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "Second",
        ],
    )

    that_night = [m for m in seeded.meals if m["date"].startswith(MONDAY)]
    assert len(that_night) == 1
    assert that_night[0]["name"] == "Second"


def test_a_night_she_filled_on_her_phone_is_not_duplicated(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The Mirror may be seconds old; the write reconciles on the slot itself."""
    runner.invoke(app, ["sync"])
    # She adds it in the app after the Mirror was filled and before we write.
    from tests.library import make_meal

    seeded.meals.append(
        make_meal("22222222-0001-4A1B-9C3D-1A2B3C4D5E6F", MONDAY, "Hers From The App")
    )

    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "Ours",
        ],
    )

    that_night = [m for m in seeded.meals if m["date"].startswith(MONDAY)]
    assert len(that_night) == 1
    assert that_night[0]["name"] == "Ours"


def test_a_replaced_meal_keeps_the_fields_nobody_here_knows_about(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    seeded.meals[0]["something_we_have_never_heard_of"] = "keep me"

    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            "2026-08-24",
            "--slot",
            "dinner",
            "--name",
            "New",
        ],
    )

    assert seeded.meal_writes[-1][0]["something_we_have_never_heard_of"] == "keep me"


def test_a_night_can_be_emptied(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app, ["write", "plan", "clear", "--date", "2026-08-24", "--slot", "dinner"]
    )

    assert result.exit_code == 0
    assert envelope_of(result.stdout)["data"]["cleared"] == "Roast Lemon Chicken"
    assert not [m for m in seeded.meals if m["date"].startswith("2026-08-24")]


def test_the_saved_plan_reaches_her_phone(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])
    seeded.notified = 0

    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "X",
            "--done",
        ],
    )

    assert seeded.notified == 1


def test_seven_nights_do_not_buzz_her_phone_seven_times(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Once per finished piece of work, never per write."""
    runner.invoke(app, ["sync"])
    seeded.notified = 0

    first = envelope_of(
        runner.invoke(
            app,
            [
                "write",
                "plan",
                "set",
                "--date",
                MONDAY,
                "--slot",
                "dinner",
                "--name",
                "A",
            ],
        ).stdout
    )
    run_id = first["data"]["run"]
    for day, name in (("2026-09-01", "B"), ("2026-09-02", "C")):
        runner.invoke(
            app,
            [
                "write",
                "plan",
                "set",
                "--date",
                day,
                "--slot",
                "dinner",
                "--name",
                name,
                "--run",
                run_id,
            ],
        )
    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            "2026-09-03",
            "--slot",
            "dinner",
            "--name",
            "D",
            "--run",
            run_id,
            "--done",
        ],
    )

    assert seeded.notified == 1


def test_a_read_after_a_write_sees_what_was_just_written(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Our own write makes the Mirror stale, whatever the stamp last said."""
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "Just Written",
        ],
    )

    meals = envelope_of(runner.invoke(app, ["plan", "show", "--from", MONDAY]).stdout)[
        "data"
    ]["meals"]
    assert [m["name"] for m in meals] == ["Just Written"]


def test_a_failure_to_announce_is_not_a_failure_to_save(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Her plan is already saved; the announcement is fire-and-forget."""
    runner.invoke(app, ["sync"])
    seeded.refuse_notify = True

    result = runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "X",
            "--done",
        ],
    )

    assert result.exit_code == 0
    assert envelope_of(result.stdout)["changed"] == {"plan": 1}


def test_planning_a_night_can_be_undone(signed_in: Path, seeded: FakePaprika) -> None:
    """A slot filled from empty undoes to empty, not to something else."""
    runner.invoke(app, ["sync"])
    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            MONDAY,
            "--slot",
            "dinner",
            "--name",
            "Oops",
        ],
    )
    assert any(m["date"].startswith(MONDAY) for m in seeded.meals)

    result = runner.invoke(app, ["write", "undo"])

    assert result.exit_code == 0
    assert not [m for m in seeded.meals if m["date"].startswith(MONDAY)]


def test_a_swap_undoes_to_what_was_there_before(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            "2026-08-24",
            "--slot",
            "dinner",
            "--name",
            "Swapped",
        ],
    )

    runner.invoke(app, ["write", "undo"])

    that_night = [m for m in seeded.meals if m["date"].startswith("2026-08-24")]
    assert that_night[0]["name"] == "Roast Lemon Chicken"


def test_a_slot_she_did_not_name_is_refused(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        ["write", "plan", "set", "--date", MONDAY, "--slot", "brunch", "--name", "X"],
    )

    assert result.exit_code == 1
    assert seeded.meal_writes == []


def test_the_plan_never_reaches_the_menus_resource(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Falling back to menus loses every date and every free-text meal."""
    runner.invoke(app, ["sync"])
    runner.invoke(
        app,
        ["write", "plan", "set", "--date", MONDAY, "--slot", "dinner", "--name", "X"],
    )

    touched = {path for _method, path in seeded.requests}
    assert "/api/v2/sync/menus/" not in touched
    assert "/api/v2/sync/menuitems/" not in touched


def test_undoing_a_week_shows_the_week_as_it_now_is(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Undo changes Paprika, so a read after it must not serve the old picture."""
    runner.invoke(app, ["sync"])
    first = envelope_of(
        runner.invoke(
            app,
            [
                "write",
                "plan",
                "set",
                "--date",
                MONDAY,
                "--slot",
                "dinner",
                "--name",
                "A",
            ],
        ).stdout
    )
    runner.invoke(
        app,
        [
            "write",
            "plan",
            "set",
            "--date",
            "2026-09-01",
            "--slot",
            "dinner",
            "--name",
            "B",
            "--run",
            first["data"]["run"],
            "--done",
        ],
    )

    runner.invoke(app, ["write", "undo"])

    meals = envelope_of(
        runner.invoke(
            app, ["plan", "show", "--from", MONDAY, "--to", "2026-09-06"]
        ).stdout
    )["data"]["meals"]
    assert meals == []
