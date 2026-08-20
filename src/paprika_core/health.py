"""How tidy her library is — arithmetic, so the question is free to ask.

No judgement, no tokens, instant, deterministic, and **incapable of being wrong
in an interesting way**. Only clustering and duplicate-finding need the Scan, and
the Scan is dispatched once she picks a job — so asking how things look costs
nothing and re-asking later is the only progress signal a cleanup spread over
several evenings ever gets.

Five classes, and two of them are information rather than work. An empty
category is a fact about her scheme, not a job; a missing photo is not ours to
fix. Reporting them and acting on them are different things.

**A health report that always finds something is one she stops believing.** So
with nothing to do it says one sentence and proposes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from paprika_core.mirror import Mirror

#: How many jobs the report opens with. Three lines, not a dashboard — the
#: biggest win, the second, and then stop.
SHOWN = 2


@dataclass(frozen=True)
class Finding:
    """One thing about her library that could be better.

    Attributes:
        kind: What sort of untidiness.
        recipes: How many recipes it affects, which is what "biggest" means.
        actionable: Whether this is a job she can pick, or only information.
    """

    kind: str
    recipes: int
    actionable: bool = True


def _normalised(name: str) -> str:
    """Reduce a title to something two copies of it would share.

    Args:
        name: The recipe's title.

    Returns:
        str: Lowercased words, punctuation dropped.
    """
    # Apostrophes are dropped rather than split on, so `Mum's Lasagne` and
    # `Mums Lasagne` are the same title — which is exactly the pair a decade of
    # imports produces.
    return " ".join(re.findall(r"[a-z0-9]+", re.sub(r"['\u2019]", "", name.casefold())))


def report(mirror: Mirror) -> list[Finding]:
    """Count what could be tidied, biggest first.

    Ordered by how many recipes are affected, because that is what makes a job
    worth an evening. Uncategorised wins a tie against filed loosely: **a hole
    beats a preference**, since filing something only at a root may well have
    been deliberate.

    Args:
        mirror: The Mirror to read.

    Returns:
        list[Finding]: Everything worth saying, in the order to say it.
    """
    categories = mirror.categories()
    parents = {node.parent_uid for node in categories if node.parent_uid}
    known = {node.uid for node in categories}
    recipes = mirror.recipes()

    uncategorised = 0
    loosely = 0
    for recipe in recipes:
        filed = [uid for uid in recipe.categories if uid in known]
        if not filed:
            uncategorised += 1
            continue
        # Filed only at roots that have children of their own: the recipes it
        # belongs with live at a leaf, and this one is sitting above them.
        if all(uid in parents for uid in filed):
            loosely += 1

    seen: dict[str, int] = {}
    for recipe in recipes:
        key = _normalised(recipe.name)
        if key:
            seen[key] = seen.get(key, 0) + 1
    duplicates = sum(count for count in seen.values() if count > 1)

    counts = {uid: 0 for uid in known}
    for recipe in recipes:
        for uid in recipe.categories:
            if uid in counts:
                counts[uid] += 1
    thin = sum(1 for total in counts.values() if total <= 1)

    findings = [
        Finding("uncategorised", uncategorised),
        Finding("filed_loosely", loosely),
        Finding("possible_duplicates", duplicates),
        # Information, never a bulk job. An empty category is a fact about her
        # scheme rather than something to fix, and a missing photo is not ours.
        Finding("thin_categories", thin, actionable=False),
    ]
    worth_saying = [finding for finding in findings if finding.recipes]
    order = {"uncategorised": 0, "filed_loosely": 1}
    worth_saying.sort(key=lambda f: (-f.recipes, order.get(f.kind, 2)))
    return worth_saying


def is_tidy(findings: list[Finding]) -> bool:
    """Say whether there is anything for her to actually do.

    Information does not make a library untidy. Thin categories are a fact about
    her scheme, so a library with several of them and nothing else to fix gets
    the one sentence.

    Args:
        findings: Everything the report found.

    Returns:
        bool: Whether there is no job worth offering.
    """
    return not any(finding.actionable for finding in findings)


def jobs(findings: list[Finding]) -> list[Finding]:
    """Return the jobs she could actually pick, biggest first.

    Args:
        findings: Everything the report found.

    Returns:
        list[Finding]: At most two, because the report is three lines rather
            than a dashboard.
    """
    return [finding for finding in findings if finding.actionable][:SHOWN]
