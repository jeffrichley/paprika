"""Attaching a picture to a recipe that has none.

Two properties carry this feature, and they are the same two that carry every
other write. **Nothing else about the recipe moves** — a photo is delivered in
the same request as the whole object, so it is exactly the place a field could
be dropped without anyone noticing. And **it can be taken back**, which is why
replacing an existing photo is refused rather than supported: the Pre-image
holds JSON, and JSON cannot hold the bytes that were there before.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from paprika_core import photos
from paprika_core.cli import app
from tests.fake_paprika import FakePaprika

runner = CliRunner()


def _an_image(width: int = 900, height: int = 600, colour: str = "red") -> bytes:
    """Return a JPEG, as a photograph of a cookbook page would arrive.

    Args:
        width: How wide.
        height: How tall. Deliberately not square by default — a page is not.
        colour: What to fill it with.

    Returns:
        bytes: JPEG bytes.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="JPEG")
    return buffer.getvalue()


def _sent(seeded: FakePaprika) -> bytes:
    """Return the picture that actually arrived.

    Args:
        seeded: The fake.

    Returns:
        bytes: The JPEG. Asserted rather than defaulted — a test reaching here
            with no photo is a test that has already failed.
    """
    assert seeded.uploaded_photo is not None
    return seeded.uploaded_photo


def _handle_of(name: str) -> str:
    """Return the handle of a recipe by name.

    Args:
        name: What it is called.

    Returns:
        str: Its handle.
    """
    lines = json.loads(runner.invoke(app, ["recipe", "index"]).stdout)["data"][
        "recipes"
    ]
    return str(next(line.split("|")[0].strip() for line in lines if name in line))


# --- What gets made ----------------------------------------------------------


def test_the_thumbnail_is_square_and_the_size_paprika_s_own_clients_send() -> None:
    """280x280 is not our number to pick — it is the one already in the wild."""
    prepared = photos.prepare(_an_image(900, 600))

    made = Image.open(io.BytesIO(prepared.thumbnail))
    assert made.size == (photos.THUMBNAIL_EDGE, photos.THUMBNAIL_EDGE)
    assert made.format == "JPEG"


def test_the_hash_is_of_the_bytes_that_are_sent() -> None:
    """`photo_hash` describes the thumbnail, not the file she pointed at.

    Hashing the original would produce a value that agrees with nothing on the
    far side — true of a file, and wrong about the photo.
    """
    prepared = photos.prepare(_an_image())

    assert (
        prepared.thumbnail_hash
        == hashlib.sha256(prepared.thumbnail).hexdigest().upper()
    )


