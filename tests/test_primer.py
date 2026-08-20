"""The primer — four facts, no verdicts, and a session that always starts.

The hook is a command with an output contract and a measured budget, so it is
tested here rather than being the one thing nobody can check.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from paprika_core import primer, setup
from paprika_core.cli import app
from tests.fake_paprika import FakePaprika

REPO = Path(__file__).resolve().parent.parent
runner = CliRunner()
TODAY = dt.date(2026, 8, 24)


def test_a_fresh_machine_is_told_to_set_up(paprika_home: Path) -> None:
    lines = primer.facts(TODAY)

    assert len(lines) == 1
    assert "/paprika:setup" in lines[0]


def test_a_damaged_store_points_at_help_never_at_setup(paprika_home: Path) -> None:
    """She may have been using this for months. Do not send her to the beginning."""
    (paprika_home / "state.toml").write_text("broken = [", encoding="utf-8")

    said = " ".join(primer.facts(TODAY))

    assert "/paprika:help" in said
    assert "/paprika:setup" not in said


def test_an_unfinished_setup_names_what_is_left(paprika_home: Path) -> None:
    setup.record(setup.Step.CREDENTIALS)

    said = " ".join(primer.facts(TODAY))

    assert "unfinished" in said
    assert "library" in said


def test_a_finished_setup_reports_the_four_facts(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["write", "profile", "set", "allergies+=peanuts"])
    runner.invoke(app, ["write", "pantry", "confirm", "cumin"])

    said = "\n".join(primer.facts(TODAY))

    assert "Setup: complete." in said
    assert "Plan for" in said
    assert "Pantry last confirmed today." in said
    assert "Allergies: peanuts." in said


def test_the_plan_carries_literal_dates(signed_in: Path, seeded: FakePaprika) -> None:
    """ "Next week" is ambiguous on a Sunday. A date is not."""
    runner.invoke(app, ["sync"])

    said = "\n".join(primer.facts(TODAY))

    assert "Mon 24 Aug" in said
    assert "Roast Lemon Chicken" in said


def test_an_unanswered_allergy_line_is_omitted_rather_than_emptied(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """Absent is us not knowing. Empty would be us concluding."""
    runner.invoke(app, ["sync"])

    said = "\n".join(primer.facts(TODAY))

    assert "Allergies" not in said


def test_being_told_there_are_none_is_said_out_loud(
    signed_in: Path, seeded: FakePaprika
) -> None:
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["write", "profile", "set", "--no-allergies"])

    assert "Allergies: none in this household." in "\n".join(primer.facts(TODAY))


def test_the_facts_carry_no_verdicts(signed_in: Path, seeded: FakePaprika) -> None:
    """ "Last confirmed nine days ago" is a fact; "out of date" is a judgement."""
    runner.invoke(app, ["sync"])

    said = "\n".join(primer.facts(TODAY)).casefold()

    for verdict in ("out of date", "stale", "you should", "too old", "needs"):
        assert verdict not in said


def test_the_primer_is_one_block(paprika_home: Path) -> None:
    built = primer.build(REPO, TODAY)

    assert built.count("<EXTREMELY_IMPORTANT>") == 1
    assert built.startswith("<EXTREMELY_IMPORTANT>")
    assert built.rstrip().endswith("</EXTREMELY_IMPORTANT>")


def test_the_fence_holds_its_ceiling() -> None:
    """Set before the content, so a later idea trades rather than appends."""
    text = (REPO / "skills" / "using-paprika" / "SKILL.md").read_text(encoding="utf-8")
    body = text.split("---", 2)[2].strip()

    assert len(body.splitlines()) <= primer.MAX_FENCE_LINES


def test_the_fence_bans_reads_as_well_as_writes() -> None:
    """The damage from a read is authority, not corruption."""
    body = (REPO / "skills" / "using-paprika" / "SKILL.md").read_text(encoding="utf-8")

    assert "Never call Paprika's web service directly" in body
    assert "Never open, edit or create" in body
    # And the dev hatch is the working directory rather than a flag.
    assert "working directory" in body


def test_the_fence_carries_both_backstops() -> None:
    body = (REPO / "skills" / "using-paprika" / "SKILL.md").read_text(encoding="utf-8")

    assert "allergy is never a preference" in body
    assert "No number without knowing where it came from" in body


def test_the_primer_lists_no_capabilities() -> None:
    """The roster is free — skill descriptions load themselves. Hence help."""
    body = (REPO / "skills" / "using-paprika" / "SKILL.md").read_text(encoding="utf-8")

    named = [name for name in ("plan-week", "grocery-list", "pantry", "find-recipe")]
    assert not [name for name in named if name in body]


def test_the_hook_starts_cleanly_on_a_missing_store(tmp_path: Path) -> None:
    result = subprocess.run(
        [str(REPO / "hooks" / "session-start.sh")],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PAPRIKA_HOME": str(tmp_path / "nothing")},
    )

    assert result.returncode == 0
    assert "EXTREMELY_IMPORTANT" in result.stdout


def test_the_hook_starts_cleanly_on_a_corrupt_store(tmp_path: Path) -> None:
    home = tmp_path / "broken"
    home.mkdir()
    (home / "state.toml").write_text("broken = [", encoding="utf-8")
    (home / "profile.toml").write_text("also [ broken", encoding="utf-8")
    (home / "cache.sqlite3").write_bytes(b"not a database at all")

    result = subprocess.run(
        [str(REPO / "hooks" / "session-start.sh")],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PAPRIKA_HOME": str(home)},
    )

    assert result.returncode == 0
    assert "/paprika:help" in result.stdout


def test_the_hook_starts_cleanly_with_nothing_installed(tmp_path: Path) -> None:
    """Finding no command is a sentence, not an error and not silence.

    This test used to assert silence. Silence is what #78 turned out to be:
    indistinguishable from a plugin working perfectly, which is why nobody
    noticed the primer had never once appeared on an installed machine.
    """
    # A PATH with bash on it and nothing of ours, and a plugin root holding no
    # command of its own — the machine where this plugin is not really
    # installed.
    somewhere = tmp_path / "bin"
    somewhere.mkdir()
    (somewhere / "bash").symlink_to(shutil.which("bash") or "/bin/bash")
    elsewhere = tmp_path / "root"
    elsewhere.mkdir()

    result = subprocess.run(
        [str(REPO / "hooks" / "session-start.sh")],
        capture_output=True,
        text=True,
        env={
            "PATH": str(somewhere),
            "PAPRIKA_HOME": str(tmp_path),
            "CLAUDE_PLUGIN_ROOT": str(elsewhere),
        },
    )

    assert result.returncode == 0
    assert "uv tool install" in result.stdout


def test_the_primer_stays_inside_its_budget(
    signed_in: Path, seeded: FakePaprika
) -> None:
    """About fifty-four milliseconds, measured — what the core/CLI seam buys.

    Measured **cold, in a fresh interpreter**, because that is the only way the
    session ever runs it and because almost all of the cost is import rather
    than work. Timing a warm build would report a fraction of a millisecond and
    prove nothing at all.

    The interpreter's own startup is excluded: a hook in any language pays that,
    and it is not what the seam was protecting.
    """
    runner.invoke(app, ["sync"])
    measure = (
        "import time, sys;"
        " t = time.perf_counter();"
        " import paprika_core.primer as p;"
        " p.build(__import__('pathlib').Path(sys.argv[1]));"
        " print((time.perf_counter() - t) * 1000)"
    )

    timings = []
    for _ in range(3):
        result = subprocess.run(
            [sys.executable, "-c", measure, str(REPO)],
            capture_output=True,
            text=True,
            cwd=REPO,
            env={**os.environ, "PAPRIKA_HOME": str(signed_in)},
        )
        assert result.returncode == 0, result.stderr
        timings.append(float(result.stdout.strip()))

    best = min(timings)
    assert best < 54.0, f"{best:.1f} ms cold, budget 54 ms"


def test_the_primer_never_pays_for_the_network(paprika_home: Path) -> None:
    """Importing the Pantry's write path costs 99 ms on its own."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import paprika_core.primer;"
            " print('httpx' in sys.modules, 'typer' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.stdout.strip() == "False False", result.stdout


