"""Reading the Library well enough to judge it, with no second judge anywhere.

The model is the semantic engine. It reads the whole index — about sixteen
tokens a recipe, so five hundred cost roughly eight thousand — shortlists from
it, and pulls a handful of bodies to judge ingredients against.

What the index deliberately cannot answer is an ingredient-level question across
the whole Library at once, so `recipe search` exists for exactly that and
nothing more.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()


def _handle_of(fragment: str) -> str:
    """Return the handle of a mirrored recipe by part of its name.

    Args:
        fragment: Something in the recipe's title.

    Returns:
        str: Its handle.
    """
    envelope = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)
    line = next(e for e in envelope["data"]["recipes"] if fragment in e)
    return str(line.split(" | ")[0])


def test_a_body_can_be_pulled_to_judge_it(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")

    result = runner.invoke(app, ["recipe", "get", handle])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert result.exit_code == 0
    recipe = envelope["data"]["recipe"]
    assert recipe["name"] == "Roast Lemon Chicken"
    assert "ingredients" in recipe
    assert "directions" in recipe


def test_a_pulled_body_carries_no_mechanics(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """She is handed a recipe, not Paprika's record of one."""
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")

    result = runner.invoke(app, ["recipe", "get", handle])

    envelope = envelope_of(result.stdout)
    assert_no_mechanics(envelope)
    recipe = envelope["data"]["recipe"]
    for mechanic in ("uid", "hash", "photo_url", "in_trash", "deleted", "photo_hash"):
        assert mechanic not in recipe
    # And the handle is how it is named, so a later change can aim at it.
    assert recipe["handle"] == handle


def test_a_pulled_body_names_her_categories(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")

    recipe = envelope_of(runner.invoke(app, ["recipe", "get", handle]).stdout)["data"][
        "recipe"
    ]

    assert "Roasts" in recipe["categories"]
    assert not any(name.startswith("CAT-") for name in recipe["categories"])


def test_several_bodies_come_back_in_one_call(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A shortlist is pulled at once rather than one round trip at a time."""
    runner.invoke(app, ["sync"])
    first = _handle_of("Roast Lemon Chicken")
    second = _handle_of("Weeknight Sourdough")

    envelope = envelope_of(runner.invoke(app, ["recipe", "get", first, second]).stdout)

    assert len(envelope["data"]["recipes"]) == 2


def test_an_unknown_handle_says_so_plainly(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["recipe", "get", "nosuch"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 1
    assert "Traceback" not in result.stdout
    assert_no_mechanics(envelope)


def test_search_answers_what_the_index_cannot(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """An ingredient-level question across the whole Library, with no fetching."""
    runner.invoke(app, ["sync"])
    seeded.requests.clear()

    envelope = envelope_of(runner.invoke(app, ["recipe", "search", "capers"]).stdout)

    assert len(envelope["data"]["recipes"]) == 1
    assert "Seared Cod" in envelope["data"]["recipes"][0]


def test_search_reads_the_mirror_rather_than_the_wire(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    seeded.requests.clear()

    runner.invoke(app, ["recipe", "search", "capers"])

    assert [p for m, p in seeded.requests if "/sync/recipe/" in p] == []


def test_search_finds_nothing_rather_than_something_close(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Lexical means lexical. Nothing here scores a near miss as a hit."""
    runner.invoke(app, ["sync"])

    envelope = envelope_of(runner.invoke(app, ["recipe", "search", "capirs"]).stdout)

    assert envelope["ok"] is True
    assert envelope["data"]["recipes"] == []


def test_search_ignores_what_she_trashed(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])

    envelope = envelope_of(runner.invoke(app, ["recipe", "search", "thing"]).stdout)

    assert not any("Threw Out" in line for line in envelope["data"]["recipes"])


def test_the_cli_cannot_return_a_web_result(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The never-blend rule stands on this: a blended list can only be built by hand.

    Every read serves the Mirror, so there is no command that could put a recipe
    from the internet into the same list as one of hers.
    """
    runner.invoke(app, ["sync"])

    for argv in (["recipe", "index"], ["recipe", "search", "chicken"]):
        envelope = envelope_of(runner.invoke(app, argv).stdout)
        for line in envelope["data"]["recipes"]:
            assert "http" not in line.casefold()
