"""The Profile — hers to state, ours to remember, never inferred.

Three tiers by consequence, and flattening them is how a safety fact ends up
treated like a preference:

* **Allergies** are structured and matchable, because the filter has to be able
  to act on them. Household-wide, because the cook only gets one pot.
* **Dislikes and loves** are free text, per person. "Not a fan of mushrooms"
  needs no schema and loses meaning under one.
* **Targets** carry their direction in the field name, so nothing downstream can
  be tempted to render a goal minus a running total.

The distinction that must never blur: **absent is not knowing; empty is
concluding.** An allergy line that was never answered and one answered "none"
are different facts, and treating them alike is how a plan gets proposed as safe
on the strength of a question nobody asked.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from paprika_core import profile
from paprika_core.errors import Code, PaprikaError


def test_a_fresh_machine_knows_nothing_rather_than_nothing_being_wrong(
    paprika_home: Path,
) -> None:
    read = profile.read()

    assert read.allergies_answered is False
    assert read.allergies == ()
    assert read.people == {}


def test_being_told_there_are_none_is_different_from_never_asking(
    paprika_home: Path,
) -> None:
    """Absent is Claude not knowing. Empty is Claude concluding."""
    profile.record_no_allergies()

    read = profile.read()

    assert read.allergies_answered is True
    assert read.allergies == ()


def test_allergies_are_household_wide(paprika_home: Path) -> None:
    """The cook only gets one pot, so an allergy is not somebody's preference."""
    profile.apply("allergies+=peanuts")
    profile.apply("allergies+=shellfish")

    assert set(profile.read().allergies) == {"peanuts", "shellfish"}
    # And there is no per-person place to put one.
    with pytest.raises(PaprikaError):
        profile.apply("people.sam.allergies+=peanuts")


def test_an_allergy_is_recorded_in_a_form_the_filter_can_act_on(
    paprika_home: Path,
) -> None:
    profile.apply("allergies+=Peanut")

    # Normalised, so a filter matches on one spelling rather than her wording.
    assert profile.read().allergies == ("peanuts",)


def test_an_allergy_we_have_no_spelling_for_is_kept_anyway(
    paprika_home: Path,
) -> None:
    """This test used to assert the opposite, and the opposite was the bug.

    It read: *"Recording it as matchable when it is not is how a hollow answer
    looks safe."* The belief was that an unrecognised allergy stored beside
    recognised ones would look checked while going unchecked. The premise was
    false — **nothing is checked mechanically**. `normalise` has one caller,
    this write, and no code anywhere reads allergies to reject a recipe. All
    screening is a skill reading the primer and applying cooking judgement, and
    that treats every word alike.

    What the refusal actually produced is in #93: a real allergy pushed into
    `dislikes`, which is the field that *can* be traded against, and a household
    that could never answer the allergy question and so read as having none.
    """
    profile.apply("allergies+=nightshades")

    assert profile.read().allergies == ("nightshades",)
    assert profile.read().allergies_answered


def test_dislikes_are_free_text_and_per_person(paprika_home: Path) -> None:
    profile.apply("people.sam.dislikes+=okra")
    profile.apply("people.sam.dislikes+=anything too spicy")
    profile.apply("people.ellie.loves+=roast potatoes")

    read = profile.read()
    assert read.people["sam"].dislikes == ("okra", "anything too spicy")
    assert read.people["ellie"].loves == ("roast potatoes",)
    assert read.people["ellie"].dislikes == ()


def test_a_person_can_be_removed_from_a_list_they_are_on(
    paprika_home: Path,
) -> None:
    profile.apply("people.sam.dislikes+=okra")
    profile.apply("people.sam.dislikes-=okra")

    assert profile.read().people["sam"].dislikes == ()


def test_the_rhythm_of_the_week_is_hers_to_state(paprika_home: Path) -> None:
    profile.apply("rhythm.fast_nights+=tuesday")
    profile.apply("rhythm.household_size=4")

    read = profile.read()
    assert read.fast_nights == ("tuesday",)
    assert read.household_size == 4


