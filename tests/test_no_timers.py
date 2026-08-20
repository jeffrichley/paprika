"""There are no timeouts and no budgets anywhere. Asserted, not remembered.

Long work is resumable because it commits incrementally, not because it is
timed. A time budget is an arbitrary knob, and cutting work off to satisfy a
clock is the wrong reason to stop — so this is a rule about the whole codebase
rather than about one call site, and it is enforced as one.

The scan reads **code**, with comments and string literals tokenized away. Prose
may discuss the session-start budget; a line of code may not introduce one.
"""

from __future__ import annotations

import re
import tokenize
from pathlib import Path

import httpx

from paprika_core.http import PaprikaClient

SOURCE = Path(__file__).resolve().parent.parent / "src" / "paprika_core"

#: Ways a timer or a cap tends to arrive.
TIMERS = re.compile(r"timeout|budget|deadline|max_seconds|signal\.alarm", re.IGNORECASE)

#: Turning httpx's own five-second default off is the opposite of adding a
#: timeout, so the one line that does it is allowed to say the word.
DISABLING = re.compile(r"timeout=None|Timeout\(None\)", re.IGNORECASE)

#: `STAMP_SECONDS` is deliberately not on the list: it bounds how long an
#: *answer about freshness* stays reusable, which is a cache validity window
#: rather than a limit on how long work may take.


def _code_by_line(module: Path) -> dict[int, str]:
    """Return each line's code, with comments and string literals removed.

    Args:
        module: The file to read.

    Returns:
        dict[int, str]: Line number to that line's code tokens, concatenated.
    """
    lines: dict[int, str] = {}
    with module.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type not in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
                continue
            lines[token.start[0]] = lines.get(token.start[0], "") + token.string
    return lines


def test_no_module_introduces_a_timer_or_a_budget() -> None:
    offenders: list[str] = []
    for module in sorted(SOURCE.glob("**/*.py")):
        for number, code in _code_by_line(module).items():
            if TIMERS.search(code) and not DISABLING.search(code):
                offenders.append(f"{module.name}:{number}: {code}")

    assert not offenders, "a timeout or budget appeared:\n" + "\n".join(offenders)


def test_the_scan_would_actually_catch_one(tmp_path: Path) -> None:
    """A conformance test nobody has seen fail is a conformance test nobody trusts."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        '"""A docstring may say budget."""\n'
        "# and so may a comment: timeout\n"
        "value = fetch(timeout=5)\n",
        encoding="utf-8",
    )

    caught = {
        number
        for number, code in _code_by_line(planted).items()
        if TIMERS.search(code) and not DISABLING.search(code)
    }

    assert caught == {3}


def test_the_client_waits_as_long_as_paprika_takes() -> None:
    """httpx defaults to a five-second timeout, which is a cap we never chose.

    This reaches into the client's own httpx instance deliberately. The
    alternative is a public accessor that exists only to be asserted on — and
    one named `timeout`, which would then have to be excused from the scan
    above. Reading a construction detail is the smaller cost.
    """
    client = PaprikaClient()
    try:
        assert client._client.timeout == httpx.Timeout(None)
    finally:
        client.close()
