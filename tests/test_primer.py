"""The primer — four facts, no verdicts, and a session that always starts.

The hook is a command with an output contract and a measured budget, so it is
tested here rather than being the one thing nobody can check.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

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


def test_the_hook_starts_cleanly_with_no_interpreter_at_all(tmp_path: Path) -> None:
    """Finding no python is silence rather than an error on her screen."""
    # A PATH with bash on it and no python at all, and a plugin root with no
    # interpreter of its own — the machine where this plugin is not really
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
    assert result.stdout == ""


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
