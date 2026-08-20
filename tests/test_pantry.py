"""The Pantry — merge-only, names only, and the age is part of the fact.

A camera can say *this is here*; only she can say *this is gone*. Absence from a
photo, from a shopping list, or from a planned day that has passed is never
evidence of absence — the jar is behind the cereal.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from paprika_core.cli import app
from tests.fake_paprika import FakePaprika
from tests.test_cli import assert_envelope_shape, assert_no_mechanics, envelope_of

runner = CliRunner()


def _have(seeded: FakePaprika) -> set[str]:
    """Return what the account currently says she has in.

    Args:
        seeded: The fake account.

    Returns:
        set[str]: Ingredient names marked in stock.
    """
    return {i["ingredient"] for i in seeded.pantry if i["in_stock"]}


def test_the_pantry_is_read_back_with_its_age(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The age is part of the fact, so nothing can read one without the other."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["pantry", "list"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert {i["ingredient"] for i in envelope["data"]["have"]} == {"cumin", "rice"}
    assert "confirmed_days_ago" in envelope["data"]


def test_never_confirmed_is_not_confirmed_today(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    envelope = envelope_of(runner.invoke(app, ["pantry", "list"]).stdout)

    assert envelope["data"]["confirmed_days_ago"] is None


def test_confirming_makes_the_belief_young(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "confirm", "cumin"])

    envelope = envelope_of(runner.invoke(app, ["pantry", "list"]).stdout)
    assert envelope["data"]["confirmed_days_ago"] == 0.0


def test_a_shop_is_recorded_in_one_go(signed_in: Path, seeded: FakePaprika) -> None:
    """Eighty names she can scan in ten seconds are one legitimate yes."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(
        app, ["write", "pantry", "add", "black beans", "onions", "flour"]
    )

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["changed"] == {"pantry": 3}
    # One request carrying all of it, not one request each.
    assert len(seeded.pantry_writes) == 1
    assert {"black beans", "onions", "flour"} <= _have(seeded)


def test_an_aisle_comes_from_her_own_scheme(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Filing black beans under her Canned Goods reads her scheme, not ours."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "black beans"])

    written = next(
        e for e in seeded.pantry_writes[-1] if e["ingredient"] == "black beans"
    )
    assert written["aisle"] == "Canned Goods"


def test_an_unknown_ingredient_gets_no_aisle_rather_than_a_guess(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A missing aisle degrades the entry; it never blocks the write."""
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["write", "pantry", "add", "harissa"])

    assert result.exit_code == 0
    written = next(e for e in seeded.pantry_writes[-1] if e["ingredient"] == "harissa")
    assert written["aisle"] == ""
    assert "harissa" in _have(seeded)


def test_nothing_is_removed_for_not_being_mentioned(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Merge-only. A jar behind the cereal is not a jar that is gone."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "flour"])

    assert {"cumin", "rice"} <= _have(seeded)


def test_only_she_can_say_something_is_gone(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "gone", "rice"])

    assert "rice" not in _have(seeded)
    assert "cumin" in _have(seeded)


def test_saying_something_is_gone_keeps_its_history(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """It is flipped, not deleted, so having it again is not a fresh start."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "gone", "rice"])

    still_there = next(i for i in seeded.pantry if i["ingredient"] == "rice")
    assert still_there["in_stock"] is False
    assert still_there["aisle"] == "Dry Goods"


def test_having_something_again_is_a_flip_not_a_new_entry(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A fresh entry would orphan the aisle her account had learned for it."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "soy sauce"])

    matching = [i for i in seeded.pantry if i["ingredient"] == "soy sauce"]
    assert len(matching) == 1
    assert matching[0]["in_stock"] is True
    assert matching[0]["aisle"] == "Sauces"


def test_naming_something_she_never_had_as_gone_records_nothing(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """An out-of-stock entry for something she never had is a fact from nowhere."""
    runner.invoke(app, ["sync"])

    envelope = envelope_of(
        runner.invoke(app, ["write", "pantry", "gone", "saffron"]).stdout
    )

    assert envelope["changed"] == {}
    assert not any(i["ingredient"] == "saffron" for i in seeded.pantry)


def test_a_pantry_write_carries_no_purchase_date(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Nothing here knows when she bought it, and a made-up date looks like hers."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "flour"])

    written = next(e for e in seeded.pantry_writes[-1] if e["ingredient"] == "flour")
    assert "purchase_date" not in written


def test_a_pantry_write_carries_no_name_field(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """There is no such field. Groceries and pantry are not symmetric."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "flour"])

    assert all("name" not in e for e in seeded.pantry_writes[-1])


def test_a_pantry_write_invents_no_quantity(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A quantity is specificity in a field nothing reads, wrong within a week."""
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "flour"])

    written = next(e for e in seeded.pantry_writes[-1] if e["ingredient"] == "flour")
    assert written["quantity"] == ""
    assert written["has_expiration"] is False
    assert written["expiration_date"] is None


def test_a_shop_can_be_undone(signed_in: Path, seeded: FakePaprika) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["write", "pantry", "add", "flour", "harissa"])
    assert {"flour", "harissa"} <= _have(seeded)

    runner.invoke(app, ["write", "undo"])

    assert not {"flour", "harissa"} & _have(seeded)


def test_saying_something_is_gone_can_be_undone(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["write", "pantry", "gone", "rice"])

    runner.invoke(app, ["write", "undo"])

    assert "rice" in _have(seeded)


def test_a_read_after_a_shop_shows_the_shop(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    runner.invoke(app, ["write", "pantry", "add", "flour"])

    have = envelope_of(runner.invoke(app, ["pantry", "list"]).stdout)["data"]["have"]
    assert "flour" in {i["ingredient"] for i in have}
