"""The chokepoint. This is the file that stops us damaging her library.

The failure this exists to prevent is not hypothetical: a shipping Paprika
server blanks rating, categories, source and photos on **every** edit, and
propagates the damage to every synced device, because it assembles a payload
from a field list it believes is complete. Issue #8 found it; ADR 0004 is the
answer.

So these tests assert data, never call sequences. What reached Paprika is the
only thing that matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from paprika_core import undo, write
from paprika_core.errors import PaprikaError
from paprika_core.session import sign_in
from tests.fake_paprika import RECIPE_FIELDS, FakePaprika


def _a_recipe(fake: FakePaprika) -> str:
    """Return the uid of a recipe that is in her Library.

    Args:
        fake: The seeded fake account.

    Returns:
        str: A uid.
    """
    return next(uid for uid, r in fake.recipes.items() if not r["in_trash"])


def test_every_field_survives_a_write(signed_in: Path, seeded: FakePaprika) -> None:
    """All thirty-five, including the seven nobody documented. The #8 failure."""
    uid = _a_recipe(seeded)
    before = dict(seeded.recipes[uid])

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("servings", "6"), run=run)

    sent = seeded.writes[-1]
    for field in RECIPE_FIELDS:
        if field == "photo_url":
            continue
        assert field in sent, f"{field} was dropped on write"
    for field in ("rating", "categories", "source", "photo", "photo_large"):
        assert sent[field] == before[field], f"{field} was damaged on write"


def test_the_undocumented_fields_survive_as_null(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A field that is null in live data is the easiest one in the world to drop."""
    uid = _a_recipe(seeded)

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "x"), run=run)

    sent = seeded.writes[-1]
    for undocumented in (
        "cook_minutes",
        "prep_minutes",
        "total_minutes",
        "servings_min",
        "servings_max",
        "cookbook_uid",
        "metadata_version",
    ):
        assert undocumented in sent
        assert sent[undocumented] is None


def test_the_change_marker_is_regenerated_and_never_echoed(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Echoing the fetched one produces a write her phone never pulls."""
    uid = _a_recipe(seeded)
    fetched = seeded.recipes[uid]["hash"]

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "x"), run=run)

    sent = seeded.writes[-1]["hash"]
    assert sent != fetched
    assert len(sent) == 64
    assert all(c in "0123456789abcdef" for c in sent)


def test_two_writes_produce_two_different_change_markers(
    signed_in: Path, seeded: FakePaprika
) -> None:
    uid = _a_recipe(seeded)

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "a"), run=run)
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "b"), run=run)

    assert seeded.writes[-1]["hash"] != seeded.writes[-2]["hash"]


def test_the_expiring_photo_link_is_stripped(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Response-only, and it goes stale within hours."""
    uid = _a_recipe(seeded)
    seeded.recipes[uid]["photo_url"] = "https://example.com/signed?expires=soon"

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "x"), run=run)

    assert "photo_url" not in seeded.writes[-1]


def test_a_write_reads_immediately_before_it_posts(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Read-modify-write on a freshly fetched object, with no exceptions."""
    uid = _a_recipe(seeded)
    seeded.requests.clear()

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "x"), run=run)

    verbs = [(m, p) for m, p in seeded.requests if uid in p]
    assert verbs[0][0] == "GET"
    assert verbs[-1][0] == "POST"


def test_a_change_made_elsewhere_is_not_clobbered(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The re-read is what collapses "cache disagrees" into "cache is stale"."""
    uid = _a_recipe(seeded)
    # She edited it on her phone since the Mirror was filled.
    seeded.recipes[uid]["source"] = "Her Phone"

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("notes", "x"), run=run)

    assert seeded.writes[-1]["source"] == "Her Phone"


def test_a_mutation_that_invents_a_field_is_refused(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Callers may change keys. They may never choose the key set."""
    uid = _a_recipe(seeded)

    with pytest.raises(PaprikaError), undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("invented", 1), run=run)

    assert seeded.writes == []


def test_a_mutation_that_drops_a_field_is_refused(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Validation is client-side, because a rejected write names no field."""
    uid = _a_recipe(seeded)

    with pytest.raises(PaprikaError), undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.pop("rating"), run=run)

    assert seeded.writes == []


def test_a_blank_photo_field_is_refused_before_it_reaches_paprika(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The three photo fields must be null, never "". Paprika answers a bare 500."""
    uid = _a_recipe(seeded)

    with pytest.raises(PaprikaError), undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("photo", ""), run=run)

    assert seeded.writes == []


def test_an_assembled_object_cannot_be_handed_to_the_chokepoint(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """It takes a function that edits the fetched object. A payload is not one.

    This is the seam ADR 0004 calls unenforceable in its Python form: here it is
    enforced by the signature, and nothing reaches Paprika when it is violated.
    """
    uid = _a_recipe(seeded)
    assembled: Any = {"uid": uid, "name": "assembled by a caller"}

    with pytest.raises(TypeError), undo.open_run() as run:
        write.write(sign_in(), uid, assembled, run=run)

    assert seeded.writes == []


def test_the_raw_post_is_reachable_from_one_module_only() -> None:
    """ADR 0004's "no exceptions" is unenforceable unless it is enforced."""
    source = Path(__file__).resolve().parent.parent / "src" / "paprika_core"
    callers = {
        module.name
        for module in source.glob("**/*.py")
        if "_post_object" in module.read_text(encoding="utf-8")
    }

    assert callers == {"http.py", "write.py"}


def test_a_deleted_object_is_restored_by_reposting_its_pre_image(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Verified live against a real account, and the reason undo can exist at all."""
    uid = _a_recipe(seeded)
    original: dict[str, Any] = dict(seeded.recipes[uid])

    with undo.open_run() as run:
        write.write(sign_in(), uid, lambda r: r.__setitem__("deleted", True), run=run)
        pre_image = run.pre_image("recipes", uid)

    assert pre_image is not None
    with undo.open_run() as run:
        write.restore(sign_in(), pre_image, run=run)

    restored = seeded.recipes[uid]
    for field in RECIPE_FIELDS:
        if field in ("hash", "photo_url", "deleted"):
            continue
        assert restored[field] == original[field], f"{field} did not come back"
