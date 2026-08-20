"""The one shape every command returns.

``{ok, attempted, changed, complete, error}`` — plus an optional ``data`` payload
for reads, which is how a one-line recipe index gets out without inventing a
second output contract.

``changed`` is a **map by kind**, never a boolean: ``{}`` means nothing of hers
moved, and ``complete: false`` beside a non-empty ``changed`` is the partial Run.
The exit code always agrees with ``ok``.

Dataclasses rather than Pydantic on purpose: this module is imported on the
session-start path, and the budget there is measured in tens of milliseconds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from paprika_core.errors import PaprikaError


@dataclass(frozen=True)
class ErrorDetail:
    """The ``error`` member: a code for a caller, a sentence for her."""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return the JSON form of this error.

        Returns:
            dict[str, str]: ``{"code": ..., "message": ...}``.
        """
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class Envelope:
    """What a command returns, whatever the command was.

    Attributes:
        ok: Whether the command did what it set out to do.
        attempted: What was tried, phrased so it can be said to her.
        changed: What kinds of her things moved, and how many of each.
        complete: Whether the work ran to the end.
        error: The failure, when there was one.
        data: Read payload. Absent from the JSON when there is none.
    """

    ok: bool
    attempted: str
    changed: dict[str, int] = field(default_factory=dict)
    complete: bool = True
    error: ErrorDetail | None = None
    data: dict[str, Any] | None = None

    @property
    def exit_code(self) -> int:
        """Return the process exit code, which always agrees with ``ok``.

        Returns:
            int: ``0`` when ``ok``, ``1`` otherwise.
        """
        return 0 if self.ok else 1

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON form of the envelope.

        Returns:
            dict[str, Any]: The five contract keys, plus ``data`` when present.
        """
        body: dict[str, Any] = {
            "ok": self.ok,
            "attempted": self.attempted,
            "changed": dict(self.changed),
            "complete": self.complete,
            "error": self.error.to_dict() if self.error else None,
        }
        if self.data is not None:
            body["data"] = self.data
        return body

    def to_json(self) -> str:
        """Return the envelope as a single line of JSON.

        Returns:
            str: Compact JSON, which is what the session actually consumes.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


def succeeded(
    attempted: str,
    changed: dict[str, int] | None = None,
    data: dict[str, Any] | None = None,
) -> Envelope:
    """Build the envelope for work that finished.

    Args:
        attempted: What was tried.
        changed: What kinds of her things moved. Omit when nothing of hers did.
        data: Read payload, when the command has one.

    Returns:
        Envelope: An ``ok`` envelope.
    """
    return Envelope(
        ok=True,
        attempted=attempted,
        changed=changed or {},
        complete=True,
        data=data,
    )


def failed(
    attempted: str,
    error: PaprikaError,
    changed: dict[str, int] | None = None,
) -> Envelope:
    """Build the envelope for work that did not finish.

    ``changed`` is carried through rather than emptied: what already moved before
    a failure is precisely the fact that decides whether retrying is safe.

    Args:
        attempted: What was tried.
        error: The failure. Only its sentence crosses into the envelope.
        changed: What had already moved when it failed.

    Returns:
        Envelope: A not-``ok``, not-``complete`` envelope.
    """
    return Envelope(
        ok=False,
        attempted=attempted,
        changed=changed or {},
        complete=False,
        error=ErrorDetail(code=error.code, message=error.message),
    )
