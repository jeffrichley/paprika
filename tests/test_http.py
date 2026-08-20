"""The wire — where everything Paprika's API does wrong is handled.

These are the tests that would have caught the failures issue #8 found in six
existing clients: a status code trusted in either direction, a gzip body sniffed
wrong, an unrecognised client refused invisibly.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import httpx
import pytest

from paprika_core import http
from paprika_core.errors import Code, PaprikaError
from paprika_core.http import PaprikaClient
from tests.fake_paprika import GOOD_EMAIL, GOOD_PASSWORD, TOKEN, FakePaprika
from tests.library import make_recipe, sync_hash

A_UID = "0F9E8D7C-6B5A-4938-8271-605F4E3D2C1B"


def test_our_user_agent_prefix_matches_paprikas_own() -> None:
    """The v2 gate is a prefix match, so we can say who we are and still get in."""
    assert http.USER_AGENT.startswith("Paprika 3/")
    assert "paprika-plugin/" in http.USER_AGENT


def test_an_error_at_a_success_status_is_still_a_failure(fake: FakePaprika) -> None:
    """The pathology that makes "check the status code" insufficient."""
    client = PaprikaClient(token="not-the-token")

    with pytest.raises(PaprikaError) as caught:
        client.get("/api/v2/sync/status/", "checking")

    assert caught.value.code == Code.PAPRIKA_REFUSED
    assert caught.value.status == 200


def test_paprikas_own_wording_never_becomes_hers(fake: FakePaprika) -> None:
    client = PaprikaClient(token="not-the-token")

    with pytest.raises(PaprikaError) as caught:
        client.get("/api/v2/sync/status/", "checking")

    assert "Invalid session." not in caught.value.message
    # Kept, though — for the log and for deciding what to do about it.
    assert caught.value.said == "Invalid session."


def test_a_gzipped_response_is_read(fake: FakePaprika) -> None:
    """Responses may or may not be gzipped, and the header does not reliably say."""
    payload = gzip.compress(json.dumps({"result": {"ok": 1}}).encode("utf-8"))

    assert http.parse_body(httpx.Response(200, content=payload), "reading") == {"ok": 1}


def test_an_unreadable_body_at_a_success_status_says_so(fake: FakePaprika) -> None:
    with pytest.raises(PaprikaError) as caught:
        http.parse_body(httpx.Response(200, content=b"<html>nope</html>"), "reading")

    assert caught.value.code == Code.PAPRIKA_REFUSED
    assert "couldn't read" in caught.value.message


def test_a_failing_status_with_no_error_body_still_fails(fake: FakePaprika) -> None:
    with pytest.raises(PaprikaError) as caught:
        http.parse_body(httpx.Response(503, content=b""), "reading")

    assert caught.value.status == 503


def test_a_login_is_form_encoded(fake: FakePaprika) -> None:
    """Form-encoded against v1, which has neither the UA gate nor a receipt check."""
    client = PaprikaClient()

    assert client.login(GOOD_EMAIL, GOOD_PASSWORD) == TOKEN
    assert ("POST", "/api/v1/account/login/") in fake.requests


def test_a_rejected_login_is_told_apart_from_any_other_refusal(
    fake: FakePaprika,
) -> None:
    client = PaprikaClient()

    with pytest.raises(PaprikaError) as caught:
        client.login(GOOD_EMAIL, "wrong")

    assert caught.value.code == Code.CREDENTIALS_REJECTED


def test_an_unreachable_paprika_is_a_sentence_not_a_stack_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(http, "TRANSPORT", httpx.MockTransport(refuse))

    with pytest.raises(PaprikaError) as caught:
        PaprikaClient(token=TOKEN).get("/api/v2/sync/status/", "checking")

    assert caught.value.code == Code.PAPRIKA_UNREACHABLE
    assert "reach Paprika" in caught.value.message


def test_a_write_is_gzipped_json_in_a_multipart_data_part(
    signed_in: Path, fake: FakePaprika
) -> None:
    """The construction the API insists on, and the riskiest code in the plugin."""
    recipe = make_recipe(A_UID, "Whole Recipe")
    recipe.pop("photo_url")

    assert (
        PaprikaClient(token=TOKEN)._post_object(
            f"/api/v2/sync/recipe/{A_UID}/", recipe, "writing"
        )
        is True
    )
    assert fake.writes[-1]["name"] == "Whole Recipe"


def test_a_malformed_write_is_a_genuine_500(signed_in: Path) -> None:
    """A 500 naming no field is why a client has to validate before it posts."""
    with pytest.raises(PaprikaError) as caught:
        PaprikaClient(token=TOKEN)._post_object(
            f"/api/v2/sync/recipe/{A_UID}/", {"uid": A_UID, "name": "Half"}, "writing"
        )

    assert caught.value.code == Code.PAPRIKA_REFUSED
    assert caught.value.status == 500


def test_a_stale_hash_is_accepted_and_stored_as_sent(
    signed_in: Path, fake: FakePaprika
) -> None:
    """There is no compare-and-swap here, and the server never bumps the token."""
    recipe = make_recipe(A_UID, "Stale", hash=sync_hash("years-ago"))
    recipe.pop("photo_url")

    PaprikaClient(token=TOKEN)._post_object(
        f"/api/v2/sync/recipe/{A_UID}/", recipe, "writing"
    )

    assert fake.recipes[A_UID]["hash"] == sync_hash("years-ago")
