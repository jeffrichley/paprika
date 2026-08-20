"""Duplicates — surfaced, never merged.

Merging decides which fields survive, and that decision is hers alone. The
action offered is *keep this one, trash the rest*, so her recovery is Paprika's
own trash rather than anything of ours that has to survive.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.library import make_recipe
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()
ONE = "AAAA1111-0000-4000-8000-000000000001"
TWO = "BBBB2222-0000-4000-8000-000000000002"


def _a_cluster(seeded: FakePaprika, **second: object) -> list[str]:
    """Seed two recipes that look like copies and return their handles.

    Args:
        seeded: The fake account.
        **second: What differs about the second one.

    Returns:
        list[str]: Both handles.
    """
    seeded.recipes[ONE] = make_recipe(
        ONE, "Mum's Lasagne", ingredients="500g beef\n1 onion", total_time="1 hr"
    )
    seeded.recipes[TWO] = make_recipe(
        TWO, "Mums Lasagne", ingredients="500g beef\n1 onion", total_time="1 hr"
    )
    seeded.recipes[TWO].update(second)
    runner.invoke(app, ["sync"])
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    return [
        str(next(line for line in lines if name in line).split(" | ")[0])
        for name in ("Mum's Lasagne", "Mums Lasagne")
    ]


def test_a_cluster_is_shown_with_its_differences(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A name is not enough to judge by here; she is choosing what survives."""
    cluster = _a_cluster(seeded, total_time="45 min", notes="Nana's version")

    result = runner.invoke(app, ["recipe", "compare", *cluster])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert result.exit_code == 0
    differs = envelope["data"]["recipes"][0]["differs"]
    assert "total_time" in differs
    assert "notes" in differs


def test_only_what_differs_is_shown(signed_in: Path, seeded: FakePaprika) -> None:
    """A screen should show the decision, not two whole recipes side by side."""
    cluster = _a_cluster(seeded, total_time="45 min")

    data = envelope_of(runner.invoke(app, ["recipe", "compare", *cluster]).stdout)[
        "data"
    ]

    assert list(data["recipes"][0]["differs"]) == ["total_time"]
    assert "ingredients" in data["same"]


def test_structural_evidence_asserts(signed_in: Path, seeded: FakePaprika) -> None:
    """Identical ingredients and method is a fact that can be stated."""
    cluster = _a_cluster(seeded)

    data = envelope_of(runner.invoke(app, ["recipe", "compare", *cluster]).stdout)[
        "data"
    ]

    assert data["identical"] is True


def test_similarity_only_asks(signed_in: Path, seeded: FakePaprika) -> None:
    """Same title, different ingredients is a real question, not a duplicate."""
    cluster = _a_cluster(seeded, ingredients="500g pork\n2 onions\n1 tin tomatoes")

    data = envelope_of(runner.invoke(app, ["recipe", "compare", *cluster]).stdout)[
        "data"
    ]

    assert data["identical"] is False
    assert "ingredients" in data["recipes"][0]["differs"]


def test_no_similarity_score_is_ever_produced(
    signed_in: Path, seeded: FakePaprika
) -> None:
    cluster = _a_cluster(seeded, total_time="45 min")

    rendered = runner.invoke(app, ["recipe", "compare", *cluster]).stdout.casefold()

    for leak in ("score", "confidence", "similarity", "%", "likelihood"):
        assert leak not in rendered


def test_keeping_one_and_trashing_the_rest_is_one_run(
    signed_in: Path, seeded: FakePaprika
) -> None:
    cluster = _a_cluster(seeded)

    result = runner.invoke(app, ["write", "recipe", "trash", cluster[1], "--done"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["changed"] == {"recipes": 1}
    assert seeded.recipes[TWO]["in_trash"] is True
    assert seeded.recipes[ONE]["in_trash"] is False


def test_several_can_be_trashed_together(signed_in: Path, seeded: FakePaprika) -> None:
    """Keep this one and trash the rest is one act, so it is one Run."""
    cluster = _a_cluster(seeded)
    third = "CCCC3333-0000-4000-8000-000000000003"
    seeded.recipes[third] = make_recipe(third, "Mum s Lasagne")
    runner.invoke(app, ["sync"])
    lines = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    extra = str(next(line for line in lines if "Mum s" in line).split(" | ")[0])

    envelope = envelope_of(
        runner.invoke(app, ["write", "recipe", "trash", cluster[1], extra]).stdout
    )

    assert envelope["changed"] == {"recipes": 2}


def test_a_trashed_duplicate_still_syncs_and_is_filtered(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Recovery is Paprika's own trash, so it must stay there and stay readable."""
    cluster = _a_cluster(seeded)
    runner.invoke(app, ["write", "recipe", "trash", cluster[1]])

    # Still on the wire, because `in_trash` is not removal.
    assert TWO in seeded.recipes
    # And out of her Library, because she threw it away.
    lines = envelope_of(runner.invoke(app, ["recipe", "index", "--fresh"]).stdout)[
        "data"
    ]["recipes"]
    assert not any("Mums Lasagne" in line for line in lines)


def test_trashing_a_duplicate_can_be_undone(
    signed_in: Path, seeded: FakePaprika
) -> None:
    cluster = _a_cluster(seeded)
    runner.invoke(app, ["write", "recipe", "trash", cluster[1]])

    runner.invoke(app, ["write", "undo"])

    assert seeded.recipes[TWO]["in_trash"] is False


def test_no_code_anywhere_can_perform_a_field_level_merge() -> None:
    """Deciding which fields survive is hers alone, everywhere in the plugin.

    Checked against **identifiers**, not prose. Scanning the text flagged
    `merge-only` in the Pantry — which means the opposite, that nothing is ever
    removed — and flagged a rule whose "never" sat on the line above. What binds
    is whether any code can do it, and none can if nothing is named for it.
    """
    import ast

    root = Path(__file__).resolve().parent.parent
    offenders: list[str] = []
    for path in sorted((root / "src").glob("**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            named = getattr(node, "name", None) or getattr(node, "id", None)
            if isinstance(named, str) and "merge" in named.casefold():
                offenders.append(f"{path.name}: {named}")

    assert not offenders, "something can merge:\n" + "\n".join(offenders)


def test_the_action_offered_is_trash_rather_than_merge() -> None:
    """The roster is the offer. There is no merge command to reach for."""
    from tests.test_write_cli import _commands_at

    assert "merge" not in _commands_at("write", "recipe")
    assert "trash" in _commands_at("write", "recipe")
