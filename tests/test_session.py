"""Signing in, and renewing a session without her ever hearing about it."""

from __future__ import annotations

from pathlib import Path

import pytest

from paprika_core import store
from paprika_core.errors import Code, PaprikaError
from paprika_core.http import PaprikaClient, is_a_stale_session
from paprika_core.session import sign_in
from tests.fake_paprika import TOKEN, FakePaprika


def test_a_held_token_is_reused_rather_than_re_earned(
    signed_in: Path, fake: FakePaprika
) -> None:
    client = sign_in()

    assert client.token == TOKEN
    assert not any(path.endswith("/login/") for _, path in fake.requests)


def test_no_credentials_is_not_set_up(paprika_home: Path) -> None:
    with pytest.raises(PaprikaError) as caught:
        sign_in()

    assert caught.value.code == Code.NOT_SET_UP


def test_a_stale_token_is_renewed_and_the_request_retried(
    credentials_present: Path, seeded: FakePaprika
) -> None:
    """One request retried, not the caller's whole run."""
    store.save_token("stale")
    client = sign_in()

    counters = client.get("/api/v2/sync/status/", "checking")

    assert counters
    assert store.read_token() == TOKEN


def test_a_session_that_stays_stale_fails_rather_than_looping(
    credentials_present: Path, fake: FakePaprika, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.save_token("stale")
    client = sign_in()
    # Renewal "succeeds" but hands back a token Paprika still won't take.
    monkeypatch.setattr(client, "_renew", lambda: "still-stale")

    with pytest.raises(PaprikaError):
        client.get("/api/v2/sync/status/", "checking")


def test_a_refused_request_is_not_mistaken_for_a_stale_session() -> None:
    """Anything else Paprika refused stays refused. It must never be re-sent."""
    refused = PaprikaError(
        Code.PAPRIKA_REFUSED, "Paprika wouldn't do that.", status=500, said=""
    )

    assert is_a_stale_session(refused) is False


def test_a_401_and_a_session_message_both_count_as_stale() -> None:
    by_status = PaprikaError(Code.PAPRIKA_REFUSED, "x", status=401, said="")
    by_wording = PaprikaError(
        Code.PAPRIKA_REFUSED, "x", status=200, said="Invalid session."
    )

    assert is_a_stale_session(by_status) is True
    assert is_a_stale_session(by_wording) is True


def test_a_client_without_a_renewal_hook_simply_fails(fake: FakePaprika) -> None:
    with pytest.raises(PaprikaError):
        PaprikaClient(token="stale").get("/api/v2/sync/status/", "checking")
