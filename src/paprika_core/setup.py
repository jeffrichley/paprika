"""What has been set up so far — written down rather than worked out.

Setup is resumable, so "incomplete" is a real state rather than a missing file:
credentials can exist with no first download, and a first download can exist with
nothing else. Deriving completeness from which files happen to be present means
every setup step added later silently redefines what *complete* means, and that
bug surfaces months afterwards as a session cheerfully reporting she is set up
when she is not.

There are **four** states rather than three, and the fourth is the one that
matters. A store that exists but cannot be read must not read as *never set up* —
that would take somebody who has used this for months and send her back to the
beginning. Unreadable is not a recorded state; it is where the reader falls when
parsing throws, which is also where a torn read lands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import tomlkit

from paprika_core import store

SETUP_KEY = "setup_completed"

CREDENTIALS_HEADER = """\
# paprika — credentials
#
# Written by setup. Yours: nothing here is ever deleted automatically.
#
# The password is stored, not just a login token, because Paprika's tokens have
# no documented lifetime and re-authenticating has to happen without stopping to
# ask. That trade-off is named in plain language in the project's README.
#
# Anything else you want to change — who lives here, allergies, what people
# dislike — lives in profile.toml next door, not in this file.
"""


class Step(StrEnum):
    """One thing setup has to get done.

    Recorded by the command that actually does the work. There is deliberately
    no command for declaring a step finished: a command that lets a caller
    *assert* progress is a command that lets a caller lie about it.
    """

    CREDENTIALS = "credentials"
    SIGNED_IN = "signed_in"
    LIBRARY = "library"


class State(StrEnum):
    """How far along setup is.

    Four, never three. ``UNREADABLE`` exists so that a corrupt or locked store is
    told apart from a fresh one.
    """

    NEVER = "never_set_up"
    INCOMPLETE = "incomplete"
    READY = "set_up"
    UNREADABLE = "unreadable"


#: Every step that has to be done before anything else will work.
REQUIRED: tuple[Step, ...] = (Step.CREDENTIALS, Step.SIGNED_IN, Step.LIBRARY)


@dataclass(frozen=True)
class Setup:
    """How far setup has got.

    Attributes:
        state: Which of the four states this machine is in.
        done: The steps recorded as finished, in the required order.
        missing: The steps still outstanding.
    """

    state: State
    done: tuple[Step, ...] = ()
    missing: tuple[Step, ...] = ()


def read() -> Setup:
    """Read how far setup has got.

    Returns:
        Setup: The state, and which steps are done and outstanding. A store that
            will not parse reports ``UNREADABLE`` and claims nothing else.
    """
    document = store.read_state_strict()
    if document is None:
        return Setup(state=State.UNREADABLE)

    recorded = document.get(SETUP_KEY) or []
    done = tuple(
        step for step in REQUIRED if isinstance(recorded, list) and step in recorded
    )
    missing = tuple(step for step in REQUIRED if step not in done)

    if not done:
        return Setup(state=State.NEVER, missing=missing)
    if missing:
        return Setup(state=State.INCOMPLETE, done=done, missing=missing)
    return Setup(state=State.READY, done=done)


def record(step: Step) -> None:
    """Write down that a step is finished.

    Called by the command that did the work, never by a caller announcing it.

    Args:
        step: What got done.
    """
    document = store.read_state() or tomlkit.document()
    recorded = document.get(SETUP_KEY)
    steps = list(recorded) if isinstance(recorded, list) else []
    if step.value not in steps:
        steps.append(step.value)
        document[SETUP_KEY] = steps
        store.write_state(document)


def save_credentials(email: str, password: str) -> None:
    """Write her Paprika email and password, and record that it happened.

    Written to its own file rather than beside the session token, so refreshing
    a session can never clobber a password she just corrected.

    Args:
        email: Her Paprika account email.
        password: Her Paprika account password.
    """
    store.write_credentials(email, password, header=CREDENTIALS_HEADER)
    record(Step.CREDENTIALS)
