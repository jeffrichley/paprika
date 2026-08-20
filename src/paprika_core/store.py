"""``~/.paprika`` — where everything durable lives, ordered by disposability.

The layout is decided in ADR 0002 and issue #13. This module owns only the two
files the walking skeleton needs: ``.env`` (hers, never auto-deleted) and
``state.toml`` (machine state, holds the token). The token lives apart from the
password on purpose, so refreshing one can never clobber the other.

``PAPRIKA_HOME`` relocates the whole store. It exists so a test can own a home
in ``tmp_path``; nothing in the session ever sets it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomlkit

from paprika_core.errors import Code, PaprikaError

STATE_FILENAME = "state.toml"
ENV_FILENAME = ".env"
MIRROR_FILENAME = "cache.sqlite3"
USDA_FILENAME = "usda.sqlite3"
MEMO_FILENAME = "nutrition.sqlite3"
LOG_DIRNAME = "logs"


def home() -> Path:
    """Return the store's root directory.

    Returns:
        Path: ``$PAPRIKA_HOME`` when set, otherwise ``~/.paprika``.
    """
    override = os.environ.get("PAPRIKA_HOME")
    if override:
        return Path(override)
    return Path.home() / ".paprika"


def ensure_home() -> Path:
    """Create the store's root directory if it is missing.

    Returns:
        Path: The store's root directory, which now exists.
    """
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    return root


def mirror_path() -> Path:
    """Return the path of the Mirror's database.

    Returns:
        Path: ``<home>/cache.sqlite3``. Disposable — it is only ever a copy.
    """
    return home() / MIRROR_FILENAME


def usda_index_path() -> Path:
    """Return the path of the materialised USDA index.

    It lives here rather than beside the installed package because the plugin
    lives in a versioned directory that changes on upgrade: a home-relative path
    means the index is built once per machine rather than once per version.

    Returns:
        Path: ``<home>/usda.sqlite3``. Disposable — it rebuilds from the
            bundled data.
    """
    return home() / USDA_FILENAME


def memo_path() -> Path:
    """Return the path of the nutrition memos.

    Deliberately a different file from :func:`usda_index_path`, so rebuilding
    the index — which is cheap and routine — cannot destroy the memos, which are
    expensive and not reproducible from anything on disk.

    Returns:
        Path: ``<home>/nutrition.sqlite3``.
    """
    return home() / MEMO_FILENAME


def _parse_env(text: str) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` file into a mapping.

    Hand-rolled rather than pulling in a dependency: the file has two keys and
    the format is a decade old.

    Args:
        text: The file's contents.

    Returns:
        dict[str, str]: The parsed keys, with surrounding quotes removed.
    """
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def credentials() -> tuple[str, str]:
    """Read her Paprika email and password from the store.

    Returns:
        tuple[str, str]: ``(email, password)``.

    Raises:
        PaprikaError: ``not_set_up`` when the file is absent or either value is
            blank. Setup being incomplete is a state, not a crash.
    """
    path = home() / ENV_FILENAME
    unset = PaprikaError(
        Code.NOT_SET_UP,
        "Paprika isn't set up on this machine yet.",
        detail=f"missing or incomplete {path}",
    )
    if not path.is_file():
        raise unset
    values = _parse_env(path.read_text(encoding="utf-8"))
    email = values.get("PAPRIKA_EMAIL", "").strip()
    password = values.get("PAPRIKA_PASSWORD", "").strip()
    if not email or not password:
        raise unset
    return email, password


def read_state() -> tomlkit.TOMLDocument:
    """Read ``state.toml``, comments and all.

    Returns:
        tomlkit.TOMLDocument: The parsed document, empty when the file is absent
            or unreadable. A corrupt state file is a state to rebuild, not a
            reason to fail.
    """
    path = home() / STATE_FILENAME
    if not path.is_file():
        return tomlkit.document()
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return tomlkit.document()


def write_state(document: tomlkit.TOMLDocument) -> None:
    """Write ``state.toml`` back, preserving whatever comments it carried.

    Args:
        document: The document to write.
    """
    ensure_home()
    path = home() / STATE_FILENAME
    path.write_text(tomlkit.dumps(document), encoding="utf-8")
    path.chmod(0o600)


def save_token(token: str) -> None:
    """Persist the login token.

    Args:
        token: The bearer token Paprika issued.
    """
    document = read_state()
    document["token"] = token
    write_state(document)


def read_token() -> str | None:
    """Return the persisted login token.

    Returns:
        str | None: The token, or ``None`` when there is not one.
    """
    value: Any = read_state().get("token")
    return value if isinstance(value, str) and value else None


def clear_token() -> None:
    """Forget the persisted login token."""
    document = read_state()
    if "token" in document:
        del document["token"]
        write_state(document)
