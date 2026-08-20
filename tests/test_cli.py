"""Seam A — the CLI envelope, which is the only behavioural seam there is.

These tests drive the Typer app and assert on ``{ok, attempted, changed,
complete, error}`` and on what actually reached Paprika. Nothing asserts on an
internal call sequence, and the subject under test is never mocked — only the
wire is.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from paprika_core import store
from paprika_core.cli import app
from tests.fake_paprika import GOOD_EMAIL, FakePaprika
from tests.library import LIBRARY_SIZE

runner = CliRunner()

#: Words that must never appear in anything the session is handed. The mechanics
#: stop at the CLI, so a skill cannot leak what it was never given.
MECHANICS = (
    "hash",
    "uid",
    "token",
    "in_trash",
    "deleted",
    "http",
    "status code",
    "bearer",
    "sync counter",
)


def envelope_of(output: str) -> dict[str, Any]:
    """Parse the one envelope a command printed.

    Args:
        output: Everything the command wrote to stdout.

    Returns:
        dict[str, Any]: The parsed envelope.
    """
    body: dict[str, Any] = json.loads(output.strip().splitlines()[-1])
    return body


def assert_envelope_shape(envelope: dict[str, Any]) -> None:
    """Assert the envelope carries exactly the contract's keys.

    Args:
        envelope: The parsed envelope.
    """
    assert set(envelope) <= {
        "ok",
        "attempted",
        "changed",
        "complete",
        "error",
        "data",
    }
    assert {"ok", "attempted", "changed", "complete", "error"} <= set(envelope)
    assert isinstance(envelope["ok"], bool)
    assert isinstance(envelope["attempted"], str) and envelope["attempted"]
    assert isinstance(envelope["changed"], dict)
    assert isinstance(envelope["complete"], bool)
    if envelope["error"] is not None:
        assert set(envelope["error"]) == {"code", "message"}


def assert_no_mechanics(envelope: dict[str, Any]) -> None:
    """Assert no Paprika mechanic crossed into the envelope, ``data`` included.

    ``data`` carries her own recipe titles, which could legitimately contain any
    English word — so it is checked structurally (no sync tokens, no uids) and by
    key name, rather than by scanning her prose for the word "deleted".

    Args:
        envelope: The parsed envelope.
    """
    fenced = {k: v for k, v in envelope.items() if k != "data"}
    text = json.dumps(fenced).lower()
    for word in MECHANICS:
        assert word not in text, f"{word!r} leaked into the envelope: {text}"

    # The whole envelope, data included, must carry no identifier of Paprika's:
    # no 64-hex sync token and no uid in any casing.
    whole = json.dumps(envelope)
    assert not re.search(r"[0-9a-fA-F]{64}", whole)
    assert not re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}", whole
    ), f"a uid leaked into the envelope: {whole}"

    # And no key in `data` may be named after a mechanic either.
    for key in envelope.get("data") or {}:
        assert key.lower() not in MECHANICS, f"data key {key!r} names a mechanic"


def test_sync_downloads_the_whole_library(signed_in: Path, seeded: FakePaprika) -> None:
    result = runner.invoke(app, ["sync"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert envelope["ok"] is True
    assert envelope["complete"] is True
    assert result.exit_code == 0
    assert envelope["data"]["recipes_downloaded"] == LIBRARY_SIZE


def test_sync_changes_nothing_of_hers(signed_in: Path, seeded: FakePaprika) -> None:
    """A sync moves the Mirror, not her library, so nothing may be reported moved."""
    runner.invoke(app, ["sync"])

    envelope = envelope_of(runner.invoke(app, ["sync"]).stdout)
    assert envelope["changed"] == {}
    assert seeded.writes == []


def test_cold_sync_is_one_plus_n_requests(signed_in: Path, seeded: FakePaprika) -> None:
    """There is no bulk recipe endpoint; each recipe costs its own request."""
    runner.invoke(app, ["sync"])

    fetches = [p for m, p in seeded.requests if m == "GET" and "/sync/recipe/" in p]
    assert len(fetches) == len(seeded.recipes)


def test_recipe_index_returns_one_line_per_recipe(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["recipe", "index"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert result.exit_code == 0
    assert envelope["data"]["count"] == LIBRARY_SIZE
    assert len(envelope["data"]["recipes"]) == LIBRARY_SIZE


def test_recipe_index_names_her_categories_not_their_ids(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    envelope = envelope_of(runner.invoke(app, ["recipe", "index"]).stdout)
    lines = envelope["data"]["recipes"]

    roast = next(line for line in lines if "Roast Lemon Chicken" in line)
    assert "Roasts" in roast
    assert "CAT-ROAST" not in roast


def test_reads_in_one_conversation_ask_at_most_once(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """A sync has just asked everything, so the reads after it cost nothing."""
    runner.invoke(app, ["sync"])
    seeded.requests.clear()

    runner.invoke(app, ["recipe", "index"])
    runner.invoke(app, ["recipe", "index"])

    assert seeded.requests == []


def test_fresh_asks_again(signed_in: Path, seeded: FakePaprika) -> None:
    """`--fresh` is an explicit opt-in, never a default."""
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["recipe", "index"])
    seeded.requests.clear()

    runner.invoke(app, ["recipe", "index", "--fresh"])

    assert seeded.requests == [("GET", "/api/v2/sync/status/")]


def test_a_read_notices_a_recipe_she_deleted_on_her_phone(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The reason freshness is asked rather than timed."""
    runner.invoke(app, ["sync"])
    gone = next(uid for uid, r in seeded.recipes.items() if not r["in_trash"])
    gone_name = seeded.recipes[gone]["name"]
    del seeded.recipes[gone]
    seeded.counters["recipes"] += 1

    envelope = envelope_of(runner.invoke(app, ["recipe", "index", "--fresh"]).stdout)

    assert all(gone_name not in line for line in envelope["data"]["recipes"])


