"""Drafts read out of files, in the disposable tier and out of her library.

Saving one is deliberately outside the write prefix, because a draft moves
nothing of hers — which is what lets the Reader hold no write tool and still
have somewhere to put what it read.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core import intake, store
from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_no_mechanics, envelope_of

runner = CliRunner()


def test_a_draft_is_kept_out_of_the_mirror(paprika_home: Path) -> None:
    """Work in progress and a stale copy of Paprika are different staleness."""
    intake.save("/pages/one.jpg", {"name": "Soda Bread"})

    assert intake.directory() != store.mirror_path().parent / "cache.sqlite3"
    assert intake.directory().name == "intake"
    assert (paprika_home / "intake").is_dir()


def test_a_draft_is_written_as_soon_as_it_is_read(paprika_home: Path) -> None:
    """Forty photographed pages is the worst thing here to have to do twice."""
    intake.save("/pages/one.jpg", {"name": "First"})

    assert [draft.fields["name"] for draft in intake.waiting()] == ["First"]

    intake.save("/pages/two.jpg", {"name": "Second"})

    assert len(intake.waiting()) == 2


def test_reading_the_same_file_again_replaces_its_draft(
    paprika_home: Path,
) -> None:
    intake.save("/pages/one.jpg", {"name": "First try"})
    intake.save("/pages/one.jpg", {"name": "Second try"})

    drafts = intake.waiting()
    assert len(drafts) == 1
    assert drafts[0].fields["name"] == "Second try"


def test_a_draft_carries_only_fields_a_recipe_has(paprika_home: Path) -> None:
    """A field invented on the far side of a dispatch cannot arrive by mention."""
    intake.save(
        "/pages/one.jpg",
        {"name": "Soda Bread", "ocr_confidence": "0.82", "page_box": "[1,2,3,4]"},
    )

    kept = intake.waiting()[0].fields
    assert "name" in kept
    assert "ocr_confidence" not in kept
    assert "page_box" not in kept


def test_a_gap_is_named_and_marked_in_the_text(paprika_home: Path) -> None:
    """It rides in the recipe's own text, which is what syncs to her phone."""
    intake.save(
        "/pages/one.jpg",
        {"ingredients": "200g flour\n[unreadable — check the book]\n1 tsp bicarb"},
        gaps=("one ingredient line",),
    )

    draft = intake.waiting()[0]
    assert draft.gaps == ("one ingredient line",)
    assert "[unreadable" in draft.fields["ingredients"]


def test_a_page_that_is_not_a_recipe_is_a_sentence_not_a_draft(
    paprika_home: Path,
) -> None:
    intake.save("/pages/cat.jpg", {}, unusable="this looks like a photo of a cat")

    draft = intake.waiting()[0]
    assert draft.unusable == "this looks like a photo of a cat"
    assert draft.fields == {}


def test_a_damaged_draft_costs_one_file_not_the_walk(paprika_home: Path) -> None:
    intake.save("/pages/one.jpg", {"name": "Fine"})
    broken = next(intake.directory().glob("*.json"))
    broken.write_text("{not json", encoding="utf-8")
    intake.save("/pages/two.jpg", {"name": "Also fine"})

    assert [draft.fields["name"] for draft in intake.waiting()] == ["Also fine"]


def test_a_walk_that_ends_clears_what_it_left(paprika_home: Path) -> None:
    intake.save("/pages/one.jpg", {"name": "One"})
    intake.save("/pages/two.jpg", {"name": "Two"})

    assert intake.clear() == 2
    assert intake.waiting() == []


def test_one_draft_can_be_dealt_with_on_its_own(paprika_home: Path) -> None:
    intake.save("/pages/one.jpg", {"name": "One"})
    intake.save("/pages/two.jpg", {"name": "Two"})

    intake.done("/pages/one.jpg")

    assert [draft.fields["name"] for draft in intake.waiting()] == ["Two"]


def test_the_reader_can_save_without_reaching_her_library(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Saving a draft is outside the write prefix, and touches nothing of hers."""
    seeded.requests.clear()

    result = runner.invoke(
        app,
        [
            "intake",
            "save",
            "--source",
            "/pages/one.jpg",
            "--set",
            "name=Soda Bread",
            "--gap",
            "one ingredient line",
        ],
    )

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["changed"] == {}
    assert seeded.writes == []
    assert seeded.requests == []


def test_the_listing_says_which_are_clean(signed_in: Path) -> None:
    """The clean lane first is the skill's business; this says which are which."""
    runner.invoke(app, ["intake", "save", "--source", "/a.jpg", "--set", "name=Clean"])
    runner.invoke(
        app,
        [
            "intake",
            "save",
            "--source",
            "/b.jpg",
            "--set",
            "name=Gapped",
            "--gap",
            "a line",
        ],
    )

    envelope = envelope_of(runner.invoke(app, ["intake", "list"]).stdout)

    assert envelope["data"]["count"] == 2
    assert envelope["data"]["clean"] == 1
    assert_no_mechanics(envelope)


def test_a_malformed_field_is_refused_without_a_traceback(signed_in: Path) -> None:
    result = runner.invoke(
        app, ["intake", "save", "--source", "/a.jpg", "--set", "nonsense"]
    )

    assert result.exit_code == 1
    assert "Traceback" not in result.stdout


def test_clearing_needs_to_be_asked_for_explicitly(signed_in: Path) -> None:
    runner.invoke(app, ["intake", "save", "--source", "/a.jpg", "--set", "name=A"])

    vague = runner.invoke(app, ["intake", "done"])

    assert vague.exit_code == 1
    assert len(intake.waiting()) == 1