def test_a_target_carries_its_direction_in_its_name(paprika_home: Path) -> None:
    profile.apply("targets.protein_leaning=higher")

    assert profile.read().targets == {"protein_leaning": "higher"}


def test_a_target_that_is_a_number_is_refused(paprika_home: Path) -> None:
    """Nothing may render a goal minus a running total, so no goal is storable."""
    with pytest.raises(PaprikaError) as caught:
        profile.apply("targets.protein=120")

    assert caught.value.code is Code.REFUSED_LOCALLY
    assert profile.read().targets == {}


def test_a_target_whose_name_does_not_carry_its_direction_is_refused(
    paprika_home: Path,
) -> None:
    """The framing lives in the field name, so a bare noun has nowhere to put it.

    Asserted separately from the numeric case, which the value check would catch
    on its own — this pins the rule about the *name*.
    """
    with pytest.raises(PaprikaError):
        profile.apply("targets.protein=higher")

    assert profile.read().targets == {}


def test_a_target_direction_has_to_be_a_direction(paprika_home: Path) -> None:
    with pytest.raises(PaprikaError):
        profile.apply("targets.protein_leaning=120g")


def test_a_machine_write_keeps_her_comments(paprika_home: Path) -> None:
    """A naive writer destroys her notes the way a naive post destroys `rating`."""
    profile.apply("allergies+=peanuts")
    path = paprika_home / "profile.toml"
    text = path.read_text()
    path.write_text(text + "\n# Max grew out of the egg thing in 2025\n")

    profile.apply("people.max.dislikes+=olives")

    after = path.read_text()
    assert "# Max grew out of the egg thing in 2025" in after
    assert "peanuts" in after
    assert "olives" in after


def test_the_file_explains_itself_to_whoever_opens_it(paprika_home: Path) -> None:
    """It is a repair hatch for the person who set this up, over the phone."""
    profile.apply("allergies+=peanuts")

    text = (paprika_home / "profile.toml").read_text()
    assert text.lstrip().startswith("#")
    assert "allergies" in text


def test_a_hand_mangled_profile_is_tolerated_rather_than_fatal(
    paprika_home: Path,
) -> None:
    """Hand-editable, so the core must not assume its writes are the only ones."""
    (paprika_home / "profile.toml").write_text("this is not [ toml", encoding="utf-8")

    read = profile.read()

    assert read.readable is False
    assert read.allergies_answered is False


def test_an_unreadable_profile_never_reports_an_allergy_it_cannot_see(
    paprika_home: Path,
) -> None:
    """Silence about a safety fact must not read as an all-clear."""
    profile.apply("allergies+=peanuts")
    (paprika_home / "profile.toml").write_text("broken = [", encoding="utf-8")

    read = profile.read()

    assert read.readable is False
    assert read.allergies_answered is False


def test_a_path_that_means_nothing_is_refused(paprika_home: Path) -> None:
    for expression in ("nonsense=1", "people.sam=x", "allergies.sam+=peanuts", "=x"):
        with pytest.raises(PaprikaError):
            profile.apply(expression)


def test_setting_a_list_outright_is_refused(paprika_home: Path) -> None:
    """A list is added to or taken from, so a whole-value write cannot flatten it."""
    profile.apply("people.sam.dislikes+=okra")

    with pytest.raises(PaprikaError):
        profile.apply("people.sam.dislikes=mushrooms")

    assert profile.read().people["sam"].dislikes == ("okra",)


def test_the_profile_is_the_only_hand_editable_file(paprika_home: Path) -> None:
    """Everything else says in its own header that it is ours."""
    from paprika_core import setup, store

    profile.apply("allergies+=peanuts")
    setup.save_credentials("her@example.com", "pw")
    store.save_token("a-session")

    hand_editable = [
        path
        for path in sorted(paprika_home.iterdir())
        if path.suffix == ".toml" and "machine" not in path.read_text().casefold()
    ]

    assert [path.name for path in hand_editable] == ["profile.toml"]


