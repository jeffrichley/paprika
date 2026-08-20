"""Failures, in her language and in ours at the same time.

Every failure that reaches the session is a :class:`PaprikaError`. It carries two
strings deliberately: ``message`` is a sentence already fit to say to her, and
``detail`` is whatever Paprika actually said. Only ``message`` crosses into the
envelope; ``detail`` goes to the log. That split is what keeps
``Unrecognized client.`` and ``HTTP 500`` on this side of the fence.
"""

from __future__ import annotations

from enum import StrEnum


class PaprikaError(Exception):
    """A failure with a code for a caller and a sentence for her.

    Args:
        code: Which failure this is.
        message: One sentence fit to say to a non-developer.
        detail: Verbatim diagnostic for the log. Never surfaced.
        status: The HTTP status this arrived at, when it came off the wire.
        said: What Paprika itself said, verbatim. For deciding what to do about
            it — never for showing her.
    """

    def __init__(
        self,
        code: Code,
        message: str,
        detail: str | None = None,
        status: int | None = None,
        said: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.status = status
        self.said = said


class Code(StrEnum):
    """Every failure code a caller can be handed.

    A ``StrEnum`` rather than loose constants so a typo is a type error on both
    sides of a comparison, while the JSON on the wire stays the plain string it
    always was.
    """

    NOT_SET_UP = "not_set_up"
    CREDENTIALS_REJECTED = "credentials_rejected"
    PAPRIKA_UNREACHABLE = "paprika_unreachable"
    PAPRIKA_REFUSED = "paprika_refused"
    NOTHING_MIRRORED = "nothing_mirrored"
    REFUSED_LOCALLY = "refused_locally"
    NOTHING_TO_UNDO = "nothing_to_undo"
    UNEXPECTED = "unexpected"
