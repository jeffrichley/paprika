"""The envelope: the one shape every command returns."""

from __future__ import annotations

import json

from paprika_core.envelope import Envelope, failed, succeeded
from paprika_core.errors import Code, PaprikaError


def test_the_exit_code_agrees_with_ok() -> None:
    assert succeeded("doing a thing").exit_code == 0
    assert (
        failed(
            "doing a thing", PaprikaError(Code.UNEXPECTED, "It didn't work.")
        ).exit_code
        == 1
    )


def test_a_failure_keeps_what_had_already_moved() -> None:
    """What moved before a failure decides whether retrying is safe."""
    envelope = failed(
        "writing three recipes",
        PaprikaError(Code.UNEXPECTED, "It stopped."),
        changed={"recipes": 3},
    )

    assert envelope.changed == {"recipes": 3}
    assert envelope.complete is False


def test_changed_is_a_map_by_kind_not_a_boolean() -> None:
    """The single word "library" flattened the distinction that mattered."""
    assert succeeded("doing a thing").to_dict()["changed"] == {}
    assert succeeded("doing a thing", changed={"recipes": 2, "plan": 1}).to_dict()[
        "changed"
    ] == {"recipes": 2, "plan": 1}


def test_data_is_absent_from_the_envelope_when_there_is_none() -> None:
    assert "data" not in succeeded("doing a thing").to_dict()
    assert "data" in succeeded("doing a thing", data={"count": 0}).to_dict()


def test_the_envelope_serialises_to_one_line() -> None:
    line = Envelope(ok=True, attempted="doing a thing").to_json()

    assert "\n" not in line
    assert json.loads(line)["ok"] is True


def test_an_error_code_serialises_as_its_plain_string() -> None:
    """A typed code inside; the same string as ever on the wire."""
    envelope = failed("doing a thing", PaprikaError(Code.NOT_SET_UP, "Not yet."))

    assert json.loads(envelope.to_json())["error"]["code"] == "not_set_up"
