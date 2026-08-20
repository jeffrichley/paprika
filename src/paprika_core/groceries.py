"""The week's shopping, minus what is already in the cupboard.

The subtraction happens **here** rather than in a conversation, because it has to
be identical every time. What she asked for is "stop making me buy a fourth jar
of cumin", and that is arithmetic over two lists rather than a judgement about
groceries.

The matching is lexical and deliberately only that. A pantry entry matches an
ingredient line when its words appear in the line as words — ``cumin`` matches
``2 tsp ground cumin`` and does not match ``cuminseed bread``. Longer pantry
names are tried first, so ``olive oil`` wins over ``oil`` when she has both.

There is no score anywhere, and no attempt to be clever about what a cook would
mean. A confident near-match is how she ends up not buying something she needed,
which is a worse failure than the jar of cumin.

**The age gates whether the list explains itself, never whether it subtracts.**
A stale Pantry is still the best information there is; what changes is that the
list says out loud what it took off and how old that belief was.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from paprika_core.http import PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.undo import Run

GROCERIES_PATH = "/api/v2/sync/groceries/"
GROCERY_LISTS_PATH = "/api/v2/sync/grocerylists/"

#: The kind this writes, for the envelope's `changed` map.
KIND = "groceries"

#: How old the Pantry may be before the list explains its own subtractions.
#: Overridable in her one hand-editable file, because a number that lives only
#: in a prompt is a number nobody can tune and no test can pin.
DEFAULT_STALE_DAYS = 7.0


@dataclass(frozen=True)
class Wanted:
    """One thing to buy.

    Attributes:
        line: The ingredient exactly as her recipe writes it. Her words, kept.
        ingredient: A lowercased form, which is what Paprika files by aisle.
        recipe: What it is for, so a list she is reading makes sense.
    """

    line: str
    ingredient: str
    recipe: str


@dataclass(frozen=True)
class Draft:
    """A shopping list, and what was taken off it.

    Attributes:
        wanted: What to buy.
        subtracted: What she already has, by pantry name.
        pantry_age_days: How old that belief is, or ``None`` if never confirmed.
        pantry_stale: Whether the list should explain itself.
    """

    wanted: list[Wanted] = field(default_factory=list)
    subtracted: list[str] = field(default_factory=list)
    pantry_age_days: float | None = None
    pantry_stale: bool = True


def _words(text: str) -> list[str]:
    """Split text into comparable words.

    Args:
        text: Anything.

    Returns:
        list[str]: Lowercased alphanumeric words.
    """
    return re.findall(r"[a-z0-9]+", text.casefold())


def _holds(line_words: list[str], pantry_words: list[str]) -> bool:
    """Say whether an ingredient line contains a pantry entry's words in order.

    Whole words, in sequence. ``cumin`` is in ``2 tsp ground cumin`` and is not
    in ``cuminseed bread`` — the second is what a substring match would get
    wrong, and getting it wrong means she does not buy something she needed.

    Args:
        line_words: The ingredient line's words.
        pantry_words: The pantry entry's words.

    Returns:
        bool: Whether she already has it.
    """
    if not pantry_words:
        return False
    span = len(pantry_words)
    return any(
        line_words[start : start + span] == pantry_words
        for start in range(len(line_words) - span + 1)
    )


def _ingredient_lines(body: dict[str, Any]) -> list[str]:
    """Split a recipe's ingredients into lines.

    Paprika stores them as one newline-separated string rather than a list, so
    this is where that becomes a list and nowhere else.

    Args:
        body: The whole recipe.

    Returns:
        list[str]: One line per ingredient, blanks and headings dropped.
    """
    raw = str(body.get("ingredients") or "")
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        # A line with no letters is a separator; one ending in a colon is a
        # heading like "For the sauce:" rather than something to buy.
        if not stripped or not re.search(r"[a-z]", stripped, re.IGNORECASE):
            continue
        if stripped.endswith(":"):
            continue
        lines.append(stripped)
    return lines


def draft(mirror: Mirror, since: str = "", until: str = "") -> Draft:
    """Work out what to buy for the Plan, minus what she already has.

    Args:
        mirror: The Mirror to read.
        since: First day, ``YYYY-MM-DD``.
        until: Last day, ``YYYY-MM-DD``.

    Returns:
        Draft: What to buy, what was taken off, and how old that belief is.
    """
    from paprika_core import profile, store

    have = [(item.ingredient, _words(item.ingredient)) for item in mirror.pantry()]
    # Longest first, so `olive oil` is matched before `oil` when she has both.
    have.sort(key=lambda entry: len(entry[1]), reverse=True)

    wanted: list[Wanted] = []
    subtracted: list[str] = []
    seen: set[str] = set()

    for meal in mirror.meals(since, until):
        if meal.recipe_handle is None:
            continue
        body = mirror.recipe_body(meal.recipe_handle)
        if body is None:
            continue
        for line in _ingredient_lines(body):
            line_words = _words(line)
            already = next(
                (name for name, words in have if _holds(line_words, words)), None
            )
            if already is not None:
                if already not in subtracted:
                    subtracted.append(already)
                continue
            key = " ".join(line_words)
            if key in seen:
                continue
            seen.add(key)
            wanted.append(Wanted(line=line, ingredient=key, recipe=meal.name))

    age = store.pantry_age_days()
    threshold = _threshold(profile.read())
    return Draft(
        wanted=wanted,
        subtracted=subtracted,
        pantry_age_days=age,
        # Never confirmed counts as stale: the list should say what it assumed.
        pantry_stale=age is None or age > threshold,
    )


def _threshold(read: Any) -> float:
    """Return how old the Pantry may be before a list explains itself.

    Args:
        read: The Profile.

    Returns:
        float: Days, from her own file when she has set one.
    """
    stated = read.pantry_stale_days
    return float(stated) if isinstance(stated, (int, float)) else DEFAULT_STALE_DAYS


def default_list_uid(client: PaprikaClient) -> str:
    """Return the grocery list to add to.

    Args:
        client: A signed-in client.

    Returns:
        str: Her default list, or the first one she has. Empty when she has
            none, which the caller must treat as a reason not to write.
    """
    lists = client.get(GROCERY_LISTS_PATH, "reading your shopping lists")
    rows = (
        [row for row in lists if isinstance(row, dict)]
        if isinstance(lists, list)
        else []
    )
    for row in rows:
        if row.get("is_default"):
            return str(row.get("uid") or "")
    return str(rows[0].get("uid") or "") if rows else ""


def push(client: PaprikaClient, wanted: list[Wanted], *, run: Run) -> list[str]:
    """Put the list into Paprika's own groceries.

    The plugin builds no list of its own — this is her list, in her app, which
    is where she already shops from.

    Args:
        client: A signed-in client.
        wanted: What to buy.
        run: The Run to capture Pre-images into.

    Returns:
        list[str]: What was added, in order.

    Raises:
        PaprikaError: On anything the wire says.
    """
    from paprika_core.errors import Code, PaprikaError

    list_uid = default_list_uid(client)
    if not list_uid:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            "There's no shopping list in Paprika to add these to.",
            detail="account has no grocery list",
        )

    entries: list[dict[str, Any]] = []
    for item in wanted:
        entry = {
            "uid": str(uuid.uuid4()).upper(),
            "list_uid": list_uid,
            "name": item.line,
            "ingredient": item.ingredient,
            "quantity": "",
            "instruction": "",
            "purchased": False,
            # Empty so Paprika files it by her own aisles rather than ours.
            "aisle": "",
            "aisle_uid": "",
            "recipe_uid": None,
            "recipe": item.recipe,
            "order_flag": 0,
            "separate": False,
        }
        run.capture(KIND, str(entry["uid"]), item.line, dict(entry, purchased=True))
        entries.append(entry)

    if entries:
        client._post_object(GROCERIES_PATH, entries, "adding to your shopping list")
        for entry in entries:
            run.mark_landed(KIND, str(entry["uid"]))
    log_event("groceries_push", count=len(entries))
    return [item.line for item in wanted]


def restore(client: PaprikaClient, body: dict[str, Any]) -> None:
    """Put a grocery entry back exactly as it was.

    Marking one purchased is the only removal this API has, so undoing an added
    item is posting it back as bought rather than deleting it.

    Args:
        client: A signed-in client.
        body: The Pre-image.
    """
    client._post_object(GROCERIES_PATH, [dict(body)], "putting your list back")
