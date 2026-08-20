"""Invented recipes — the only Intake path whose source is us.

Which is why it is the only one that marks what it saves. A year from now the
question is where a recipe came from, and the mark is only an answer to that if
it cannot be forgotten, forged, or quietly removed.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import envelope_of

runner = CliRunner()


def _saved(seeded: FakePaprika, name: str) -> dict:
    """Return the recipe that was saved under a name.

    Args:
        seeded: The fake account.
        name: Its title.

    Returns:
        dict: The stored recipe.
    """
    return next(r for r in seeded.recipes.values() if r["name"] == name)


def test_an_invented_recipe_is_marked_as_ours(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        ["write", "recipe", "create", "--set", "name=Thursday Traybake", "--invented"],
    )

    assert result.exit_code == 0
    saved = _saved(seeded, "Thursday Traybake")
    assert "Created with Claude" in saved["source"]
    assert dt.date.today().isoformat() in saved["source"]


def test_the_mark_is_applied_by_the_command_not_by_whoever_calls_it(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A mark a caller can forget is a mark that means nothing a year later."""
    runner.invoke(app, ["sync"])

    # Nothing was said about the source; the flag alone is what marks it.
    runner.invoke(
        app, ["write", "recipe", "create", "--set", "name=Invented", "--invented"]
    )

    assert "Created with Claude" in _saved(seeded, "Invented")["source"]


def test_the_other_intake_paths_do_not_mark_anything(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A link and a dictation are hers. Only this one is ours."""
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "recipe",
            "create",
            "--set",
            "name=From A Blog",
            "--set",
            "source=Some Blog",
        ],
    )

    assert "Created with Claude" not in _saved(seeded, "From A Blog")["source"]


def test_the_mark_cannot_be_written_by_hand(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A caller that could forge it could put it on a recipe she wrote."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        [
            "write",
            "recipe",
            "create",
            "--set",
            "name=Pretender",
            "--set",
            "source=Created with Claude — 2020-01-01",
        ],
    )

    assert result.exit_code == 1
    assert seeded.writes == []


def test_the_mark_cannot_be_edited_away(signed_in: Path, seeded: FakePaprika) -> None:
    """Where a recipe came from is not something to change later."""
    runner.invoke(app, ["sync"])
    runner.invoke(
        app, ["write", "recipe", "create", "--set", "name=Ours", "--invented"]
    )
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    handle = str(next(line for line in lines if "Ours" in line).split(" | ")[0])

    result = runner.invoke(
        app, ["write", "recipe", "set", handle, "--set", "source=A Cookbook"]
    )

    assert result.exit_code == 1
    assert "Created with Claude" in _saved(seeded, "Ours")["source"]


def test_an_invented_recipe_is_otherwise_an_ordinary_recipe(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(
        app,
        [
            "write",
            "recipe",
            "create",
            "--set",
            "name=Thursday Traybake",
            "--set",
            "ingredients=6 chicken thighs\n2 lemons",
            "--set",
            "directions=Roast for 40 minutes.",
            "--invented",
        ],
    )

    saved = _saved(seeded, "Thursday Traybake")
    assert saved["ingredients"].startswith("6 chicken thighs")
    assert saved["in_trash"] is False


def test_an_invented_recipe_can_still_be_edited_otherwise(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The mark is permanent; the recipe is not frozen."""
    runner.invoke(app, ["sync"])
    runner.invoke(
        app, ["write", "recipe", "create", "--set", "name=Ours", "--invented"]
    )
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    handle = str(next(line for line in lines if "Ours" in line).split(" | ")[0])

    result = runner.invoke(
        app, ["write", "recipe", "set", handle, "--set", "servings=6"]
    )

    assert result.exit_code == 0
    assert _saved(seeded, "Ours")["servings"] == "6"


def test_an_invented_recipe_can_be_undone_like_any_other(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(
        app, ["write", "recipe", "create", "--set", "name=Regret", "--invented"]
    )

    runner.invoke(app, ["write", "undo"])

    assert not any(r["name"] == "Regret" for r in seeded.recipes.values())


def test_it_can_be_saved_inside_a_planning_run(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """She should not be ejected into another skill to invent a dish."""
    runner.invoke(app, ["sync"])

    created = envelope_of(
        runner.invoke(
            app,
            ["write", "recipe", "create", "--set", "name=Thursday Thing", "--invented"],
        ).stdout
    )
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    handle = str(
        next(line for line in lines if "Thursday Thing" in line).split(" | ")[0]
    )
    planned = envelope_of(
        runner.invoke(
            app,
            [
                "write",
                "plan",
                "set",
                "--date",
                "2026-08-27",
                "--slot",
                "dinner",
                "--recipe",
                handle,
                "--run",
                created["data"]["run"],
                "--done",
            ],
        ).stdout
    )

    # One Run covers inventing it and putting it on the night.
    assert planned["data"]["run"] == created["data"]["run"]
    assert planned["changed"] == {"recipes": 1, "plan": 1}
