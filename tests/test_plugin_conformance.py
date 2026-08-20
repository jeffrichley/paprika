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


def test_every_skill_directory_holds_a_skill_file() -> None:
    """A skill directory without ``SKILL.md`` is a skill that silently never loads."""
    for entry in (REPO / "skills").iterdir():
        if entry.is_dir():
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
