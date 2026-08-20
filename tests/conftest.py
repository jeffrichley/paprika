"""Fixtures that make a real network request impossible.

Two of them are autouse, and both are autouse for the same reason: a safety
property that each test has to remember to opt into is a safety property that
will eventually be forgotten.

* :func:`fake_paprika` puts the fake transport in front of every client, so an
  unfaked path is answered by the fake rather than by ``paprikaapp.com``.
* :func:`no_network` fails loudly if a socket is opened anyway, so a path that
  slips past the transport seam is a red test rather than a silent live request
  against somebody's real recipe library.

:func:`paprika_home` gives every test its own ``~/.paprika`` inside ``tmp_path``,
so nothing here can read or write the developer's own store.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from paprika_core import http, store
from paprika_core.mirror import Mirror
from tests.fake_paprika import GOOD_EMAIL, GOOD_PASSWORD, TOKEN, FakePaprika
from tests.library import CATEGORY_TREE, build_library


class NetworkAccessError(AssertionError):
    """Raised when a test tries to open a real socket."""


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if anything opens a real socket.

    The fake transport is the intended path. This is the backstop that turns
    "somebody added a code path the fake doesn't cover" from a live request into
    a failing test.

    Args:
        monkeypatch: pytest's patcher.
    """

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise NetworkAccessError(
            "A test tried to open a real network connection. Every request must "
            "go through the fake Paprika transport."
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def fake() -> FakePaprika:
    """Return an empty fake Paprika account.

    Returns:
        FakePaprika: The account, which a test may seed.
    """
    return FakePaprika()


@pytest.fixture(autouse=True)
def fake_paprika(
    fake: FakePaprika, monkeypatch: pytest.MonkeyPatch
) -> Iterator[FakePaprika]:
    """Point every client at the fake, whether the test asked for it or not.

    Args:
        fake: The account to answer with.
        monkeypatch: pytest's patcher.

    Yields:
        FakePaprika: The same account, for assertions.
    """
    monkeypatch.setattr(http, "TRANSPORT", fake.transport())
    yield fake


@pytest.fixture(autouse=True)
def paprika_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give this test its own ``~/.paprika``.

    Autouse, because a test that forgot it would read the developer's real store
    and could write to it.

    Args:
        tmp_path: pytest's per-test directory.
        monkeypatch: pytest's patcher.

    Returns:
        Path: The store's root, which exists and is empty.
    """
    root = tmp_path / ".paprika"
    root.mkdir()
    monkeypatch.setenv("PAPRIKA_HOME", str(root))
    return root


@pytest.fixture
def credentials_present(paprika_home: Path) -> Path:
    """Write a ``.env`` holding credentials the fake will accept.

    Args:
        paprika_home: The store's root.

    Returns:
        Path: The store's root, now at the "credentials given" setup state.
    """
    env = paprika_home / ".env"
    env.write_text(
        f"PAPRIKA_EMAIL={GOOD_EMAIL}\nPAPRIKA_PASSWORD={GOOD_PASSWORD}\n",
        encoding="utf-8",
    )
    env.chmod(0o600)
    return paprika_home


@pytest.fixture
def signed_in(credentials_present: Path) -> Path:
    """Put the store at the "already has a session" setup state.

    Args:
        credentials_present: The store, with credentials.

    Returns:
        Path: The store's root.
    """
    store.save_token(TOKEN)
    return credentials_present


@pytest.fixture
def seeded(fake: FakePaprika) -> FakePaprika:
    """Seed the fake account with the reference Library and category tree.

    Args:
        fake: The empty account.

    Returns:
        FakePaprika: The account, holding recipes and a three-level tree.
    """
    fake.categories = [dict(category) for category in CATEGORY_TREE]
    for recipe in build_library():
        fake.recipes[recipe["uid"]] = recipe
    # Change counters, not counts — they move on modification and say nothing
    # about how many of anything there are.
    fake.counters = {"recipes": 812, "categories": 44, "meals": 130, "pantry": 61}
    return fake


@pytest.fixture
def mirror(paprika_home: Path) -> Iterator[Mirror]:
    """Open a Mirror in this test's store.

    Args:
        paprika_home: The store's root.

    Yields:
        Mirror: An open, empty Mirror.
    """
    with Mirror(store.mirror_path()) as open_mirror:
        yield open_mirror
