"""``~/.paprika/logs/paprika.jsonl`` — where the mechanics go instead of the session.

One line per command and per request: method, path, status, duration, and for a
failure whatever Paprika actually said. **Bodies are never logged** — the tempting
default puts her whole library in a plaintext file.

Nothing here raises. A log that can fail a command is worse than no log.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from paprika_core.store import LOG_DIRNAME, home

LOG_FILENAME = "paprika.jsonl"
MAX_BYTES = 1_048_576


def log_path() -> Path:
    """Return the log file's path.

    Returns:
        Path: ``<home>/logs/paprika.jsonl``.
    """
    return home() / LOG_DIRNAME / LOG_FILENAME


def log_event(event: str, **fields: Any) -> None:
    """Append one event to the log, or silently give up.

    Args:
        event: A short event name, e.g. ``request`` or ``command``.
        **fields: Anything else worth keeping. Never a response body.
    """
    record: dict[str, Any] = {"t": round(time.time(), 3), "event": event}
    record.update(fields)
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size >= MAX_BYTES:
            path.replace(path.parent / f"{LOG_FILENAME}.1")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        return