def test_status_reports_what_this_machine_has(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])

    result = runner.invoke(app, ["status"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert_no_mechanics(envelope)
    assert result.exit_code == 0
    assert envelope["data"]["setup"] == "set_up"
    assert envelope["data"]["still_to_do"] == []
    assert envelope["data"]["recipes"] == LIBRARY_SIZE
    # The wiring, not the arithmetic — the fake answers instantly, so the
    # measured median is sub-millisecond here. `test_pace.py` owns the maths.
    assert isinstance(envelope["data"]["estimated_seconds"], int)


def test_status_works_before_setup_rather_than_failing(paprika_home: Path) -> None:
    """Reporting that setup is unfinished is an answer, not an error."""
    result = runner.invoke(app, ["status"])

    envelope = envelope_of(result.stdout)
    assert result.exit_code == 0
    assert envelope["ok"] is True
    assert envelope["data"]["setup"] == "never_set_up"
    assert envelope["data"]["mirror_age_seconds"] is None


def test_recipe_index_before_a_sync_says_so_without_a_traceback(
    signed_in: Path,
) -> None:
    result = runner.invoke(app, ["recipe", "index"])

    envelope = envelope_of(result.stdout)
    assert_envelope_shape(envelope)
    assert envelope["ok"] is False
    assert result.exit_code == 1
    assert envelope["error"]["code"] == "nothing_mirrored"
    assert "Traceback" not in result.stdout


def test_login_stores_a_session(credentials_present: Path) -> None:
    result = runner.invoke(app, ["login"])

    envelope = envelope_of(result.stdout)
    assert envelope["ok"] is True
    assert result.exit_code == 0
    assert store.read_token() is not None


def test_login_without_credentials_is_not_set_up(paprika_home: Path) -> None:
    result = runner.invoke(app, ["login"])

    envelope = envelope_of(result.stdout)
    assert envelope["ok"] is False
    assert result.exit_code == 1
    assert envelope["error"]["code"] == "not_set_up"
    assert_no_mechanics(envelope)


def test_bad_credentials_are_rejected_in_her_words(paprika_home: Path) -> None:
    """Paprika refuses at a 200. That must still be a failure, and a plain one."""
    (paprika_home / ".env").write_text(
        f"PAPRIKA_EMAIL={GOOD_EMAIL}\nPAPRIKA_PASSWORD=wrong\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["login"])

    envelope = envelope_of(result.stdout)
    assert envelope["ok"] is False
    assert result.exit_code == 1
    assert envelope["error"]["code"] == "credentials_rejected"
    # Paprika's own wording never crosses over.
    assert "Invalid email or password." not in result.stdout


def test_sync_without_setup_says_so_rather_than_failing_oddly(
    paprika_home: Path,
) -> None:
    result = runner.invoke(app, ["sync"])

    envelope = envelope_of(result.stdout)
    assert envelope["error"]["code"] == "not_set_up"
    assert result.exit_code == 1
    assert envelope["complete"] is False


def test_a_stale_session_is_renewed_without_reaching_the_envelope(
    credentials_present: Path, seeded: FakePaprika
) -> None:
    """An expired token is not a failure she should ever hear about."""
    store.save_token("stale-token")

    result = runner.invoke(app, ["sync"])

    envelope = envelope_of(result.stdout)
    assert envelope["ok"] is True
    assert result.exit_code == 0
    assert store.read_token() != "stale-token"


def test_exit_code_always_agrees_with_ok(signed_in: Path, seeded: FakePaprika) -> None:
    for argv in (["sync"], ["recipe", "index"], ["login"]):
        result = runner.invoke(app, argv)
        envelope = envelope_of(result.stdout)
        assert result.exit_code == (0 if envelope["ok"] else 1), argv


def test_human_rendering_is_the_same_envelope(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """``--human`` is a second renderer, never a second contract."""
    runner.invoke(app, ["sync"])

    human = runner.invoke(app, ["--human", "recipe", "index"])
    machine = runner.invoke(app, ["recipe", "index"])

    assert human.exit_code == machine.exit_code == 0
    assert "Roast Lemon Chicken" in human.stdout
    assert human.stdout != machine.stdout


def test_diagnostics_go_to_the_log_not_the_session(paprika_home: Path) -> None:
    runner.invoke(app, ["sync"])

    log = paprika_home / "logs" / "paprika.jsonl"
    assert log.is_file()
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(record["event"] == "command" for record in records)


def test_status_estimates_the_first_download_before_it_happens(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """The one moment the estimate matters, and the Mirror cannot supply the count."""
    runner.invoke(app, ["login"])
    result = runner.invoke(app, ["status"])

    envelope = envelope_of(result.stdout)
    assert envelope["ok"] is True
    assert envelope["data"]["recipes"] == 0
    # One cheap request for the stub index is what makes the number honest.
    assert envelope["data"]["estimated_seconds"] is not None
    assert ("GET", "/api/v2/sync/recipes/") in seeded.requests


def test_status_admits_it_cannot_estimate_before_setup(paprika_home: Path) -> None:
    """Nothing can be measured or counted yet, so nothing is claimed."""
    envelope = envelope_of(runner.invoke(app, ["status"]).stdout)

    assert envelope["data"]["estimated_seconds"] is None
