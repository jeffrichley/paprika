"""The harness's own guarantees, because a fake nobody checks is a fake nobody trusts.

These do not mirror ``src/`` and are not meant to: they assert the two safety
properties every other test leans on, and that the fake reproduces the API's
pathologies rather than an idealised version of them.
"""

from __future__ import annotations

import socket
from pathlib import Path

import httpx
import pytest

from paprika_core import http
from paprika_core.errors import PaprikaError
from paprika_core.http import PaprikaClient
from tests.conftest import NetworkAccessError
from tests.fake_paprika import RECIPE_FIELDS, TOKEN, FakePaprika
from tests.library import CATEGORY_TREE, make_recipe


def test_the_network_guard_fires_on_a_real_socket() -> None:
    with pytest.raises(NetworkAccessError):
        socket.create_connection(("example.com", 443))

    with pytest.raises(NetworkAccessError):
        socket.socket().connect(("example.com", 443))


def test_the_fake_is_injected_without_a_test_asking() -> None:
    """The transport seam is autouse, so an unfaked path cannot reach the wire."""
    assert http.TRANSPORT is not None


def test_an_unrecognised_user_agent_is_refused_at_a_200(fake: FakePaprika) -> None:
    """The v2 gate. Getting this wrong looks like a client that reads nothing."""
    with httpx.Client(
        base_url="https://www.paprikaapp.com",
        transport=fake.transport(),
        headers={"User-Agent": "curl/8.0"},
    ) as raw:
        response = raw.get("/api/v2/sync/status/")

    assert response.status_code == 200
    assert response.json()["error"]["message"] == "Unrecognized client."


def test_there_is_no_bulk_recipe_endpoint(signed_in: Path, seeded: FakePaprika) -> None:
    """The index returns stubs; bodies cost one request each."""
    stubs = PaprikaClient(token=TOKEN).get("/api/v2/sync/recipes/", "listing")

    assert stubs
    for stub in stubs:
        assert set(stub) == {"uid", "hash"}


def test_the_plural_recipes_route_is_a_500(signed_in: Path) -> None:
    """``/sync/recipes/`` is the web clipper's scraper, not a bulk write."""
    with pytest.raises(PaprikaError):
        PaprikaClient(token=TOKEN)._post_object("/api/v2/sync/recipes/", [], "writing")


def test_there_is_no_delete_verb(fake: FakePaprika) -> None:
    with httpx.Client(
        base_url="https://www.paprikaapp.com", transport=fake.transport()
    ) as raw:
        response = raw.request("DELETE", "/api/v2/sync/groceries/ABC/")

    assert response.status_code == 404


def test_status_holds_counters_rather_than_counts(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A counter that looks like a count is the trap, so the fixture refuses to."""
    counters = PaprikaClient(token=TOKEN).get("/api/v2/sync/status/", "checking")

    assert counters["recipes"] != len(seeded.recipes)


def test_a_trashed_recipe_stays_on_the_wire_and_stays_readable(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """``in_trash`` is not removal. The v2 recipe object has no ``deleted`` field."""
    client = PaprikaClient(token=TOKEN)
    trashed = next(uid for uid, r in seeded.recipes.items() if r["in_trash"])

    stubs = client.get("/api/v2/sync/recipes/", "listing")

    assert any(stub["uid"] == trashed for stub in stubs)
    assert client.get(f"/api/v2/sync/recipe/{trashed}/", "reading")["in_trash"] is True


def test_removal_leaves_no_tombstone(signed_in: Path, seeded: FakePaprika) -> None:
    """A removed recipe is simply absent; only a moved counter says so."""
    client = PaprikaClient(token=TOKEN)
    gone = next(iter(seeded.recipes))
    before = client.get("/api/v2/sync/recipes/", "listing")

    del seeded.recipes[gone]
    seeded.counters["recipes"] += 1

    after = client.get("/api/v2/sync/recipes/", "listing")
    assert len(after) == len(before) - 1
    # Nothing in the collection marks it as ever having existed.
    assert all(stub["uid"] != gone for stub in after)


def test_the_reference_recipe_carries_every_field() -> None:
    """Built on the real object, including the seven nobody documented."""
    recipe = make_recipe("8F2A1C4E-11D3-4A1B-9C3D-1A2B3C4D5E6F", "Anything")

    assert set(recipe) == set(RECIPE_FIELDS)
    assert len(RECIPE_FIELDS) == 35
    for undocumented in (
        "cook_minutes",
        "prep_minutes",
        "total_minutes",
        "servings_min",
        "servings_max",
        "cookbook_uid",
        "metadata_version",
    ):
        assert undocumented in recipe


def test_the_reference_recipe_keeps_its_free_text_twins_as_null() -> None:
    """A field currently ``null`` in live data is the easiest one to drop."""
    recipe = make_recipe("8F2A1C4E-11D3-4A1B-9C3D-1A2B3C4D5E6F", "Anything")

    assert recipe["description"] is None
    assert recipe["on_grocery_list"] is None
    # The three photo fields are null, never "".
    assert (recipe["photo"], recipe["photo_hash"], recipe["photo_large"]) == (
        None,
        None,
        None,
    )


def test_the_reference_category_tree_is_three_levels_deep() -> None:
    by_uid = {category["uid"]: category for category in CATEGORY_TREE}
    depths = []
    for category in CATEGORY_TREE:
        depth = 0
        parent = category["parent_uid"]
        while parent:
            depth += 1
            parent = by_uid[parent]["parent_uid"]
        depths.append(depth)

    assert max(depths) == 2
    assert sum(1 for c in CATEGORY_TREE if c["parent_uid"] is None) > 1
