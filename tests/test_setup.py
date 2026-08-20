"""Setup state — recorded, never inferred, and four states rather than three.

Deriving "set up" from whether a file exists means every future setup step
silently redefines what complete means. Worse, it collapses *unreadable* into
*never set up*: a corrupt or locked store would tell a user of many months that
she has never set this up, and send her back to the beginning.

So the completed steps are written down, and a store that cannot be read is its
own answer.
"""

from __future__ import annotations

from pathlib import Path

from paprika_core import setup, store
from tests.fake_paprika import GOOD_EMAIL, GOOD_PASSWORD, FakePaprika


def test_a_fresh_machine_has_never_been_set_up(paprika_home: Path) -> None:
    assert setup.read().state is setup.State.NEVER


def test_credentials_alone_are_not_finished(paprika_home: Path) -> None:
    """Resumable setup means "incomplete" is a real state, not a missing file."""
    setup.record(setup.Step.CREDENTIALS)

    read = setup.read()

    assert read.state is setup.State.INCOMPLETE
    assert setup.Step.CREDENTIALS in read.done
    assert setup.Step.LIBRARY in read.missing


def test_every_step_recorded_is_set_up(paprika_home: Path) -> None:
    for step in setup.REQUIRED:
        setup.record(step)

    read = setup.read()

    assert read.state is setup.State.READY
    assert read.missing == ()


def test_a_store_that_cannot_be_read_is_its_own_state(paprika_home: Path) -> None:
    """The failure #11 names: a corrupt store must never read as "never set up"."""
    (paprika_home / "state.toml").write_text("this is not [ toml", encoding="utf-8")

    assert setup.read().state is setup.State.UNREADABLE


def test_an_unreadable_store_is_never_mistaken_for_a_fresh_one(
    paprika_home: Path,
) -> None:
    assert setup.read().state is setup.State.NEVER

    (paprika_home / "state.toml").write_text("broken = [", encoding="utf-8")

    assert setup.read().state is not setup.State.NEVER


def test_recording_the_same_step_twice_is_harmless(paprika_home: Path) -> None:
    setup.record(setup.Step.CREDENTIALS)
    setup.record(setup.Step.CREDENTIALS)

    assert setup.read().done == (setup.Step.CREDENTIALS,)


def test_recording_a_step_leaves_the_token_alone(paprika_home: Path) -> None:
    """The token and the progress share a file, so one must not clobber the other."""
    store.save_token("a-session")

    setup.record(setup.Step.LIBRARY)

    assert store.read_token() == "a-session"
    assert setup.Step.LIBRARY in setup.read().done


def test_recording_a_step_keeps_hand_written_comments(paprika_home: Path) -> None:
    (paprika_home / "state.toml").write_text(
        "# Jeff wrote this by hand\nnote = 'keep me'\n", encoding="utf-8"
    )

    setup.record(setup.Step.CREDENTIALS)

    text = (paprika_home / "state.toml").read_text()
    assert "# Jeff wrote this by hand" in text
    assert "keep me" in text


def test_credentials_are_written_owner_only(paprika_home: Path) -> None:
    """Her password sits at rest, so the file it sits in is the only guard."""
    setup.save_credentials(GOOD_EMAIL, GOOD_PASSWORD)

    env = paprika_home / ".env"
    assert env.stat().st_mode & 0o777 == 0o600
    assert store.credentials() == (GOOD_EMAIL, GOOD_PASSWORD)


def test_saving_credentials_records_the_step(paprika_home: Path) -> None:
    setup.save_credentials(GOOD_EMAIL, GOOD_PASSWORD)

    assert setup.Step.CREDENTIALS in setup.read().done


def test_credentials_land_in_their_own_file_not_beside_the_token(
    paprika_home: Path,
) -> None:
    """Refreshing a session must never be able to clobber a password."""
    setup.save_credentials(GOOD_EMAIL, GOOD_PASSWORD)
    store.save_token("a-session")

    assert store.credentials() == (GOOD_EMAIL, GOOD_PASSWORD)
    assert "PAPRIKA_PASSWORD" not in (paprika_home / "state.toml").read_text()
    assert "a-session" not in (paprika_home / ".env").read_text()


def test_the_written_file_explains_itself(paprika_home: Path) -> None:
    """One hand-editable file is a repair hatch, and a repair hatch needs comments."""
    setup.save_credentials(GOOD_EMAIL, GOOD_PASSWORD)

    text = (paprika_home / ".env").read_text()
    assert text.lstrip().startswith("#")


