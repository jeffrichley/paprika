"""Seam B — the plugin's assets read as data.

Two of the layout rules here are silent when broken: a plugin with anything but
``plugin.json`` inside ``.claude-plugin/``, or with ``skills/`` nested inside it,
does not fail loudly — it just quietly loads nothing. So they are asserted rather
than remembered.

The agent rules are asserted against whatever ``agents/`` holds, which is nothing
yet. That is deliberate: the rule that neither agent may hold a write tool has to
be in place *before* the agents are, or the first one written is the one nobody
checked.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / ".claude-plugin" / "plugin.json"


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Read the plugin manifest.

    Returns:
        dict[str, Any]: The parsed manifest.
    """
    body: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return body


def test_the_manifest_exists_and_parses(manifest: dict[str, Any]) -> None:
    assert manifest["name"] == "paprika"
    assert manifest["version"]
    assert manifest["description"]


def test_the_manifest_directory_holds_nothing_else() -> None:
    """``.claude-plugin/`` contains ``plugin.json`` and nothing else."""
    contents = sorted(p.name for p in MANIFEST.parent.iterdir())

    assert contents == ["plugin.json"]


def test_the_asset_directories_live_at_the_plugin_root() -> None:
    """``skills/``, ``agents/`` and ``hooks/`` are siblings of ``.claude-plugin/``."""
    for name in ("skills", "agents", "hooks"):
        assert (REPO / name).is_dir(), f"{name}/ is missing from the plugin root"
        assert not (
            REPO / ".claude-plugin" / name
        ).exists(), f"{name}/ must not be nested inside .claude-plugin/"


def test_every_manifest_path_is_relative_and_resolves(manifest: dict[str, Any]) -> None:
    """All manifest paths start with ``./`` and point at something that exists."""
    for key in ("commands", "agents", "skills", "hooks", "outputStyles", "mcpServers"):
        value = manifest.get(key)
        if value is None:
            continue
        paths = value if isinstance(value, list) else [value]
        for path in paths:
            assert isinstance(path, str)
            assert path.startswith("./"), f"{key}: {path} must start with ./"
            assert (REPO / path).exists(), f"{key}: {path} does not exist"


def test_the_hook_configuration_is_valid_json() -> None:
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))

    assert isinstance(hooks, dict)
    assert isinstance(hooks.get("hooks", {}), dict)


def test_every_hook_command_goes_through_the_plugin_root() -> None:
    """A hook that hard-codes a path breaks the moment the plugin is installed."""
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))

    for matchers in hooks.get("hooks", {}).values():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                if hook.get("type") == "command":
                    assert "${CLAUDE_PLUGIN_ROOT}" in hook["command"]


#: Holds references that skills load, rather than skills of its own.
SHARED = "shared"


def test_every_skill_directory_holds_a_skill_file() -> None:
    """A skill directory without ``SKILL.md`` is a skill that silently never loads."""
    for entry in (REPO / "skills").iterdir():
        if entry.is_dir() and entry.name != SHARED:
            assert (entry / "SKILL.md").is_file(), f"{entry.name} has no SKILL.md"


def test_no_agent_definition_grants_a_write_tool() -> None:
    """Both agents are a large read and a small return. Neither may write.

    Asserted now, while ``agents/`` is empty, so the rule predates the agents.
    """
    for definition in (REPO / "agents").glob("*.md"):
        text = definition.read_text(encoding="utf-8").lower()
        for forbidden in ("write", "edit", "notebookedit", "paprika write"):
            assert (
                forbidden not in text
            ), f"{definition.name} appears to grant {forbidden}"


