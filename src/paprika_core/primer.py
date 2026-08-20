"""What every session is told before she has said anything.

The fence and four facts, injected whole at session start. Two constraints shape
this module more than anything else it does:

**It must never fail the session.** A corrupt store, an unreadable Profile, a
missing folder — none of them may stop Claude Code starting. Everything here
falls back to saying less rather than to raising.

**It must be quick.** The measured budget is about fifty-four milliseconds, which
is why this module imports the store, the Profile and the Mirror and nothing
else. Importing the Pantry's write path would pull the HTTP client and cost
ninety-nine milliseconds on its own — the core/CLI seam exists to protect exactly
this number.

The four facts carry **no verdicts**. "Pantry last confirmed nine days ago" is a
fact; "your pantry is out of date" is a judgement, and judgement belongs in the
conversation where she can argue with it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from paprika_core import profile, setup, store
from paprika_core.mirror import Mirror

#: How far ahead the Plan is reported. A week, because that is the unit she
#: plans in and the unit a Rollup is judged over.
LOOKAHEAD_DAYS = 7

#: The most lines the fence may run to. Set before the content, so a later idea
#: has to trade against an existing one rather than being appended.
MAX_FENCE_LINES = 35


def _fence(root: Path) -> str:
    """Read the fence, which is the meta-skill's own text.

    Args:
        root: The plugin's root directory.

    Returns:
        str: The skill's body, without its frontmatter. Empty when it cannot be
            read, because a session that starts without the fence is still
            better than no session.
    """
    try:
        text = (root / "skills" / "using-paprika" / "SKILL.md").read_text(
            encoding="utf-8"
        )
    except OSError:
        return ""
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) == 3 else text.strip()


def _plan_lines(today: dt.date) -> list[str]:
    """Return what is planned over the coming week, with literal dates.

    Literal rather than relative, because "next week" is ambiguous on a Sunday
    and a date is not.

    Args:
        today: The day the session started.

    Returns:
        list[str]: One line per planned meal, or a single line saying there is
            nothing. Empty when the Mirror cannot be read at all.
    """
    until = today + dt.timedelta(days=LOOKAHEAD_DAYS)
    try:
        with Mirror(store.mirror_path()) as mirror:
            meals = mirror.meals(today.isoformat(), until.isoformat())
    except Exception:
        return []
    if not meals:
        return [f"Plan for {today:%a %-d %b}–{until:%a %-d %b}: none."]
    return [f"Plan for {today:%a %-d %b}–{until:%a %-d %b}:"] + [
        f"  {dt.date.fromisoformat(meal.date):%a %-d %b}: {meal.name}" for meal in meals
    ]


def _pantry_line() -> str:
    """Return how old what-she-has is, as a fact rather than a verdict.

    Returns:
        str: One line.
    """
    age = store.pantry_age_days()
    if age is None:
        return "Pantry: never confirmed."
    days = int(age)
    if days == 0:
        return "Pantry last confirmed today."
    return f"Pantry last confirmed {days} day{'s' if days != 1 else ''} ago."


def _allergy_line(read: profile.Profile) -> list[str]:
    """Return the allergy fact, or nothing at all.

    An absent line means nobody has been asked; an empty one would mean the
    answer was none. Those are different, so the line is **omitted entirely**
    rather than printed empty — a blank allergy line is the plugin concluding
    something nobody told it.

    Args:
        read: The Profile.

    Returns:
        list[str]: One line, or none.
    """
    if not read.readable or not read.allergies_answered:
        return []
    if not read.allergies:
        return ["Allergies: none in this household."]
    return [f"Allergies: {', '.join(read.allergies)}."]


def facts(today: dt.date | None = None) -> list[str]:
    """Return the four facts, according to how far setup has got.

    Args:
        today: The day the session started. Defaults to today.

    Returns:
        list[str]: The lines to inject. Four states, never three — a store that
            exists but will not read must not send a user of many months back to
            the beginning.
    """
    when = today or dt.date.today()
    progress = setup.read()

    if progress.state is setup.State.UNREADABLE:
        return [
            "Paprika's own files on this machine can't be read. Her recipes in "
            "Paprika itself are untouched. Point her at /paprika:help, not at "
            "setup — she may have been using this for months."
        ]
    if progress.state is setup.State.NEVER:
        return [
            "Paprika is not set up. If she asks for anything recipe- or "
            "meal-shaped, say so once, plainly, and name /paprika:setup — then "
            "drop it."
        ]

    lines = []
    if progress.state is setup.State.INCOMPLETE:
        outstanding = ", ".join(
            step.value.replace("_", " ") for step in progress.missing
        )
        lines.append(f"Setup is unfinished — still to do: {outstanding}.")
    else:
        lines.append("Setup: complete.")

    lines += _plan_lines(when)
    lines.append(_pantry_line())
    lines += _allergy_line(profile.read())
    return lines


def build(root: Path, today: dt.date | None = None) -> str:
    """Build the whole block injected at session start.

    Args:
        root: The plugin's root directory.
        today: The day the session started.

    Returns:
        str: The fence and the facts, inside one block. Never raises: a session
            that starts with less is better than one that does not start.
    """
    try:
        body = _fence(root)
        state = facts(today)
    except Exception:
        body, state = _fence(root), []
    block = [body] if body else []
    if state:
        block.append("## Paprika state\n\n" + "\n".join(state))
    return "<EXTREMELY_IMPORTANT>\n" + "\n\n".join(block) + "\n</EXTREMELY_IMPORTANT>"
