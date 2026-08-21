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
import json
from pathlib import Path

from paprika_core import profile, setup, store
from paprika_core.mirror import Mirror

#: How far ahead the Plan is reported. A week, because that is the unit she
#: plans in and the unit a Rollup is judged over.
LOOKAHEAD_DAYS = 7

#: What this plugin is called to the thing that installed the command — the name
#: whoever is repairing it has to type.
DISTRIBUTION = "paprika-plugin"

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


def installed_version() -> str | None:
    """Return the version of the command that is running.

    Read from the package rather than from its installed metadata, because
    ``importlib.metadata`` costs about **47 ms** cold — most of a second primer
    on top of the one we have. The budget test caught that; the constant is
    free, travels with the code wherever it was installed from, and is moved by
    the same release that moves the manifest.

    Returns:
        str | None: The version, or ``None`` when it cannot be established.
    """
    from paprika_core import __version__

    return __version__ or None


def plugin_version(root: Path) -> str | None:
    """Return the version of the plugin whose skills this session is using.

    Args:
        root: The plugin's root directory.

    Returns:
        str | None: The version in its manifest, or ``None`` when the manifest
            cannot be read.
    """
    try:
        manifest = json.loads(
            (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    found = manifest.get("version")
    return str(found) if found else None


def mismatch_lines(root: Path) -> list[str]:
    """Say so when the skills and the command are different versions.

    They are installed by two commands nobody runs together — ``/plugin update``
    and ``uv tool upgrade`` — so drifting apart is the ordinary outcome, not the
    unlucky one. Unchecked it surfaces as a skill calling a subcommand that does
    not exist, which reads as a broken plugin rather than a stale one.

    Args:
        root: The plugin's root directory.

    Returns:
        list[str]: One line, or none. **Not knowing a version is not a
            disagreement** — a warning every session is one nobody reads by the
            second week.
    """
    theirs, ours = plugin_version(root), installed_version()
    if theirs is None or ours is None or theirs == ours:
        return []
    return [
        f"The skills here are version {theirs} and the `paprika` command is "
        f"{ours}. Anything that fails oddly is likely that. Fixing it is "
        f"`uv tool upgrade {DISTRIBUTION}` and `/plugin update paprika`, then a "
        f"new session."
    ]


def on_day(when: dt.date) -> str:
    """Render a date the way a person says it out loud.

    ``%-d`` gives a day with no leading zero on glibc and BSD, and raises
    ``ValueError`` on Windows; ``%#d`` is the reverse. There is no portable
    directive for it, so the day comes from :attr:`datetime.date.day` and
    strftime is only asked for the parts every platform agrees on.

    Args:
        when: The date.

    Returns:
        str: Something like ``Mon 7 Sep`` — no leading zero, because
            ``Mon 07 Sep`` reads like a serial number rather than a day.
    """
    return f"{when:%a} {when.day} {when:%b}"


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
        return [f"Plan for {on_day(today)}–{on_day(until)}: none."]
    return [f"Plan for {on_day(today)}–{on_day(until)}:"] + [
        f"  {on_day(dt.date.fromisoformat(meal.date))}: {meal.name}" for meal in meals
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
    if not read.readable:
        return []
    lines = []
    if read.allergies_answered or read.always_avoid:
        if read.always_avoid:
            named = [
                f"{name} (traces matter)" if name in read.always_severe else name
                for name in read.always_avoid
            ]
            lines.append(f"Allergies, every meal: {', '.join(named)}.")
        else:
            lines.append("Allergies: none in this household.")
    if read.guests_to_ask_about:
        # Named, but not folded into the line above: a guest's allergy binds the
        # meals they are at and nothing else, and a week has to ask whether they
        # are coming rather than assume it either way.
        who = ", ".join(
            "{} ({})".format(
                name,
                ", ".join(
                    f"{a} — traces matter" if a in read.guests[name].severe else a
                    for a in read.guests[name].allergies
                ),
            )
            for name in read.guests_to_ask_about
        )
        lines.append(f"Guests who sometimes eat here: {who}.")
    return lines


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
        state = mismatch_lines(root) + facts(today)
    except Exception:
        # The fence still goes out: a session holding the rules and none of the
        # facts is worth far more than no session at all. But saying nothing is
        # how a whole platform lost this block without anyone noticing, so the
        # gap is named — a machine with nothing planned must not look the same
        # as a machine that could not work out what it had.
        body = _fence(root)
        state = [
            "What this machine holds could not be read, so nothing below is "
            "known this session — not the plan, not the pantry, not the "
            "allergies. Her recipes in Paprika are untouched. Ask before "
            "assuming any of it, and treat /paprika:help as the next step if "
            "she notices."
        ]
    block = [body] if body else []
    if state:
        block.append("## Paprika state\n\n" + "\n".join(state))
    return "<EXTREMELY_IMPORTANT>\n" + "\n\n".join(block) + "\n</EXTREMELY_IMPORTANT>"