# --- The hook on a machine where this plugin is actually installed -----------
#
# Every hook test above this line leaves CLAUDE_PLUGIN_ROOT unset, so the script
# resolves to this checkout and finds its `.venv`. That shape does not exist on
# an installed plugin, and testing only it is how #78 shipped.


def _installed_plugin(tmp_path: Path) -> Path:
    """Lay out a plugin the way an install leaves it: no venv, no source.

    Args:
        tmp_path: The test's directory.

    Returns:
        Path: A plugin root holding the manifests and the skills, and nothing
            that could run Python.
    """
    root = tmp_path / "installed"
    (root / ".claude-plugin").mkdir(parents=True)
    shutil.copytree(REPO / "skills", root / "skills")
    shutil.copy(REPO / ".claude-plugin" / "plugin.json", root / ".claude-plugin")
    shutil.copytree(REPO / "hooks", root / "hooks")
    return root


def _shim_on_path(tmp_path: Path) -> str:
    """Return the PATH an install really leaves behind.

    `uv tool install` links **one command** into `~/.local/bin`; the venv's own
    `bin` never joins PATH. So `python3` here is the system one, which does not
    have this plugin's dependencies — and that difference is the whole of #78.
    Putting the venv's `bin` on PATH instead would hide the bug being tested.

    Args:
        tmp_path: The test's directory.

    Returns:
        str: A PATH value.
    """
    shim = tmp_path / "local-bin"
    shim.mkdir(exist_ok=True)
    (shim / "paprika").symlink_to(Path(sys.executable).parent / "paprika")
    return f"{shim}:/usr/bin:/bin"