def test_saving_credentials_replaces_rather_than_appends(paprika_home: Path) -> None:
    setup.save_credentials("old@example.com", "old-password")
    setup.save_credentials(GOOD_EMAIL, GOOD_PASSWORD)

    assert store.credentials() == (GOOD_EMAIL, GOOD_PASSWORD)
    assert "old-password" not in (paprika_home / ".env").read_text()


def test_setup_is_resumable_and_says_what_is_left(
    credentials_present: Path, seeded: FakePaprika
) -> None:
    """A closed laptop must not cost her the whole download."""
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    runner.invoke(app, ["login"])

    envelope = envelope_of(runner.invoke(app, ["status"]).stdout)
    assert envelope["data"]["setup"] == "incomplete"
    assert envelope["data"]["still_to_do"] == ["library"]
    # And it can say how long the part that is left will take.
    assert envelope["data"]["estimated_seconds"] is not None

    runner.invoke(app, ["sync"])

    assert envelope_of(runner.invoke(app, ["status"]).stdout)["data"]["setup"] == (
        "set_up"
    )


def test_an_interrupted_first_download_resumes(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """What already landed stays landed, and the rest is what gets fetched."""
    import pytest as _pytest

    from paprika_core import sync
    from paprika_core.mirror import Mirror
    from paprika_core.session import sign_in

    def stop_after_two(done: int, total: int) -> None:
        if done == 2:
            raise KeyboardInterrupt

    with Mirror(store.mirror_path()) as first, _pytest.raises(KeyboardInterrupt):
        sync.cold_sync(sign_in(), first, progress=stop_after_two)

    seeded.requests.clear()
    with Mirror(store.mirror_path()) as second:
        sync.cold_sync(sign_in(), second)

    fetched = [p for m, p in seeded.requests if m == "GET" and "/sync/recipe/" in p]
    assert len(fetched) == len(seeded.recipes) - 2


def test_every_command_gives_one_not_set_up_message(paprika_home: Path) -> None:
    """Produced by the core, so no skill has to remember to say it."""
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    messages = set()
    for argv in (
        ["sync"],
        ["login"],
        ["recipe", "index"],
        ["write", "recipe", "set", "abc123", "--set", "notes=x"],
    ):
        envelope = envelope_of(runner.invoke(app, argv).stdout)
        assert envelope["ok"] is False, argv
        if envelope["error"]["code"] == "not_set_up":
            messages.add(envelope["error"]["message"])

    assert len(messages) == 1


def test_no_setup_failure_reaches_the_session_as_a_traceback(
    paprika_home: Path,
) -> None:
    from typer.testing import CliRunner

    from paprika_core.cli import app

    runner = CliRunner()
    (paprika_home / "state.toml").write_text("broken = [", encoding="utf-8")

    for argv in (["status"], ["sync"], ["recipe", "index"], ["login"]):
        result = runner.invoke(app, argv)
        assert "Traceback" not in result.stdout, argv
        assert "Error:" not in result.stdout, argv


def test_an_expired_session_never_reaches_her(
    credentials_present: Path, seeded: FakePaprika
) -> None:
    """She never sees a login error; it is renewed underneath her."""
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    runner.invoke(app, ["sync"])
    store.save_token("expired")

    envelope = envelope_of(runner.invoke(app, ["recipe", "index", "--fresh"]).stdout)

    assert envelope["ok"] is True
    assert store.read_token() != "expired"


def test_the_credentials_command_refuses_a_password_on_the_command_line(
    paprika_home: Path,
) -> None:
    """A password in an argument is visible in the process list to everyone."""
    from typer.testing import CliRunner

    from paprika_core.cli import app
    from tests.test_cli import envelope_of

    runner = CliRunner()
    result = runner.invoke(app, ["setup", "credentials", "--email", GOOD_EMAIL])

    assert result.exit_code == 1
    assert envelope_of(result.stdout)["error"]["code"] == "refused_locally"
    assert not (paprika_home / ".env").exists()


def test_the_credentials_command_takes_the_password_privately(
    paprika_home: Path,
) -> None:
    from typer.testing import CliRunner

    from paprika_core.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["setup", "credentials", "--email", GOOD_EMAIL, "--password-stdin"],
        input=GOOD_PASSWORD + "\n",
    )

    assert result.exit_code == 0
    assert store.credentials() == (GOOD_EMAIL, GOOD_PASSWORD)
    assert setup.read().state is setup.State.INCOMPLETE
