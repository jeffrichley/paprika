"""The `paprika write …` surface, and what a Run reports when it stops.

Every mutating command sits under one prefix, so a write reads as a write in the
transcript she and Jeff both scroll, greps as one in the log, and is deniable
with a single rule rather than a list somebody has to maintain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()


def _handle_of(name_fragment: str) -> str:
    """Return the handle of a mirrored recipe by part of its name.

    Args:
        name_fragment: Something in the recipe's title.

    Returns:
        str: Its handle.
    """
    envelope = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)
    line = next(
        entry for entry in envelope["data"]["recipes"] if name_fragment in entry
    )
    return str(line.split(" | ")[0])


def test_a_write_changes_only_what_was_asked_for(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """An edit touches one thing and nothing else about the recipe changes."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    before = next(
        dict(r) for r in seeded.recipes.values() if r["name"] == "Roast Lemon Chicken"
    )

    result = runner.invoke(app, ["write", "recipe", "set", handle, "--set", "rating=5"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert result.exit_code == 0
    assert envelope["changed"] == {"recipes": 1}

    sent = seeded.writes[-1]
    assert sent["rating"] == 5
    for field in ("name", "ingredients", "directions", "categories", "source"):
        assert sent[field] == before[field]


def test_the_envelope_names_the_kind_that_moved(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A map by kind, because the single word "library" flattened what mattered."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Weeknight Sourdough")

    envelope = envelope_of(
        runner.invoke(
            app, ["write", "recipe", "set", handle, "--set", "notes=x"]
        ).stdout
    )

    assert envelope["changed"] == {"recipes": 1}
    assert_no_mechanics(envelope)


def test_re_filing_only_ever_adds_a_category(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A Run must never undo filing she did on purpose."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    before = next(
        list(r["categories"])
        for r in seeded.recipes.values()
        if r["name"] == "Roast Lemon Chicken"
    )

    runner.invoke(
        app, ["write", "recipe", "set", handle, "--add", "categories=Seafood"]
    )

    sent = seeded.writes[-1]["categories"]
    assert set(before).issubset(set(sent))
    assert len(sent) == len(before) + 1


def test_a_category_is_named_rather_than_identified(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """She says "Seafood"; what Paprika stores never crosses into the session."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Aunt Ruth")

    result = runner.invoke(
        app, ["write", "recipe", "set", handle, "--add", "categories=Seafood"]
    )

    assert result.exit_code == 0
    assert "CAT-SEAFOOD" in seeded.writes[-1]["categories"]
    assert_no_mechanics(envelope_of(result.stdout))


def test_an_unknown_category_is_refused_before_anything_is_sent(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Aunt Ruth")

    result = runner.invoke(
        app, ["write", "recipe", "set", handle, "--add", "categories=Nonsense"]
    )

    assert result.exit_code == 1
    assert envelope_of(result.stdout)["changed"] == {}
    assert seeded.writes == []


def test_the_mechanics_cannot_be_set_by_name(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A patch may not reach identity, the change marker, or removal."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Aunt Ruth")

    for forbidden in ("uid=X", "hash=" + "a" * 64, "deleted=true", "in_trash=true"):
        result = runner.invoke(
            app, ["write", "recipe", "set", handle, "--set", forbidden]
        )
        assert result.exit_code == 1, forbidden
        assert seeded.writes == [], forbidden


def test_trashing_is_recoverable_in_her_own_app(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """What she calls deleting is `in_trash`, so recovery never needs our snapshot."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Aunt Ruth")

    result = runner.invoke(app, ["write", "recipe", "trash", handle])

    assert result.exit_code == 0
    assert seeded.writes[-1]["in_trash"] is True
    # Still on the wire, still readable — trashing is not removal.
    assert any(r["name"] == "Aunt Ruth's Casserole" for r in seeded.recipes.values())


def test_the_two_commands_that_must_not_exist(signed_in: Path) -> None:
    """No `write recipe remove`, and no `write category delete`."""
    assert runner.invoke(app, ["write", "recipe", "remove", "abc123"]).exit_code != 0
    assert runner.invoke(app, ["write", "category", "delete", "Dinner"]).exit_code != 0


def test_a_write_returns_a_run_that_later_writes_can_join(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    first_handle = _handle_of("Roast Lemon Chicken")
    second_handle = _handle_of("Weeknight Sourdough")

    first = envelope_of(
        runner.invoke(
            app, ["write", "recipe", "set", first_handle, "--set", "notes=a"]
        ).stdout
    )
    run_id = first["data"]["run"]

    second = envelope_of(
        runner.invoke(
            app,
            [
                "write",
                "recipe",
                "set",
                second_handle,
                "--set",
                "notes=b",
                "--run",
                run_id,
            ],
        ).stdout
    )

    assert second["data"]["run"] == run_id
    assert second["changed"] == {"recipes": 2}


def test_undo_puts_back_what_was_just_done(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "name=Wrong"])
    assert any(r["name"] == "Wrong" for r in seeded.recipes.values())

    result = runner.invoke(app, ["write", "undo"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["changed"] == {"recipes": 1}
    assert any(r["name"] == "Roast Lemon Chicken" for r in seeded.recipes.values())


def test_undo_with_nothing_to_undo_says_so_plainly(signed_in: Path) -> None:
    result = runner.invoke(app, ["write", "undo"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 1
    assert envelope["error"]["code"] == "nothing_to_undo"
    assert_no_mechanics(envelope)


def test_undo_list_describes_runs_by_what_they_changed(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "notes=x"])

    envelope = envelope_of(runner.invoke(app, ["undo", "list"]).stdout)

    runs = envelope["data"]["runs"]
    assert runs[0]["changed"] == {"recipes": 1}
    assert runs[0]["names"] == ["Roast Lemon Chicken"]
    # Never by id. She has never seen one and never will.
    assert "run" not in runs[0]


def test_a_write_without_a_mirror_is_refused_kindly(signed_in: Path) -> None:
    result = runner.invoke(
        app, ["write", "recipe", "set", "abc123", "--set", "notes=x"]
    )

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 1
    assert envelope["changed"] == {}
    assert "Traceback" not in result.stdout


def test_every_mutating_command_sits_under_one_prefix() -> None:
    """`Bash(paprika write:*)` must be sufficient to deny every write.

    ADR 0005 requires the Scan to hold no write tool at all. A structural prefix
    is the version of that rule which survives a contributor, so the roster is
    asserted rather than remembered — `undo` in particular writes to her library
    and must not sit outside the fence.
    """
    # `sync` is deliberately outside the prefix: it moves the Mirror, not her
    # data, and a prefix that means two things means neither.
    assert _commands_at() == {
        "login",
        "sync",
        "status",
        "setup",
        "recipe",
        "write",
        "undo",
        "profile",
    }
    # Setup writes to this machine, never to her library, so it stays outside.
    assert _commands_at("setup") == {"credentials"}
    assert _commands_at("write") == {"recipe", "undo", "profile"}
    assert _commands_at("write", "profile") == {"set"}
    # Reading her household changes nothing, so it stays outside the prefix.
    assert _commands_at("profile") == {"show"}
    assert _commands_at("write", "recipe") == {"set", "trash"}
    # Reading what could be put back changes nothing, so it stays outside.
    assert _commands_at("undo") == {"list"}
    # And the reads are reads.
    assert _commands_at("recipe") == {"index", "get", "search"}


def test_the_write_prefix_covers_every_command_that_can_change_her_library(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Nothing outside `write` reaches Paprika with a POST."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    runner.invoke(app, ["write", "recipe", "set", handle, "--set", "notes=x"])
    seeded.requests.clear()

    for argv in (["status"], ["recipe", "index"], ["undo", "list"], ["sync"]):
        runner.invoke(app, argv)

    assert [p for m, p in seeded.requests if m == "POST"] == []


def _commands_at(*path: str) -> set[str]:
    """Return the command names a caller can type at a point in the tree.

    Walks the real command tree Typer builds, rather than its registration
    lists, because a command registered without an explicit name gets one
    derived from its function and would otherwise be invisible here.

    Args:
        *path: The subcommands to walk down first.

    Returns:
        set[str]: The names available at that point.
    """
    node: Any = typer.main.get_command(app)
    for step in path:
        node = node.commands[step]
    return set(getattr(node, "commands", {}))