def test_the_read_exposes_no_file_mechanics(paprika_home: Path) -> None:
    """She is told what is known about her household, never where it is kept."""
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import assert_no_mechanics, envelope_of

    runner = CliRunner()
    runner.invoke(app, ["write", "profile", "set", "allergies+=peanuts"])

    result = runner.invoke(app, ["profile", "show"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["data"]["allergies"] == ["peanuts"]
    assert_no_mechanics(envelope)
    for leak in ("profile.toml", "/.paprika", "toml"):
        assert leak not in result.stdout


def test_a_profile_write_moves_nothing_in_paprika(
    paprika_home: Path,
) -> None:
    """Her household is hers, and it is not her Paprika library."""
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    envelope = envelope_of(
        runner.invoke(
            app, ["write", "profile", "set", "people.sam.dislikes+=okra"]
        ).stdout
    )

    assert envelope["ok"] is True
    assert envelope["changed"] == {}


def test_saying_there_are_no_allergies_is_an_answer(paprika_home: Path) -> None:
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    runner.invoke(app, ["write", "profile", "set", "--no-allergies"])

    data = envelope_of(runner.invoke(app, ["profile", "show"]).stdout)["data"]
    assert data["allergies_answered"] is True
    assert data["allergies"] == []


def test_an_allergy_with_no_name_at_all_is_refused_without_a_traceback(
    paprika_home: Path,
) -> None:
    """The only refusal left on this path, and it is about blankness.

    Was: an allergy we had no spelling for. That refusal is gone with #93.
    """
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    result = runner.invoke(app, ["write", "profile", "set", "allergies+=   "])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 1
    assert envelope["error"]["code"] == "refused_locally"
    assert "Traceback" not in result.stdout


def test_an_unusual_allergy_reaches_the_session_by_name(paprika_home: Path) -> None:
    """The whole point: the primer has to carry it, or nothing can act on it."""
    from paprika_core import primer, setup

    for step in setup.REQUIRED:
        setup.record(step)
    profile.apply("allergies+=tomatoes")

    lines = primer.facts(dt.date(2026, 8, 21))

    assert any("tomatoes" in line for line in lines), lines


# --- An allergy the plugin cannot name is still an allergy -------------------
#
# #93. The list of fourteen gated what could be *recorded*, in service of a
# filter that does not exist: `normalise` is called from one place, when
# writing, and nothing ever reads allergies to reject a recipe. The screening is
# the model reading the primer's allergy line and applying cooking judgement,
# and that works the same for any word.


def test_an_allergy_outside_the_common_list_is_recorded(paprika_home: Path) -> None:
    """Monica is allergic to tomatoes. That is the case this exists for."""
    profile.apply("allergies+=tomatoes")

    assert profile.read().allergies == ("tomatoes",)


def test_recording_one_settles_the_question(paprika_home: Path) -> None:
    """The second-order failure, and the worse of the two.

    While an unlistable allergy could not be recorded, a household holding one
    could never reach an answered state — so every plan asked again, and the way
    to stop being asked was to declare *no allergies*. That reads as a checked
    fact and is a lie. Being unable to record the truth was steering her into
    recording a falsehood.
    """
    before = profile.read()
    assert not before.allergies_answered

    profile.apply("allergies+=tomatoes")

    assert profile.read().allergies_answered


def test_a_spelling_we_know_still_lands_on_one_name(paprika_home: Path) -> None:
    """Canonicalising is still worth doing — it just is not a gate.

    Otherwise `dairy` and `milk` sit in the list as two separate allergies and
    the household looks like it has more constraints than it has.
    """
    profile.apply("allergies+=dairy")
    profile.apply("allergies+=milk")

    assert profile.read().allergies == ("milk",)


def test_what_she_typed_is_kept_when_we_do_not_know_it(paprika_home: Path) -> None:
    """Her words, tidied only of spacing and case. Never reinterpreted."""
    profile.apply("allergies+=  Nightshades  ")

    assert profile.read().allergies == ("nightshades",)


def test_an_allergy_is_still_never_per_person(paprika_home: Path) -> None:
    """Unchanged by all of this: the cook only gets one pot."""
    with pytest.raises(PaprikaError):
        profile.apply("people.monica.allergies+=tomatoes")
