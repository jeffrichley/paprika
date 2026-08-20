"""The log — where the mechanics go instead of the session."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paprika_core import log
from paprika_core.log import log_event


def test_the_log_never_raises(
    paprika_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A log that can fail a command is worse than no log."""
    monkeypatch.setenv("PAPRIKA_HOME", "/dev/null/nowhere")

    log_event("command", attempted="doing a thing")


def test_the_log_rotates_rather_than_growing(
    paprika_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(log, "MAX_BYTES", 64)

    for _ in range(20):
        log_event("request", path="/api/v2/sync/status/", status=200)

    logs = paprika_home / "logs"
    assert (logs / "paprika.jsonl").is_file()
    assert (logs / "paprika.jsonl.1").is_file()


def test_each_event_is_one_json_line(paprika_home: Path) -> None:
    log_event("request", path="/api/v2/sync/status/", status=200)

    line = (paprika_home / "logs" / "paprika.jsonl").read_text().strip()
    record = json.loads(line)
    assert record["event"] == "request"
    assert record["status"] == 200
