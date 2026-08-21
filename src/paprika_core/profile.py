"""``~/.paprika/profile.toml`` — the standing facts a plan is drawn against.

The **one hand-editable file** in the store, and TOML rather than JSON precisely
because TOML takes comments: it can explain itself next to her allergy list
instead of depending on somebody remembering the schema over the phone a year
later. Every machine write round-trips comment-preserving, because a naive
writer destroys her notes exactly the way a naive recipe post destroys `rating`
— same failure, same fix.

Being hand-editable, it may arrive mangled. The core tolerates that rather than
assuming its own writes are the only ones.

Three tiers, and flattening them is how a safety fact gets treated like a
preference. Allergies are structured, matchable and household-wide, because the
cook only gets one pot. Dislikes and loves are free text, per person. Targets
carry their direction in the field name so that nothing downstream can render a
goal minus a running total.

**Absent is not knowing; empty is concluding.** The two are held apart here
because a plan proposed as safe on the strength of a question nobody asked is
the worst thing this file could cause.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any

import tomlkit

from paprika_core import allergens, store
from paprika_core.errors import Code, PaprikaError

PROFILE_FILENAME = "profile.toml"

#: A target's key must end in this. The direction lives in the name, so there is
#: nowhere to put a number that something could later subtract from.
LEANING = "_leaning"

#: The only directions a target may lean.
DIRECTIONS = ("higher", "lower", "steady")

#: Free-text list fields a person carries.
PERSON_LISTS = ("dislikes", "loves", "allergies")

HEADER = """\
# paprika — your household
#
# This is the one file here you can change by hand, and it keeps whatever
# comments you leave in it. Everything else in this folder belongs to the
# program and says so.
#
# allergies    Household-wide, on purpose: the cook only gets one pot. Only
#              names the program can actually screen for are kept here, so if
#              something you typed is missing it was refused out loud rather
#              than quietly written down.
#
#              An absent list means nobody has been asked. An empty list means
#              the answer was "none". Those are different, and the program
#              treats them differently.
#
# people       One entry per person cooked for, each with what they dislike and
#              what they love. Free text — write it however you say it.
#
# rhythm       How the week actually goes: how many people, which nights are
#              fast, who is away, and how many days old what-you-have can get
#              before a shopping list starts explaining what it left off.
#
# targets      Directions, never numbers. A key reads like `protein_leaning`
#              and its value is higher, lower or steady — because a goal with a
#              number invites something to subtract a running total from it,
#              and the numbers here are never good enough for that.
"""


@dataclass(frozen=True)
class Person:
    """One person the household cooks for.

    Attributes:
        name: What she calls them.
        dislikes: Free text, in her words. Advisory, and worth weighing against
            everything else.
        loves: Free text, in her words.
        allergies: Hard constraints. On any meal this person eats, they bind
            the **whole** meal — the cook only gets one pot, and nobody is
            handed a separate dinner.
        usually: When a guest normally comes, in her words: ``Sundays``. Held so
            the question can be *"Monica on Sunday as usual?"* rather than an
            open one. **Recorded so it can be asked about, never so it can be
            assumed.** Empty for family, who are here anyway.
    """

    name: str
    dislikes: tuple[str, ...] = ()
    loves: tuple[str, ...] = ()
    allergies: tuple[str, ...] = ()
    usually: str = ""


@dataclass(frozen=True)
class Profile:
    """The standing facts, as they currently stand.

    Attributes:
        readable: Whether the file could be read at all. When false, nothing
            else here is a claim about anything.
        allergies_answered: Whether anybody has ever been asked. Held apart from
            an empty list on purpose.
        allergies: Canonical allergy names the filter can act on.
        people: The family, by name. They live here, so their allergies bind
            every meal and no attendance needs modelling for them.
        guests: People who come sometimes, by name, each carrying their own
            constraints. Applied only to meals they are actually at — which is
            what stops one guest's allergy constraining a week she is not part
            of.
        household_size: How many people, when stated.
        pantry_stale_days: How old what-she-has may be before a list explains
            itself. Hers to tune, because a number that lives only in a prompt
            is one nobody can change and no test can pin.
        fast_nights: Nights that have to be quick.
        away: Who is away this week.
        targets: Directional leanings, never numbers.
    """

    readable: bool = True
    allergies_answered: bool = False
    allergies: tuple[str, ...] = ()
    people: dict[str, Person] = field(default_factory=dict)
    guests: dict[str, Person] = field(default_factory=dict)
    household_size: int | None = None
    pantry_stale_days: float | None = None
    fast_nights: tuple[str, ...] = ()
    away: tuple[str, ...] = ()
    targets: dict[str, str] = field(default_factory=dict)

    @property
    def always_avoid(self) -> tuple[str, ...]:
        """Return what binds every meal, whoever is at the table.

        The household's own allergies plus every family member's. Family live
        here, so there is nothing to ask and nothing to model — their
        constraints simply hold.

        Returns:
            tuple[str, ...]: Allergy names, deduplicated, in a stable order.
        """
        found = list(self.allergies)
        for person in self.people.values():
            found += [name for name in person.allergies if name not in found]
        return tuple(found)

    @property
    def guests_to_ask_about(self) -> tuple[str, ...]:
        """Return the guests whose presence a week has to establish.

        Only those carrying an **allergy**. A guest with dislikes alone is worth
        knowing about and is not worth interrupting for: getting it wrong costs
        somebody a meal they did not love, not a hospital visit.

        Returns:
            tuple[str, ...]: Guest names, in the order stored.
        """
        return tuple(name for name, guest in self.guests.items() if guest.allergies)


def path() -> "store.Path":
    """Return the Profile's path.

    Returns:
        Path: ``<home>/profile.toml``.
    """
    return store.home() / PROFILE_FILENAME


def _document() -> tomlkit.TOMLDocument | None:
    """Read the file, saying so when it will not parse.

    Returns:
        tomlkit.TOMLDocument | None: The document, an empty one when the file is
            simply absent, or ``None`` when it exists and cannot be read.
    """
    target = path()
    try:
        if not target.is_file():
            return tomlkit.document()
        text = target.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return tomlkit.parse(text)
    except ValueError:
        return None


def _write(document: tomlkit.TOMLDocument) -> None:
    """Write the file back, comments and all.

    Args:
        document: The document to write.
    """
    store.ensure_home()
    target = path()
    body = tomlkit.dumps(document)
    if not body.lstrip().startswith("#"):
        body = HEADER + "\n" + body
    target.write_text(body, encoding="utf-8")


def _strings(value: Any) -> tuple[str, ...]:
    """Coerce a stored value into a tuple of strings.

    Args:
        value: Whatever was in the file, which a hand edit may have mangled.

    Returns:
        tuple[str, ...]: The strings in it, ignoring anything that is not one.
    """
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, (str, int, float)))


def read() -> Profile:
    """Read the standing facts.

    Returns:
        Profile: What is known. A file that cannot be read reports
            ``readable=False`` and claims nothing else — silence about a safety
            fact must never read as an all-clear.
    """
    document = _document()
    if document is None:
        return Profile(readable=False)

    allergies_raw = document.get("allergies")
    people: dict[str, Person] = {}
    stored_people = document.get("people")
    if isinstance(stored_people, dict):
        for name, entry in stored_people.items():
            if not isinstance(entry, dict):
                continue
            people[str(name)] = Person(
                name=str(name),
                dislikes=_strings(entry.get("dislikes")),
                loves=_strings(entry.get("loves")),
                allergies=_strings(entry.get("allergies")),
            )

    guests: dict[str, Person] = {}
    stored_guests = document.get("guests")
    if isinstance(stored_guests, dict):
        for name, entry in stored_guests.items():
            if not isinstance(entry, dict):
                continue
            guests[str(name)] = Person(
                name=str(name),
                dislikes=_strings(entry.get("dislikes")),
                loves=_strings(entry.get("loves")),
                allergies=_strings(entry.get("allergies")),
                usually=str(entry.get("usually") or ""),
            )

    rhythm = document.get("rhythm")
    rhythm = rhythm if isinstance(rhythm, dict) else {}
    size = rhythm.get("household_size")

    targets_raw = document.get("targets")
    targets = {
        str(key): str(value)
        for key, value in (targets_raw or {}).items()
        if isinstance(targets_raw, dict)
    }

    return Profile(
        readable=True,
        allergies_answered=isinstance(allergies_raw, list),
        allergies=_strings(allergies_raw),
        people=people,
        guests=guests,
        household_size=int(size) if isinstance(size, int) else None,
        pantry_stale_days=(
            float(stale)
            if isinstance(stale := rhythm.get("pantry_stale_days"), (int, float))
            else None
        ),
        fast_nights=_strings(rhythm.get("fast_nights")),
        away=_strings(rhythm.get("away")),
        targets=targets,
    )


def record_no_allergies() -> None:
    """Write down that the household has none.

    An empty list is an answer. Its absence is not, which is why this exists as
    something to say rather than something to leave undone.
    """
    document = _document() or tomlkit.document()
    document["allergies"] = []
    _write(document)


def _refuse(message: str, detail: str) -> PaprikaError:
    """Build the refusal used throughout this module.

    Args:
        message: One sentence fit to say to her.
        detail: The diagnostic, for the log.

    Returns:
        PaprikaError: The failure to raise.
    """
    return PaprikaError(Code.REFUSED_LOCALLY, message, detail=detail)


def _split(expression: str) -> tuple[str, str, str]:
    """Split a ``path=value`` expression into its parts.

    Args:
        expression: As typed, using ``=``, ``+=`` or ``-=``.

    Returns:
        tuple[str, str, str]: The path, the operator, and the value.

    Raises:
        PaprikaError: When it is not one of the three forms.
    """
    for operator in ("+=", "-=", "="):
        head, found, tail = expression.partition(operator)
        if found and head.strip():
            return head.strip(), operator, tail.strip()
    raise _refuse(
        "That change wasn't written in a way we could apply.",
        f"unparseable profile expression {expression!r}",
    )


def apply(expression: str) -> None:
    """Apply one named change to the Profile.

    A path expression rather than a file, for the same reason a recipe write
    takes a patch rather than an object: if this ever accepted a whole
    ``profile.toml``, the comments she wrote would be one careless caller away
    from gone.

    Args:
        expression: ``allergies+=peanuts``, ``people.sam.dislikes+=okra``,
            ``rhythm.household_size=4``, ``targets.protein_leaning=higher``.

    Raises:
        PaprikaError: When the path means nothing, the value is the wrong shape,
            or an allergy is one we cannot check for.
    """
    where, operator, value = _split(expression)
    document = _document()
    if document is None:
        raise _refuse(
            "Your household file can't be read, so nothing was changed.",
            f"unparseable {path()}",
        )

    parts = where.split(".")
    if parts[0] == "allergies":
        _apply_allergy(document, parts, operator, value)
    elif parts[0] in ("people", "guests"):
        _apply_person(document, parts, operator, value)
    elif parts[0] == "rhythm":
        _apply_rhythm(document, parts, operator, value)
    elif parts[0] == "targets":
        _apply_target(document, parts, operator, value)
    else:
        raise _refuse(
            "That isn't something kept about your household.",
            f"unknown profile path {where!r}",
        )
    _write(document)


def _list_at(holder: MutableMapping[str, Any], key: str) -> list[Any]:
    """Return a copy of a stored list, treating anything else as absent.

    The file is hand-editable, so what is at a key may not be a list at all.

    Args:
        holder: The document or table holding it.
        key: Which list.

    Returns:
        list[Any]: Its current contents, for the caller to amend and store back.
    """
    current = holder.get(key)
    return list(current) if isinstance(current, list) else []


def _apply_allergy(
    document: tomlkit.TOMLDocument, parts: list[str], operator: str, value: str
) -> None:
    """Add or remove a household allergy.

    Args:
        document: The Profile document.
        parts: The split path.
        operator: ``+=`` or ``-=``.
        value: The allergy as she said it.

    Raises:
        PaprikaError: When aimed per-person, set outright, or unmatchable.
    """
    if len(parts) != 1:
        raise _refuse(
            "Allergies are kept for the whole household, not per person.",
            f"per-person allergy path {'.'.join(parts)!r}",
        )
    if operator == "=":
        raise _refuse(
            "Allergies are added one at a time, or cleared by saying there are none.",
            "whole-value write to allergies",
        )

    canonical = allergens.normalise(value)
    if canonical is None:
        raise _refuse(
            "An allergy needs a name.",
            "blank allergen",
        )

    current = _list_at(document, "allergies")
    if operator == "+=" and canonical not in current:
        current.append(canonical)
    if operator == "-=" and canonical in current:
        current.remove(canonical)
    document["allergies"] = current


def _entry_in(
    document: tomlkit.TOMLDocument, table_name: str, who: str
) -> MutableMapping[str, Any]:
    """Return one person's table, making it and its parent when absent.

    Args:
        document: The Profile document.
        table_name: ``people`` or ``guests``.
        who: Their name, as she says it.

    Returns:
        MutableMapping[str, Any]: The table to write into.
    """
    table = document.get(table_name)
    if not isinstance(table, dict):
        table = tomlkit.table(is_super_table=True)
        document[table_name] = table
    entry = table.get(who)
    if not isinstance(entry, dict):
        entry = tomlkit.table()
        table[who] = entry
    return entry


def _apply_usually(
    document: tomlkit.TOMLDocument, parts: list[str], operator: str, value: str
) -> None:
    """Record when a guest normally comes.

    Held so a week can ask *"Monica on Sunday as usual?"* rather than an open
    question. **Never so it can be assumed** — she says who is coming.

    Args:
        document: The Profile document.
        parts: ``guests.<name>.usually``.
        operator: Must be ``=``.
        value: In her words: ``Sundays``.

    Raises:
        PaprikaError: When added to rather than set.
    """
    if operator != "=":
        raise _refuse(
            "When somebody usually comes is one answer, so it's set rather than "
            "added to.",
            "list operator on guests.usually",
        )
    _entry_in(document, "guests", parts[1])["usually"] = value


def _apply_person(
    document: tomlkit.TOMLDocument, parts: list[str], operator: str, value: str
) -> None:
    """Add or remove one of a person's dislikes, loves or allergies.

    Serves ``people`` and ``guests`` alike: a guest is the same shape as a
    family member and differs only in when their constraints apply. Family live
    here so theirs always do; a guest's bind the meals they are at. Keeping one
    writer is what stops the two drifting into different rules.

    Args:
        document: The Profile document.
        parts: The split path, ``people.<name>.<list>`` or ``guests.<name>.…``.
            For a guest, ``guests.<name>.usually=Sundays`` is also accepted.
        operator: ``+=``, ``-=``, or ``=`` for ``usually`` alone.
        value: Free text, in her words.

    Raises:
        PaprikaError: On a path that names no list, or a whole-value write.
    """
    table_name = parts[0]

    # When a guest normally comes is a single fact, not a list, and it is the
    # one thing here that is set outright.
    if table_name == "guests" and len(parts) == 3 and parts[2] == "usually":
        _apply_usually(document, parts, operator, value)
        return

    if len(parts) != 3 or parts[2] not in PERSON_LISTS:
        raise _refuse(
            "That isn't something kept about a person.",
            f"bad person path {'.'.join(parts)!r}",
        )
    if operator == "=":
        raise _refuse(
            "That's a list, so it's added to or taken from rather than replaced.",
            "whole-value write to a person list",
        )

    if parts[2] == "allergies":
        # Her word, tidied onto one name where we know it — the same treatment
        # a household allergy gets, so `dairy` and `milk` do not read as two.
        canonical = allergens.normalise(value)
        if canonical is None:
            raise _refuse("An allergy needs a name.", "blank allergen")
        value = canonical

    person = _entry_in(document, table_name, parts[1])

    current = _list_at(person, parts[2])
    if operator == "+=" and value not in current:
        current.append(value)
    if operator == "-=" and value in current:
        current.remove(value)
    person[parts[2]] = current


def _apply_rhythm(
    document: tomlkit.TOMLDocument, parts: list[str], operator: str, value: str
) -> None:
    """Set how the week actually goes.

    Args:
        document: The Profile document.
        parts: The split path, ``rhythm.<field>``.
        operator: ``=`` for the size, ``+=``/``-=`` for the lists.
        value: The value as typed.

    Raises:
        PaprikaError: On an unknown field or a size that is not a number.
    """
    if len(parts) != 2:
        raise _refuse(
            "That isn't something kept about your week.",
            f"bad rhythm path {'.'.join(parts)!r}",
        )
    rhythm = document.get("rhythm")
    if not isinstance(rhythm, dict):
        rhythm = tomlkit.table()
        document["rhythm"] = rhythm

    if parts[1] in ("household_size", "pantry_stale_days"):
        try:
            rhythm[parts[1]] = int(value)
        except ValueError:
            raise _refuse("That one is a number.", f"{parts[1]}={value!r}") from None
        return

    if parts[1] not in ("fast_nights", "away"):
        raise _refuse(
            "That isn't something kept about your week.",
            f"unknown rhythm field {parts[1]!r}",
        )
    current = _list_at(rhythm, parts[1])
    if operator == "+=" and value not in current:
        current.append(value)
    if operator == "-=" and value in current:
        current.remove(value)
    rhythm[parts[1]] = current


def _apply_target(
    document: tomlkit.TOMLDocument, parts: list[str], operator: str, value: str
) -> None:
    """Set a directional target.

    The shape is the safeguard: a key must carry its direction in its name and a
    value must be a direction, so there is no way to store a number that
    something downstream could subtract a running total from.

    Args:
        document: The Profile document.
        parts: The split path, ``targets.<field>_leaning``.
        operator: Must be ``=``.
        value: ``higher``, ``lower`` or ``steady``.

    Raises:
        PaprikaError: On a key that is not a leaning, or a value that is not a
            direction.
    """
    if len(parts) != 2 or not parts[1].endswith(LEANING):
        raise _refuse(
            "Targets are directions rather than numbers, so this one needs to say "
            "which way it leans.",
            f"target key {'.'.join(parts[1:])!r} does not end in {LEANING!r}",
        )
    if operator != "=" or value.casefold() not in DIRECTIONS:
        raise _refuse(
            "A target leans higher, lower or steady — never to a number.",
            f"target value {value!r}",
        )
    targets = document.get("targets")
    if not isinstance(targets, dict):
        targets = tomlkit.table()
        document["targets"] = targets
    targets[parts[1]] = value.casefold()
