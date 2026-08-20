"""``~/.paprika`` — credentials she owns, machine state we own."""

from __future__ import annotations

from pathlib import Path

import pytest

from paprika_core import store
from paprika_core.errors import Code, PaprikaError


def test_the_store_survives_a_corrupt_state_file(paprika_home: Path) -> None:
    """A broken state file is a state to rebuild, not a reason to fail a command."""
    (paprika_home / "state.toml").write_text("this is not [ toml", encoding="utf-8")

    assert store.read_token() is None

    store.save_token("fresh")
    assert store.read_token() == "fresh"


def test_the_state_file_is_owner_only(paprika_home: Path) -> None:
    store.save_token("secret")

    assert (paprika_home / "state.toml").stat().st_mode & 0o777 == 0o600


def test_clearing_a_token_leaves_the_rest_of_the_file(paprika_home: Path) -> None:
    """Refreshing a token must never clobber something repaired by hand."""
    (paprika_home / "state.toml").write_text(
        '# her note\nsetup_finished = true\ntoken = "old"\n', encoding="utf-8"
    )

    store.clear_token()

    text = (paprika_home / "state.toml").read_text()
    assert store.read_token() is None
    assert "setup_finished = true" in text
    assert "# her note" in text


def test_credentials_ignore_comments_and_quotes(paprika_home: Path) -> None:
    (paprika_home / ".env").write_text(
        "# a comment\nPAPRIKA_EMAIL=\"her@example.com\"\nPAPRIKA_PASSWORD='pw'\n",
        encoding="utf-8",
    )

    assert store.credentials() == ("her@example.com", "pw")


def test_a_blank_password_is_not_set_up(paprika_home: Path) -> None:
    (paprika_home / ".env").write_text(
        "PAPRIKA_EMAIL=her@example.com\nPAPRIKA_PASSWORD=\n", encoding="utf-8"
    )

    with pytest.raises(PaprikaError) as caught:
        store.credentials()

    assert caught.value.code == Code.NOT_SET_UP


def test_a_missing_env_file_is_not_set_up(paprika_home: Path) -> None:
    with pytest.raises(PaprikaError) as caught:
        store.credentials()

    assert caught.value.code == Code.NOT_SET_UP
