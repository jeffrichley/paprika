"""A patch — named keys and values, which is the only thing a write can be given.

ADR 0004's chokepoint is ``write(uid, mutate_fn)``, and a caller on the far side
of a process boundary cannot pass a closure. So the transport carries a **patch**:
``--set``, ``--add`` and ``--remove``. The core turns it into the mutation.

This is what makes ADR 0004's "unenforceable exception" physically impossible
rather than merely discouraged — the transport cannot carry a whole object, so
there is no path by which one contributor assembles a payload and the next
copies it. Anything a patch cannot express is a **missing command**, not grounds
for accepting an object.

``--add`` and ``--remove`` exist because re-filing is additive: a Run must be
able to add a category without disturbing the filing she did on purpose.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from paprika_core.errors import Code, PaprikaError

#: What the chokepoint takes: a function that edits the fetched object in place.
Mutation = Callable[[dict[str, Any]], None]

#: Name-to-identifier maps, by field.
Lookups = Mapping[str, Mapping[str, str]]

#: Fields a patch may never touch, whatever a caller asks for. These are
#: identity, mechanics, or removal — none of them are hers to set by name.
FORBIDDEN = frozenset({"uid", "hash", "photo_url", "deleted", "in_trash"})

#: Fields that hold a list, so `--add` and `--remove` mean something on them.
LIST_FIELDS = frozenset({"categories"})

#: Fields Paprika stores as a number, so `"4"` must not be written as a string.
INTEGER_FIELDS = frozenset({"rating"})

#: Fields Paprika stores as a boolean.
BOOLEAN_FIELDS = frozenset({"on_favorites", "is_pinned"})


def _split(assignment: str) -> tuple[str, str]:
    """Split a ``field=value`` argument.

    Args:
        assignment: The argument as typed.

    Returns:
        tuple[str, str]: The field and the value.

    Raises:
        PaprikaError: When there is no ``=`` in it.
    """
    field_name, separator, value = assignment.partition("=")
    if not separator or not field_name.strip():
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            "That change wasn't written in a way we could apply.",
            detail=f"expected field=value, got {assignment!r}",
        )
    return field_name.strip(), value


@dataclass
class Patch:
    """The named changes a caller asked for.

    Attributes:
        sets: Fields to replace outright.
        adds: List fields to add entries to.
        removes: List fields to take entries out of.
    """

    sets: dict[str, str] = field(default_factory=dict)
    adds: dict[str, list[str]] = field(default_factory=dict)
    removes: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def parse(
        cls,
        sets: Iterable[str] = (),
        adds: Iterable[str] = (),
        removes: Iterable[str] = (),
    ) -> Patch:
        """Build a patch from the raw ``field=value`` arguments.

        Args:
            sets: ``--set`` arguments.
            adds: ``--add`` arguments.
            removes: ``--remove`` arguments.

        Returns:
            Patch: The parsed patch.

        Raises:
            PaprikaError: On a malformed argument, a forbidden field, or an
                ``--add``/``--remove`` aimed at something that is not a list.
        """
        patch = cls()
        for raw in sets:
            name, value = _split(raw)
            patch.sets[name] = value
        for raw in adds:
            name, value = _split(raw)
            patch.adds.setdefault(name, []).append(value)
        for raw in removes:
            name, value = _split(raw)
            patch.removes.setdefault(name, []).append(value)

        touched = set(patch.sets) | set(patch.adds) | set(patch.removes)
        forbidden = touched & FORBIDDEN
        if forbidden:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "That isn't something this can change.",
                detail=f"patch touched reserved fields: {sorted(forbidden)}",
            )
        not_lists = (set(patch.adds) | set(patch.removes)) - LIST_FIELDS
        if not_lists:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "That isn't something you can add to or take from.",
                detail=f"not list fields: {sorted(not_lists)}",
            )
        if not touched:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "Nothing was asked for, so nothing was changed.",
                detail="empty patch",
            )
        return patch

    def touches(self) -> set[str]:
        """Return every field this patch would change.

        Returns:
            set[str]: The field names.
        """
        return set(self.sets) | set(self.adds) | set(self.removes)

    def as_mutation(
        self, lookups: Mapping[str, Mapping[str, str]] | None = None
    ) -> Mutation:
        """Turn the patch into the mutation the chokepoint takes.

        Args:
            lookups: Per-field name-to-identifier maps, so a caller can say
                ``--add categories=Dinner`` and never learn what a category
                identifier looks like.

        Returns:
            Mutation: A function that edits a fetched object in place.
        """
        tables = lookups or {}

        def mutate(recipe: dict[str, Any]) -> None:
            self._replace(recipe)
            self._extend(recipe, tables)
            self._reduce(recipe, tables)

        return mutate

    def _replace(self, recipe: dict[str, Any]) -> None:
        """Apply the ``--set`` changes.

        Args:
            recipe: The fetched object, edited in place.

        Raises:
            PaprikaError: When a field does not exist on a recipe.
        """
        for name, value in self.sets.items():
            if name not in recipe:
                raise PaprikaError(
                    Code.REFUSED_LOCALLY,
                    f"A recipe has nothing called {name!r}.",
                    detail=f"unknown field {name!r}",
                )
            recipe[name] = _coerce(name, value)

    def _extend(self, recipe: dict[str, Any], tables: Lookups) -> None:
        """Apply the ``--add`` changes, without duplicating what is there.

        Args:
            recipe: The fetched object, edited in place.
            tables: Name-to-identifier maps.
        """
        for name, values in self.adds.items():
            current = list(recipe.get(name) or [])
            for value in values:
                resolved = _resolve(tables, name, value)
                if resolved not in current:
                    current.append(resolved)
            recipe[name] = current

    def _reduce(self, recipe: dict[str, Any], tables: Lookups) -> None:
        """Apply the ``--remove`` changes.

        Args:
            recipe: The fetched object, edited in place.
            tables: Name-to-identifier maps.
        """
        for name, values in self.removes.items():
            current = list(recipe.get(name) or [])
            for value in values:
                resolved = _resolve(tables, name, value)
                if resolved in current:
                    current.remove(resolved)
            recipe[name] = current


def _resolve(tables: Lookups, name: str, value: str) -> str:
    """Turn a name she used into the identifier Paprika stores.

    Args:
        tables: Name-to-identifier maps, by field.
        name: Which field.
        value: The name as typed.

    Returns:
        str: The identifier, or the value unchanged when the field needs no
            lookup.

    Raises:
        PaprikaError: When there is nothing by that name.
    """
    table = tables.get(name)
    if table is None:
        return value
    found = table.get(value.casefold())
    if found is None:
        raise PaprikaError(
            Code.REFUSED_LOCALLY,
            f"There's nothing called {value!r} to use.",
            detail=f"no {name} entry named {value!r}",
        )
    return found


def _coerce(name: str, value: str) -> Any:
    """Turn a typed string into the type Paprika stores for that field.

    Everything else stays a string, because almost every field on a recipe is
    free text — ``servings`` is ``"12 muffins"`` and ``total_time`` is ``"35"``.

    Args:
        name: The field.
        value: The value as typed.

    Returns:
        Any: The value in the right type.

    Raises:
        PaprikaError: When a numeric field was given something that is not one.
    """
    if name in INTEGER_FIELDS:
        try:
            return int(value)
        except ValueError:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                f"{name} has to be a number.",
                detail=f"{name}={value!r}",
            ) from None
    if name in BOOLEAN_FIELDS:
        return value.strip().casefold() in {"true", "yes", "1", "on"}
    return value
