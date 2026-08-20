"""Re-filing hundreds of recipes in groups that share a destination.

One group is one screen and one yes, which is what makes eighty names a
legitimate confirmation: for re-filing specifically, a recipe's **name** is
enough to judge by, so eighty names are eighty words she can scan rather than
eighty pages she would have to read.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()


def _handles(fragments: list[str]) -> list[str]:
    """Return handles for recipes named by fragments of their titles.

    Args:
        fragments: Parts of recipe titles.

    Returns:
        list[str]: Their handles.
    """
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    return [
        str(next(line for line in lines if fragment in line).split(" | ")[0])
        for fragment in fragments
    ]


def test_a_whole_group_is_filed_in_one_run(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    group = _handles(["Aunt Ruth", "Seared Cod"])

    result = runner.invoke(
        app, ["write", "category", "file", *group, "--into", "Seafood"]
    )

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert result.exit_code == 0
    assert envelope["changed"] == {"recipes": 2}
    assert len(set(envelope["data"]["saved"])) == 2


def test_filing_only_ever_adds(signed_in: Path, seeded: FakePaprika) -> None:
    """A Run never removes filing she did on purpose."""
    runner.invoke(app, ["sync"])
    before = next(
        list(r["categories"])
        for r in seeded.recipes.values()
        if r["name"] == "Roast Lemon Chicken"
    )
    group = _handles(["Roast Lemon Chicken"])

    runner.invoke(app, ["write", "category", "file", *group, "--into", "Seafood"])

    after = next(
        r["categories"]
        for r in seeded.recipes.values()
        if r["name"] == "Roast Lemon Chicken"
    )
    assert set(before).issubset(set(after))
    assert len(after) == len(before) + 1


def test_a_group_is_its_own_run_so_undo_reverses_that_group(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    first = _handles(["Aunt Ruth"])
    second = _handles(["Seared Cod"])
    runner.invoke(app, ["write", "category", "file", *first, "--into", "Bread"])
    runner.invoke(app, ["write", "category", "file", *second, "--into", "Baking"])

    runner.invoke(app, ["write", "undo"])

    # The second group came back; the first was a different yes and stands.
    cod = next(r for r in seeded.recipes.values() if r["name"].startswith("Seared"))
    ruth = next(r for r in seeded.recipes.values() if "Ruth" in r["name"])
    assert "CAT-BAKING" not in cod["categories"]
    assert "CAT-BREAD" in ruth["categories"]


def test_a_group_that_starts_failing_stops_and_names_what_did_not_land(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    group = _handles(["Aunt Ruth", "Seared Cod", "Weeknight"])
    seeded.fail_writes_after = 1

    result = runner.invoke(
        app, ["write", "category", "file", *group, "--into", "Baking"]
    )

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 1
    assert envelope["complete"] is False
    assert envelope["changed"] == {"recipes": 1}
    assert envelope["data"]["not_saved"]


def test_a_new_category_must_name_its_parent(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A flat new top level is what she was trying to get away from."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["write", "category", "create", "--name", "Weeknight"])

    assert result.exit_code != 0
    assert seeded.category_writes == []


def test_a_new_category_goes_under_an_existing_one(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        [
            "write",
            "category",
            "create",
            "--name",
            "Weeknight",
            "--parent",
            "Main Dishes",
        ],
    )

    assert result.exit_code == 0
    written = seeded.category_writes[-1][0]
    assert written["name"] == "Weeknight"
    assert written["parent_uid"] == "CAT-MAINS"


def test_a_parent_she_does_not_have_is_refused(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        ["write", "category", "create", "--name", "X", "--parent", "Nonsense"],
    )

    assert result.exit_code == 1
    assert seeded.category_writes == []
    assert "Nonsense" in envelope_of(result.stdout)["error"]["message"]


def test_a_category_she_already_has_is_not_added_twice(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app,
        [
            "write",
            "category",
            "create",
            "--name",
            "Seafood",
            "--parent",
            "Main Dishes",
        ],
    )

    assert result.exit_code == 1
    assert seeded.category_writes == []


def test_a_new_category_can_be_undone(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(
        app,
        [
            "write",
            "category",
            "create",
            "--name",
            "Weeknight",
            "--parent",
            "Main Dishes",
        ],
    )
    assert any(c["name"] == "Weeknight" for c in seeded.categories)

    runner.invoke(app, ["write", "undo"])

    assert not any(c["name"] == "Weeknight" for c in seeded.categories)


def test_there_is_no_way_to_delete_a_category(signed_in: Path) -> None:
    """Her scheme wins. A command that can dismantle her tree has no caller."""
    from tests.test_write_cli import _commands_at

    assert "delete" not in _commands_at("write", "category")
    assert _commands_at("write", "category") == {"create", "file"}


def test_filing_a_group_tells_her_phone_once(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Notify fires at a resting point — the end of a group — never per write."""
    runner.invoke(app, ["sync"])
    group = _handles(["Aunt Ruth", "Seared Cod"])
    seeded.notified = 0

    runner.invoke(
        app, ["write", "category", "file", *group, "--into", "Baking", "--done"]
    )

    assert seeded.notified == 1