def test_the_hook_speaks_on_an_installed_plugin(tmp_path: Path) -> None:
    """The regression for #78: no venv beside the plugin, and it still runs."""
    root = _installed_plugin(tmp_path)

    result = subprocess.run(
        [str(root / "hooks" / "session-start.sh")],
        capture_output=True,
        text=True,
        env={
            "PATH": _shim_on_path(tmp_path),
            "PAPRIKA_HOME": str(tmp_path / "home"),
            "CLAUDE_PLUGIN_ROOT": str(root),
        },
    )

    assert result.returncode == 0
    assert "EXTREMELY_IMPORTANT" in result.stdout
    # The fence itself, not merely a wrapper around nothing.
    assert "paprika" in result.stdout


def test_the_hook_says_so_when_the_command_is_missing(tmp_path: Path) -> None:
    """Not installed and working perfectly must not look the same.

    Silence here is what let #78 pass for a verified hook: the script returns
    zero either way, so only what it *says* can tell the two apart.
    """
    root = _installed_plugin(tmp_path)
    bare = tmp_path / "bin"
    bare.mkdir()
    (bare / "bash").symlink_to(shutil.which("bash") or "/bin/bash")

    result = subprocess.run(
        [str(root / "hooks" / "session-start.sh")],
        capture_output=True,
        text=True,
        env={
            "PATH": str(bare),
            "PAPRIKA_HOME": str(tmp_path / "home"),
            "CLAUDE_PLUGIN_ROOT": str(root),
        },
    )

    assert result.returncode == 0
    assert "uv tool install" in result.stdout
    assert "not on PATH" in result.stdout


