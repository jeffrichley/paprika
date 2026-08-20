"""Drafts read out of files, before any of them is a recipe.

They live in their own directory under the store's **disposable** tier, not in
the Mirror. Work in progress and a stale copy of Paprika are two different kinds
of staleness, and putting them in one place would mean a routine rebuild of one
throws away the other.

Each draft is written as it is finished rather than at the end. Forty
photographed pages is the most expensive read in this plugin to have to do
twice, which is what makes "resumable because it commits incrementally" true
here rather than decorative.

**Nothing here can reach her library.** Saving a draft is deliberately outside
the ``paprika write …`` prefix, because it moves nothing of hers — which is also
what lets the Reader hold no write tool while still having somewhere to put what
it read. A draft becomes a recipe only by going through the chokepoint on her
yes, like everything else.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paprika_core import store

INTAKE_DIRNAME = "intake"

#: What a draft may carry. A whitelist, so a field invented on the far side of a
#: dispatch cannot arrive here by being mentioned.
FIELDS = (
    "name",
    "ingredients",
    "directions",
    "notes",
    "servings",
    "difficulty",
    "prep_time",
    "cook_time",
    "total_time",
    "source",
    "source_url",
)


@dataclass(frozen=True)
class Draft:
    """One file, read.

    Attributes:
        source: The file it came from, so a Walk knows what it has done.
        fields: What was on the page. Anything absent stays absent.
        gaps: Lines that could not be read, named. Marked in the recipe's own
            text as well, because that is what syncs to her phone.
        unusable: Set when the read produced no recipe at all — a page with no
            ingredients, or a file that is not a recipe. A plain sentence rather
            than a draft.
        read_at: When it was read.
    """

    source: str
    fields: dict[str, str] = field(default_factory=dict)
    gaps: tuple[str, ...] = ()
    unusable: str | None = None
    read_at: float = 0.0


def directory() -> Path:
    """Return where drafts are kept.

    Returns:
        Path: ``<home>/intake``. Disposable — cleared when a Walk ends.
    """
    return store.home() / INTAKE_DIRNAME


def _slug(source: str) -> str:
    """Return a stable filename for a draft.

    Args:
        source: The file it came from.

    Returns:
        str: A filename derived from the path, so re-reading the same file
            replaces its draft rather than making a second one.
    """
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16] + ".json"


def save(
    source: str,
    fields: dict[str, str],
    gaps: tuple[str, ...] = (),
    unusable: str | None = None,
) -> Draft:
    """Write one draft, immediately.

    Args:
        source: The file it came from.
        fields: What was on the page.
        gaps: Lines that could not be read.
        unusable: Why there is no draft, when there is none.

    Returns:
        Draft: What was written.
    """
    kept = {name: value for name, value in fields.items() if name in FIELDS}
    draft = Draft(
        source=source,
        fields=kept,
        gaps=tuple(gaps),
        unusable=unusable,
        read_at=time.time(),
    )
    target = directory()
    target.mkdir(parents=True, exist_ok=True)
    (target / _slug(source)).write_text(
        json.dumps(
            {
                "source": draft.source,
                "fields": draft.fields,
                "gaps": list(draft.gaps),
                "unusable": draft.unusable,
                "read_at": draft.read_at,
            }
        ),
        encoding="utf-8",
    )
    return draft


def _load(path: Path) -> Draft | None:
    """Read one draft from disk.

    Args:
        path: The draft file.

    Returns:
        Draft | None: The draft, or ``None`` when it cannot be read. A damaged
            draft is one file to read again, not a reason to fail a Walk.
    """
    try:
        body: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return Draft(
        source=str(body.get("source") or ""),
        fields=dict(body.get("fields") or {}),
        gaps=tuple(body.get("gaps") or ()),
        unusable=body.get("unusable"),
        read_at=float(body.get("read_at") or 0.0),
    )


def waiting() -> list[Draft]:
    """Return every draft read so far, oldest first.

    Returns:
        list[Draft]: The drafts. Empty when there are none, which is also what a
            machine that has never read a file looks like.
    """
    target = directory()
    if not target.is_dir():
        return []
    drafts = [_load(path) for path in sorted(target.glob("*.json"))]
    return sorted(
        [draft for draft in drafts if draft is not None], key=lambda d: d.read_at
    )


def done(source: str) -> None:
    """Forget one draft, because it has been dealt with.

    Args:
        source: The file it came from.
    """
    (directory() / _slug(source)).unlink(missing_ok=True)


def clear() -> int:
    """Forget every draft, because the Walk ended.

    Returns:
        int: How many were dropped.
    """
    target = directory()
    if not target.is_dir():
        return 0
    paths = list(target.glob("*.json"))
    for path in paths:
        path.unlink(missing_ok=True)
    return len(paths)
