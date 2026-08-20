"""Reading an ingredient line must never touch the network.

The whole reason #48 bundles USDA data rather than calling the API is that a
home cook should not need a key, a rate limit, or a connection. The parser
quietly undid that: NLTK ships no part-of-speech tagger with the library, so
``ingredient-parser-nlp`` calls ``nltk.download`` the first time it parses
anything. On a developer's machine ``~/nltk_data`` is already populated and it
never shows; on hers it is a silent 1.5 MB fetch, and offline it is a failure.

These tests run in a subprocess with ``HOME`` and ``NLTK_DATA`` redirected at an
empty directory, because that is the only way to prove the bundled copy is doing
the work rather than a copy the developer happens to have.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from paprika_core.errors import Code, PaprikaError
from paprika_core.nutrition.parsing import TAGGER, nltk_data_dir, parse_line

#: The checksum the NLTK data index publishes for this resource. Pinned so the
#: bundled copy stays traceable to the release it came from.
TAGGER_MD5 = "729e2255f83045670374180de9bdb613"

PROGRAM = """
import os, socket, sys

os.environ["HOME"] = {home!r}
os.environ["USERPROFILE"] = {home!r}
os.environ["NLTK_DATA"] = {empty!r}


def refuse(*args, **kwargs):
    raise AssertionError("the parser tried to open a network connection")


socket.socket.connect = refuse
socket.socket.connect_ex = refuse
socket.create_connection = refuse

from paprika_core.nutrition.parsing import parse_line

parsed = parse_line("2 large yellow onions, diced")
print(parsed.name, "|", parsed.quantity, "|", parsed.size)
"""


def test_a_line_parses_with_no_user_level_nltk_data_and_no_socket(
    tmp_path: Path,
) -> None:
    """The failing case on a clean machine, run the way a clean machine runs it."""
    empty = tmp_path / "nltk_data"
    empty.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            PROGRAM.format(home=str(tmp_path), empty=str(empty)),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "yellow onions | 2.0 | large"
    # The parser announces its own download on stdout before making it.
    assert "Downloading" not in result.stdout


def test_the_tagger_is_bundled_and_is_the_one_nltk_publishes() -> None:
    bundled = nltk_data_dir() / "taggers" / f"{TAGGER}.zip"

    assert bundled.is_file()
    assert hashlib.md5(bundled.read_bytes()).hexdigest() == TAGGER_MD5


def test_it_is_laid_out_the_way_nltk_looks_for_it() -> None:
    """NLTK finds ``taggers/<name>/<file>`` inside ``taggers/<name>.zip``."""
    assert (nltk_data_dir() / "taggers").is_dir()


def test_a_missing_tagger_is_said_out_loud_rather_than_downloaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The alternative — what the parser does alone — is a silent fetch."""
    monkeypatch.setattr(
        "paprika_core.nutrition.parsing.nltk_data_dir", lambda: tmp_path / "gone"
    )

    with pytest.raises(PaprikaError) as caught:
        parse_line("2 large yellow onions")

    assert caught.value.code is Code.NUTRITION_DATA_MISSING
    assert "nltk" not in caught.value.message.lower()