def test_the_hook_runs_the_command_rather_than_a_file_of_its_own() -> None:
    """One entry point. A second one is a second set of dependencies to have."""
    script = (REPO / "hooks" / "session-start.sh").read_text(encoding="utf-8")

    assert "primer" in script
    assert not (REPO / "hooks" / "session_start.py").exists()
    # Nothing may reach the source tree directly: an interpreter that can import
    # `paprika_core` from `src/` is one that has skipped installing it.
    assert "src" not in script
    assert "session_start.py" not in script


# --- Two halves, two version lines -------------------------------------------
#
# The skills come from `/plugin update` and the command from `uv tool upgrade`.
# Nothing makes those happen together, so the primer is where they are compared
# — it is the one thing guaranteed to be read before she asks for anything.


def test_the_primer_says_when_the_two_halves_disagree(
    paprika_home: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(primer, "installed_version", lambda: "0.1.0")

    lines = primer.mismatch_lines(_plugin_at(paprika_home, "0.4.0"))

    assert len(lines) == 1
    said = lines[0]
    # Both numbers, so whoever reads it knows which way round to fix it.
    assert "0.4.0" in said and "0.1.0" in said
    assert "uv tool upgrade" in said


def test_the_primer_is_quiet_when_the_two_halves_agree(
    paprika_home: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(primer, "installed_version", lambda: "0.4.0")

    assert primer.mismatch_lines(_plugin_at(paprika_home, "0.4.0")) == []


def test_a_version_it_cannot_read_is_not_a_complaint(
    paprika_home: Path, monkeypatch: Any
) -> None:
    """Unknown is not disagreement. Guessing here cries wolf every session."""
    monkeypatch.setattr(primer, "installed_version", lambda: None)

    assert primer.mismatch_lines(_plugin_at(paprika_home, "0.4.0")) == []

    monkeypatch.setattr(primer, "installed_version", lambda: "0.4.0")
    assert primer.mismatch_lines(paprika_home / "no-plugin-here") == []


def _plugin_at(root: Path, version: str) -> Path:
    """Write a plugin manifest claiming a version.

    Args:
        root: Where to put it.
        version: What it should claim.

    Returns:
        Path: The plugin root.
    """
    manifest = root / ".claude-plugin"
    manifest.mkdir(parents=True, exist_ok=True)
    (manifest / "plugin.json").write_text(
        json.dumps({"name": "paprika", "version": version}), encoding="utf-8"
    )
    return root


def test_the_mismatch_is_carried_into_what_the_session_sees(
    paprika_home: Path, monkeypatch: Any
) -> None:
    """A fact nobody is shown is not a fact."""
    monkeypatch.setattr(primer, "installed_version", lambda: "0.1.0")
    shutil.copytree(REPO / "skills", paprika_home / "skills")

    block = primer.build(_plugin_at(paprika_home, "0.4.0"), TODAY)

    assert "uv tool upgrade" in block


# --- The command the hook actually calls -------------------------------------


def test_the_primer_command_prints_the_block(paprika_home: Path) -> None:
    result = runner.invoke(app, ["primer", "--root", str(REPO)])

    assert result.exit_code == 0
    assert result.stdout.startswith("<EXTREMELY_IMPORTANT>")
    assert "Never call Paprika's web service directly" in result.stdout


def test_the_primer_command_survives_a_root_that_is_not_there(
    paprika_home: Path,
) -> None:
    """It runs before she has said anything, so it may never be the thing that
    stops a session starting."""
    result = runner.invoke(app, ["primer", "--root", str(paprika_home / "gone")])

    assert result.exit_code == 0


def test_the_primer_command_returns_no_envelope(paprika_home: Path) -> None:
    """The one command that is not part of the contract, deliberately.

    Its reader is a shell hook that injects stdout verbatim, not a skill parsing
    JSON. Wrapping it would mean the hook needed a JSON parser to say anything.
    """
    result = runner.invoke(app, ["primer", "--root", str(REPO)])

    assert '"ok"' not in result.stdout