def test_a_wide_photograph_is_centre_cropped_rather_than_squashed() -> None:
    """A squashed page is unreadable in a way a cropped one is not."""
    tall = Image.new("RGB", (600, 900), "white")
    for y in range(400, 500):
        for x in range(600):
            tall.putpixel((x, y), (255, 0, 0))
    buffer = io.BytesIO()
    tall.save(buffer, format="JPEG")

    prepared = photos.prepare(buffer.getvalue())

    # The red band sat across the middle, so the middle is what survives.
    made = Image.open(io.BytesIO(prepared.thumbnail)).convert("RGB")
    middle = made.getpixel((photos.THUMBNAIL_EDGE // 2, photos.THUMBNAIL_EDGE // 2))
    assert isinstance(middle, tuple)
    assert middle[0] > 200


def test_something_that_is_not_a_picture_is_refused_before_anything_is_sent(
    signed_in: Path, seeded: FakePaprika, tmp_path: Path
) -> None:
    not_a_photo = tmp_path / "shopping.txt"
    not_a_photo.write_text("eggs, milk", encoding="utf-8")
    runner.invoke(app, ["sync"])
    before = len(seeded.writes)

    result = runner.invoke(
        app,
        [
            "write",
            "recipe",
            "photo",
            _handle_of("Roast Lemon Chicken"),
            "--file",
            str(not_a_photo),
        ],
    )

    envelope = json.loads(result.stdout)
    assert result.exit_code == 1
    assert envelope["changed"] == {}
    assert "Traceback" not in result.stdout
    assert len(seeded.writes) == before


# --- What lands --------------------------------------------------------------


def test_the_picture_arrives_in_the_same_request_as_the_recipe(
    signed_in: Path, seeded: FakePaprika, tmp_path: Path
) -> None:
    """One request, so a photo cannot land against a recipe that did not."""
    photo = tmp_path / "page.jpg"
    photo.write_bytes(_an_image())
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")

    result = runner.invoke(
        app, ["write", "recipe", "photo", handle, "--file", str(photo)]
    )

    assert result.exit_code == 0
    stored = next(
        r for r in seeded.recipes.values() if r["name"] == "Roast Lemon Chicken"
    )
    assert stored["photo"]
    assert stored["photo_hash"] == hashlib.sha256(_sent(seeded)).hexdigest().upper()


def test_attaching_a_photo_moves_nothing_else(
    signed_in: Path, seeded: FakePaprika, tmp_path: Path
) -> None:
    """The chokepoint property, at the one call site that sends a second part."""
    photo = tmp_path / "page.jpg"
    photo.write_bytes(_an_image())
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    before = dict(
        next(r for r in seeded.recipes.values() if r["name"] == "Roast Lemon Chicken")
    )

    runner.invoke(app, ["write", "recipe", "photo", handle, "--file", str(photo)])

    after = next(
        r for r in seeded.recipes.values() if r["name"] == "Roast Lemon Chicken"
    )
    moved = {field for field in before if before[field] != after[field]}
    # Only the two photo fields and the change marker may differ.
    assert moved <= {"photo", "photo_hash", "hash"}


def test_a_photo_can_be_taken_back(
    signed_in: Path, seeded: FakePaprika, tmp_path: Path
) -> None:
    """Undo returns the fields to null — never to `""`, which is a bare 500."""
    photo = tmp_path / "page.jpg"
    photo.write_bytes(_an_image())
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    runner.invoke(app, ["write", "recipe", "photo", handle, "--file", str(photo)])

    result = runner.invoke(app, ["write", "undo"])

    assert result.exit_code == 0
    stored = next(
        r for r in seeded.recipes.values() if r["name"] == "Roast Lemon Chicken"
    )
    assert stored["photo"] is None
    assert stored["photo_hash"] is None


def test_replacing_a_photo_is_refused_because_it_could_not_be_undone(
    signed_in: Path, seeded: FakePaprika, tmp_path: Path
) -> None:
    """The scope of #83, enforced where it cannot be forgotten.

    A Pre-image is JSON and cannot hold the bytes that were there before, and
    `photo_url` expires within hours — so a replaced photo has nothing to go
    back to. Refusing is the honest version of that, and the refusal says what
    to do instead rather than only saying no.
    """
    photo = tmp_path / "page.jpg"
    photo.write_bytes(_an_image())
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    runner.invoke(app, ["write", "recipe", "photo", handle, "--file", str(photo)])

    second = tmp_path / "other.jpg"
    second.write_bytes(_an_image(colour="blue"))
    result = runner.invoke(
        app, ["write", "recipe", "photo", handle, "--file", str(second)]
    )

    envelope = json.loads(result.stdout)
    assert result.exit_code == 1
    assert envelope["changed"] == {}
    assert "already has a picture" in envelope["error"]["message"]
    # And the first photo is untouched by the attempt.
    stored = next(
        r for r in seeded.recipes.values() if r["name"] == "Roast Lemon Chicken"
    )
    assert stored["photo_hash"] == hashlib.sha256(_sent(seeded)).hexdigest().upper()


def test_importing_the_package_does_not_pay_for_an_image_library() -> None:
    """Pillow costs about 40 ms to import and most sessions never touch a photo."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import paprika_core, sys; print('PIL' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_a_recipe_says_whether_it_has_a_picture(
    signed_in: Path, seeded: FakePaprika, tmp_path: Path
) -> None:
    """Writing a photo without being able to read one back is a blind spot.

    Found on a real library: `recipe get` exposed fourteen fields and none of
    them photo-shaped, so the field most visibly lost by a whole-object replace
    was the only one nothing could check.
    """
    runner.invoke(app, ["sync"])
    handle = _handle_of("Roast Lemon Chicken")
    before = json.loads(runner.invoke(app, ["recipe", "get", handle]).stdout)
    assert before["data"]["recipes"][0]["photo"] is None

    photo = tmp_path / "page.jpg"
    photo.write_bytes(_an_image())
    runner.invoke(app, ["write", "recipe", "photo", handle, "--file", str(photo)])

    after = json.loads(runner.invoke(app, ["recipe", "get", handle]).stdout)
    assert after["data"]["recipes"][0]["photo"]
