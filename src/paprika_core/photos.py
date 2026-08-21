"""Turning a file she pointed at into the bytes Paprika expects.

A recipe carries **two** pictures and only one of them is settled. The recipe's
own ``photo`` is a square thumbnail delivered as a second multipart part in the
same request as the recipe JSON — documented, confirmed, and what this module
makes. The full-size gallery picture is a separate object at
``/api/v2/sync/photo/{uid}/`` whose *field set is written down nowhere*, and
this API answers a malformed write with a bare 500. Guessing a key set against
that is how you corrupt someone's library, so the gallery half is deliberately
absent rather than half-built.

Two numbers here are not ours to choose. **280x280** and **JPEG quality 85** are
what Paprika's own clients send; picking anything else would be inventing a
convention for an interface that already has one.

Nothing in this module reaches the network, and nothing in it decides whether a
write may happen. It converts bytes, and the chokepoint does the rest.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from paprika_core.errors import Code, PaprikaError

if TYPE_CHECKING:  # pragma: no cover
    pass

#: The edge of the square Paprika's own clients send.
THUMBNAIL_EDGE = 280

#: The quality they send it at.
THUMBNAIL_QUALITY = 85

#: How big a file we will even open. A photograph of a page is a few megabytes;
#: anything past this is a mistake worth naming rather than a wait worth having.
MOST_BYTES = 40 * 1024 * 1024


@dataclass(frozen=True)
class Prepared:
    """A picture, ready to send.

    Attributes:
        thumbnail: The square JPEG that goes up as ``photo_upload``.
        thumbnail_hash: Uppercase SHA256 of **those** bytes — not of the file
            she pointed at, which is a different picture and would describe
            nothing on the far side.
        filename: What the recipe's ``photo`` field will name.
    """

    thumbnail: bytes
    thumbnail_hash: str
    filename: str


def prepare(image: bytes) -> Prepared:
    """Make the square thumbnail, and the hash that describes it.

    Centre-cropped rather than squashed: a page squeezed into a square is
    unreadable in a way a cropped one is not, and the middle of a photograph is
    where somebody pointed the camera.

    Pillow is imported here rather than at module scope. It costs about forty
    milliseconds and the great majority of sessions never touch a photo — the
    same reason the ingredient parser is behind a lazy import.

    Args:
        image: The bytes of the file she pointed at.

    Returns:
        Prepared: What to send.

    Raises:
        PaprikaError: When the file is not a picture, or is absurdly large.
    """
    if len(image) > MOST_BYTES:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            "That file is too big to be a photograph of a page.",
            detail=f"{len(image)} bytes exceeds {MOST_BYTES}",
        )

    import io

    from PIL import Image, UnidentifiedImageError

    try:
        opened = Image.open(io.BytesIO(image))
        opened.load()
    except (UnidentifiedImageError, OSError, ValueError) as problem:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            "That file isn't a picture.",
            detail=f"cannot open as an image: {problem}",
        ) from problem

    # A photograph carries its rotation in EXIF rather than in its pixels, and a
    # sideways page helps nobody.
    from PIL import ImageOps

    upright = ImageOps.exif_transpose(opened) or opened
    square = ImageOps.fit(
        upright.convert("RGB"),
        (THUMBNAIL_EDGE, THUMBNAIL_EDGE),
        method=Image.Resampling.LANCZOS,
    )

    buffer = io.BytesIO()
    square.save(buffer, format="JPEG", quality=THUMBNAIL_QUALITY)
    thumbnail = buffer.getvalue()

    return Prepared(
        thumbnail=thumbnail,
        thumbnail_hash=hashlib.sha256(thumbnail).hexdigest().upper(),
        filename=f"{uuid.uuid4().hex.upper()}.jpg",
    )