def test_the_console_script_is_declared() -> None:
    """``paprika`` is a console script over the installed package, not a shebang."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")

    assert 'paprika = "paprika_core.cli:main"' in pyproject
    assert 'requires-python = ">=3.11"' in pyproject


def test_there_is_one_lockfile_and_one_project() -> None:
    """One venv, one lockfile — not PEP 723 inline metadata per script."""
    assert (REPO / "uv.lock").is_file()
    assert len(list(REPO.glob("*/pyproject.toml"))) == 0


def _skill_files() -> list[Path]:
    """Return every skill definition in the plugin.

    Returns:
        list[Path]: The ``SKILL.md`` files.
    """
    return sorted((REPO / "skills").glob("*/SKILL.md"))


def _skill_prose() -> list[Path]:
    """Return everything a skill puts in front of the model.

    Includes the shared references skills load, which are prose she can be
    affected by just as much as a skill is.

    Returns:
        list[Path]: The Markdown files.
    """
    return sorted((REPO / "skills").glob("**/*.md"))


def test_every_skill_declares_a_name_and_a_description() -> None:
    """Without frontmatter a skill silently never fires."""
    for skill in _skill_files():
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill.parent.name} has no frontmatter"
        front = text.split("---", 2)[1]
        assert "\nname:" in front, f"{skill.parent.name} declares no name"
        assert "\ndescription:" in front, f"{skill.parent.name} declares no description"


def test_a_skill_description_says_when_rather_than_how() -> None:
    """A description that summarises the workflow becomes a shortcut past the body."""
    for skill in _skill_files():
        front = skill.read_text(encoding="utf-8").split("---", 2)[1]
        description = front.split("description:", 1)[1].split("\n")[0].strip()
        assert description.startswith("Use when"), skill.parent.name
        assert len(description) < 1024, skill.parent.name


def test_a_skill_name_matches_its_directory() -> None:
    for skill in _skill_files():
        front = skill.read_text(encoding="utf-8").split("---", 2)[1]
        name = front.split("name:", 1)[1].split("\n")[0].strip()
        assert name == skill.parent.name


#: Words that mean Paprika's machinery. A skill that starts using one has been
#: handed something the CLI was supposed to keep, and the fence has eroded.
MECHANIC_WORDS = (
    "hash",
    "uid",
    "jwt",
    "bearer",
    "http",
    "in_trash",
    "sync counter",
    "state.toml",
    ".env",
    "cache.sqlite3",
    "undo.sqlite3",
    "~/.paprika",
)


def test_no_skill_text_leaks_paprikas_mechanics() -> None:
    """The fence holds because a skill is never handed the mechanics to leak.

    This is the test that fails when that stops being true.
    """
    for skill in _skill_prose():
        body = skill.read_text(encoding="utf-8").casefold()
        for word in MECHANIC_WORDS:
            assert word not in body, f"{skill.parent.name} mentions {word!r}"


def test_no_skill_asks_her_to_touch_a_file() -> None:
    """She is not a developer. A skill that hands her a file has already failed."""
    for skill in _skill_files():
        body = skill.read_text(encoding="utf-8").casefold()
        for phrase in ("open the file", "edit the file", "create a file", "chmod"):
            assert phrase not in body, f"{skill.parent.name} says {phrase!r}"


def test_a_skill_only_reaches_paprika_through_the_command() -> None:
    """The fence bans direct API calls, so no skill may name a Paprika URL."""
    for skill in _skill_files():
        body = skill.read_text(encoding="utf-8").casefold()
        assert "paprikaapp.com" not in body
        assert "/api/v2/" not in body


#: A similarity score is a second judge competing with the model — a confident
#: number with no Provenance behind it, and no honest way to show her why a
#: vector thought a dish was mild. The decision is that none exists; this is
#: what stops one arriving quietly with a dependency.
SECOND_JUDGE = (
    "embedding",
    "vector store",
    "vectorstore",
    "faiss",
    "chromadb",
    "sentence-transformers",
    "cosine_similarity",
    "similarity_score",
)


def test_nothing_scores_a_recipe_against_a_query() -> None:
    """No embedding, no vector store, no similarity score, anywhere."""
    offenders: list[str] = []
    for module in sorted((REPO / "src").glob("**/*.py")):
        text = module.read_text(encoding="utf-8").casefold()
        offenders += [f"{module.name}: {word}" for word in SECOND_JUDGE if word in text]

    assert not offenders, "a second judge appeared:\n" + "\n".join(offenders)


def test_no_dependency_brings_a_second_judge_with_it() -> None:
    """The likeliest way one arrives is as somebody's convenient library."""
    locked = (REPO / "uv.lock").read_text(encoding="utf-8").casefold()

    for package in ("faiss", "chromadb", "sentence-transformers", "pgvector"):
        assert f'name = "{package}"' not in locked, f"{package} is in the lockfile"


#: The words the week-planning prototype ran a whole session without using. The
#: result was structural rather than stylistic — a skill cannot leak what it was
#: never handed — and this is what keeps it that way.
NEVER_SAID = (
    "uid",
    "hash",
    "sync",
    "token",
    "api",
    "cache",
    "tier",
    "provenance",
    "200",
)


def test_no_skill_says_any_of_the_words_the_prototype_never_needed() -> None:
    """Nine words, and a whole session was run without one of them appearing."""
    offenders: list[str] = []
    for skill in _skill_prose():
        for line in skill.read_text(encoding="utf-8").splitlines():
            # Code is for the model rather than for her, and a command's name
            # is not a word said out loud — so fenced blocks and inline spans
            # come out before the prose is read. Without this the scan flags its
            # own counter-examples, which is how a guard stops being trusted.
            if line.lstrip().startswith("```"):
                continue
            prose = re.sub(r"`[^`]*`", " ", line)
            words = re.findall(r"[a-z0-9]+", prose.casefold())
            offenders += [
                f"{skill.parent.name}: {word} in {line.strip()[:60]!r}"
                for word in NEVER_SAID
                if word in words
            ]

    assert not offenders, "a mechanic word reached the session:\n" + "\n".join(
        offenders
    )


def test_the_cooking_judgement_reference_exists_and_is_loaded() -> None:
    """ADR 0003: cooking judgement is a shared reference, never an agent."""
    reference = REPO / "skills" / "shared" / "cooking-judgement.md"

    assert reference.is_file()
    # And the skill that needs it says so, rather than hoping.
    planner = (REPO / "skills" / "plan-week" / "SKILL.md").read_text(encoding="utf-8")
    assert "cooking-judgement.md" in planner
