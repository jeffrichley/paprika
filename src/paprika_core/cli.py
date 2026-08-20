"""The ``paprika`` command — and the line Paprika's mechanics stop at.

Everything that must be identical every time lives on this side. Everything that
needs judgement lives in a skill on the other side. What crosses is one envelope,
as JSON on stdout, and an exit code that always agrees with it.

``--human`` re-renders that same envelope with Rich for whoever is maintaining
this. It is one renderer over one contract, not a second output path.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Annotated, Any

import typer

from paprika_core import (
    bulk,
    freshness,
    pace,
    profile,
    setup,
    store,
    sync,
    undo,
    write,
)
from paprika_core.envelope import Envelope, ErrorDetail, failed, succeeded
from paprika_core.errors import Code, PaprikaError
from paprika_core.http import RECIPE_INDEX_PATH, PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.patch import Patch
from paprika_core.recipes import index_lines
from paprika_core.session import sign_in

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage a Paprika recipe library from Claude Code.",
)
recipe_app = typer.Typer(no_args_is_help=True, help="Read the Library.")
app.add_typer(recipe_app, name="recipe")

# Every mutating command lives under this one prefix, so a write reads as a
# write in the transcript, greps as one in the log, and — the reason it wins —
# is deniable with a single rule (`Bash(paprika write:*)`) rather than a list
# somebody has to maintain.
write_app = typer.Typer(no_args_is_help=True, help="Change things in Paprika.")
app.add_typer(write_app, name="write")
write_recipe_app = typer.Typer(no_args_is_help=True, help="Change a recipe.")
write_app.add_typer(write_recipe_app, name="recipe")

# Reading what could be put back changes nothing, so it stays outside the
# prefix. Actually putting it back is a write like any other, and sits inside.
undo_app = typer.Typer(no_args_is_help=True, help="What could be put back.")
app.add_typer(undo_app, name="undo")

profile_app = typer.Typer(no_args_is_help=True, help="Read your household.")
app.add_typer(profile_app, name="profile")
write_profile_app = typer.Typer(no_args_is_help=True, help="Change your household.")
write_app.add_typer(write_profile_app, name="profile")

_HUMAN = False


def _emit(envelope: Envelope) -> None:
    """Print the envelope and exit with a code that agrees with it.

    Args:
        envelope: What the command produced.

    Raises:
        typer.Exit: Always. The exit code is ``envelope.exit_code``.
    """
    log_event(
        "command",
        attempted=envelope.attempted,
        ok=envelope.ok,
        changed=envelope.changed,
        complete=envelope.complete,
        code=envelope.error.code if envelope.error else None,
    )
    if _HUMAN:
        _render_human(envelope)
    else:
        typer.echo(envelope.to_json())
    raise typer.Exit(code=envelope.exit_code)


def _render_human(envelope: Envelope) -> None:
    """Re-render the same envelope for a person reading a terminal.

    Args:
        envelope: What the command produced.
    """
    from rich.console import Console

    console = Console()
    if envelope.ok:
        console.print(f"[green]OK[/green] {envelope.attempted}")
    else:
        message = envelope.error.message if envelope.error else "It didn't work."
        console.print(f"[red]Stopped[/red] {envelope.attempted}\n{message}")
    if envelope.changed:
        moved = ", ".join(f"{n} {kind}" for kind, n in envelope.changed.items())
        console.print(f"Changed in Paprika: {moved}")
    for key, value in (envelope.data or {}).items():
        if isinstance(value, list):
            for line in value:
                console.print(line)
        else:
            console.print(f"{key}: {value}")


def _run(attempted: str, work: Callable[[], Envelope]) -> None:
    """Run a command, turning any failure into the one envelope shape.

    A traceback never reaches stdout: an unexpected exception is logged and
    reported as a sentence, because nothing in this tool may require her to be
    technical.

    Args:
        attempted: What is being tried, phrased so it can be said to her.
        work: The command body.
    """
    try:
        envelope = work()
    except PaprikaError as error:
        envelope = failed(attempted, error)
    except Exception as error:  # a traceback must never escape to stdout
        log_event("unexpected", attempted=attempted, error=repr(error))
        envelope = failed(
            attempted,
            PaprikaError(
                Code.UNEXPECTED,
                "Something went wrong on our side, and nothing was changed.",
                detail=repr(error),
            ),
        )
    _emit(envelope)


@app.callback()
def main_callback(
    human: Annotated[
        bool,
        typer.Option("--human", help="Render the envelope for a person, not a model."),
    ] = False,
) -> None:
    """Set options that apply to every command.

    Args:
        human: Whether to render with Rich instead of emitting JSON.
    """
    global _HUMAN
    _HUMAN = human


@app.command()
def login() -> None:
    """Sign in to Paprika and remember the session."""
    attempted = "signing in to Paprika"

    def work() -> Envelope:
        email, password = store.credentials()
        store.ensure_home()
        setup.record(setup.Step.CREDENTIALS)
        store.clear_token()
        client = PaprikaClient()
        try:
            store.save_token(client.login(email, password))
        finally:
            client.close()
        setup.record(setup.Step.SIGNED_IN)
        return succeeded(attempted)

    _run(attempted, work)


@app.command(name="sync")
def sync_library() -> None:
    """Download the whole Library into the Mirror."""
    attempted = "downloading your recipes from Paprika"

    def work() -> Envelope:
        store.ensure_home()
        client = sign_in()
        try:
            with Mirror(store.mirror_path()) as mirror:
                count = sync.cold_sync(client, mirror)
        finally:
            client.close()
        # Progress is recorded by the command that did the work. There is no
        # command for declaring a step finished, because one would let a caller
        # lie about it.
        setup.record(setup.Step.CREDENTIALS)
        setup.record(setup.Step.SIGNED_IN)
        setup.record(setup.Step.LIBRARY)
        # Nothing of hers moved: a sync moves the Mirror, not her library.
        return succeeded(attempted, data={"recipes_downloaded": count})

    _run(attempted, work)


setup_app = typer.Typer(no_args_is_help=True, help="Get this working on this machine.")
app.add_typer(setup_app, name="setup")


@setup_app.command("credentials")
def setup_credentials(
    email: Annotated[str, typer.Option("--email", help="Her Paprika account email.")],
    password_stdin: Annotated[
        bool,
        typer.Option(
            "--password-stdin",
            help="Read the password from standard input rather than an argument.",
        ),
    ] = False,
) -> None:
    """Save the Paprika sign-in this machine should use.

    The password is never accepted as an argument. An argument is visible to
    every other process on the machine through the process list, and lands in
    shell history besides — so the only way in is standard input, and asking for
    it any other way is refused rather than quietly allowed.

    Args:
        email: Her Paprika account email.
        password_stdin: Required. Read the password from standard input.
    """
    attempted = "saving your Paprika sign-in"

    def work() -> Envelope:
        if not password_stdin:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "The password has to be handed over privately, not typed as an "
                "option.",
                detail="--password-stdin is required",
            )
        password = sys.stdin.read().strip()
        if not email.strip() or not password:
            raise PaprikaError(
                Code.NOT_SET_UP,
                "We still need both the email and the password.",
                detail="empty email or password",
            )
        setup.save_credentials(email.strip(), password)
        return succeeded(attempted)

    _run(attempted, work)


FRESH_OPTION = typer.Option("--fresh", help="Ask Paprika even if we just asked.")


def _refresh(mirror: Mirror, fresh: bool) -> freshness.Freshness:
    """Establish that the Mirror is current before anything reads it.

    Args:
        mirror: The Mirror about to be served.
        fresh: Whether to ask even if a recent answer is in hand.

    Returns:
        freshness.Freshness: What it cost and what it found.
    """
    client = sign_in()
    try:
        return freshness.ensure_current(client, mirror, force=fresh)
    finally:
        client.close()


def _library_size() -> int | None:
    """Ask how many recipes the Library holds, without downloading any of them.

    One request. The stub index runs about a hundred bytes per recipe, which is
    cheap enough to spend on making a wait estimate true.

    Returns:
        int | None: The count, or ``None`` if Paprika could not be asked.
    """
    client = sign_in()
    try:
        stubs = client.get(RECIPE_INDEX_PATH, "counting your recipes")
    except PaprikaError:
        # A failed estimate is not a failed command. Saying nothing is honest.
        return None
    finally:
        client.close()
    return len(stubs) if isinstance(stubs, list) else None


@contextmanager
def _current_mirror(fresh: bool) -> Iterator[tuple[Mirror, freshness.Freshness]]:
    """Open the Mirror, having first proved it current.

    Args:
        fresh: Whether to ask even if a recent answer is in hand.

    Yields:
        tuple[Mirror, freshness.Freshness]: The Mirror and what the check found.

    Raises:
        PaprikaError: ``nothing_mirrored`` when the Library was never downloaded.
    """
    path = store.mirror_path()
    not_yet = PaprikaError(
        Code.NOTHING_MIRRORED,
        "Your recipes haven't been downloaded to this machine yet.",
        detail=f"no mirror at {path}",
    )
    if not path.exists():
        raise not_yet
    with Mirror(path) as mirror:
        # Never synced and synced-but-empty are different answers. An account
        # with no recipes is a true, successful, empty read — saying "not
        # downloaded yet" there would be a sentence that isn't true.
        if mirror.age_seconds() is None:
            raise not_yet
        yield mirror, _refresh(mirror, fresh)


@recipe_app.command("index")
def recipe_index(fresh: Annotated[bool, FRESH_OPTION] = False) -> None:
    """List the whole Library, one line per recipe.

    Args:
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "reading your recipes"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, checked):
            data: dict[str, Any] = {
                "recipes": index_lines(mirror),
                "count": mirror.count_recipes(),
                "mirror_age_seconds": round(checked.age_seconds or 0),
            }
        return succeeded(attempted, data=data)

    _run(attempted, work)


@app.command()
def status(fresh: Annotated[bool, FRESH_OPTION] = False) -> None:
    """Report what this machine holds and how long a download would take.

    Args:
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "checking what this machine has"

    def work() -> Envelope:
        store.ensure_home()
        progress = setup.read()
        ready = progress.state is setup.State.READY

        age: float | None = None
        count = 0
        # A store that will not read is its own answer, and asking it anything
        # further would only produce a confident wrong one.
        if progress.state is not setup.State.UNREADABLE:
            with Mirror(store.mirror_path()) as mirror:
                age = mirror.age_seconds()
                if ready and age is not None:
                    age = _refresh(mirror, fresh).age_seconds
                count = mirror.count_recipes()

        # Before the first download the Mirror cannot say how big the Library
        # is — and that is precisely when the estimate matters. One cheap
        # request buys an honest number; without it we would report "no wait at
        # all" for what is really a hundred-second walk.
        can_ask = setup.Step.CREDENTIALS in progress.done
        expected = count if age is not None else (_library_size() if can_ask else None)

        return succeeded(
            attempted,
            data={
                "setup": progress.state.value,
                "still_to_do": [step.value for step in progress.missing],
                "recipes": count,
                "mirror_age_seconds": round(age) if age is not None else None,
                # Measured from this machine's own request durations. A skill
                # turns 103 into "about two minutes". Null means we cannot say.
                "estimated_seconds": (
                    round(pace.cold_sync_seconds(expected))
                    if expected is not None
                    else None
                ),
            },
        )

    _run(attempted, work)


RUN_OPTION = typer.Option("--run", help="Join these changes to an earlier Run.")


def _resolve(handles: list[str]) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Turn handles into identities, and read her category names.

    Args:
        handles: The handles a caller named.

    Returns:
        tuple: The ``(uid, name)`` pairs, and a name-to-identifier map for
            categories so a caller never has to learn what one looks like.

    Raises:
        PaprikaError: When a handle names nothing in the Library.
    """
    with Mirror(store.mirror_path()) as mirror:
        known = {r.handle: r for r in mirror.recipes()}
        categories = {
            name.casefold(): uid for uid, name in mirror.category_names().items()
        }
        found: list[tuple[str, str]] = []
        for handle in handles:
            recipe = known.get(handle)
            if recipe is None:
                raise PaprikaError(
                    Code.NOTHING_MIRRORED,
                    "That isn't a recipe we know about.",
                    detail=f"no mirrored recipe for handle {handle!r}",
                )
            found.append((mirror.uid_for(handle) or "", recipe.name))
    return found, categories


def _perform(
    attempted: str,
    targets: list[tuple[str, str, Any]],
    run_id: str | None,
) -> Envelope:
    """Run a set of writes as one Run and turn the outcome into an envelope.

    Args:
        attempted: What is being tried.
        targets: What to change.
        run_id: An open Run to join, or ``None`` to start one.

    Returns:
        Envelope: The result, carrying the Run so a stopped one is addressable.
    """
    client = sign_in()
    try:
        with undo.open_run(run_id) as run:
            outcome = bulk.apply_all(client, targets, run=run)
            joined = run.id
    finally:
        client.close()

    data: dict[str, Any] = {"run": joined, "saved": outcome.landed}
    if outcome.missing:
        data["not_saved"] = outcome.missing
    if outcome.error is not None:
        return Envelope(
            ok=False,
            attempted=attempted,
            changed=outcome.changed,
            complete=False,
            error=ErrorDetail(code=outcome.error.code, message=outcome.error.message),
            data=data,
        )
    return Envelope(
        ok=True,
        attempted=attempted,
        changed=outcome.changed,
        complete=outcome.complete,
        data=data,
    )


@write_recipe_app.command("set")
def write_recipe_set(
    handle: str,
    set_: Annotated[list[str] | None, typer.Option("--set", help="field=value")] = None,
    add: Annotated[list[str] | None, typer.Option("--add", help="field=value")] = None,
    remove: Annotated[
        list[str] | None, typer.Option("--remove", help="field=value")
    ] = None,
    run: Annotated[str | None, RUN_OPTION] = None,
) -> None:
    """Change named fields on one recipe.

    Args:
        handle: Which recipe.
        set_: Fields to replace.
        add: List entries to add.
        remove: List entries to take out.
        run: An earlier Run to join.
    """
    attempted = "changing a recipe"

    def work() -> Envelope:
        patch = Patch.parse(sets=set_ or [], adds=add or [], removes=remove or [])
        found, categories = _resolve([handle])
        mutate = patch.as_mutation({"categories": categories})
        return _perform(attempted, [(uid, name, mutate) for uid, name in found], run)

    _run(attempted, work)


@write_recipe_app.command("trash")
def write_recipe_trash(
    handle: str,
    run: Annotated[str | None, RUN_OPTION] = None,
) -> None:
    """Put one recipe in Paprika's trash, where she can get it back herself.

    Args:
        handle: Which recipe.
        run: An earlier Run to join.
    """
    attempted = "moving a recipe to the trash"

    def work() -> Envelope:
        found, _ = _resolve([handle])

        def mutate(recipe: dict[str, Any]) -> None:
            recipe["in_trash"] = True

        return _perform(attempted, [(uid, name, mutate) for uid, name in found], run)

    _run(attempted, work)


@write_app.command("undo")
def write_undo(
    run: Annotated[str | None, typer.Argument(help="Which Run to reverse.")] = None,
) -> None:
    """Put back what the most recent change did.

    Args:
        run: Which Run to reverse. Omit for the most recent.
    """
    attempted = "putting things back the way they were"

    def work() -> Envelope:
        recent = undo.recent_runs()
        if not recent:
            raise PaprikaError(
                Code.NOTHING_TO_UNDO,
                "There's nothing recent to put back.",
                detail="no run holds a landed pre-image",
            )
        # Offered by name only for the most recent, per the retention rule.
        target = run or recent[0].run_id
        pre_images = undo.pre_images_of(target)
        if not pre_images:
            raise PaprikaError(
                Code.NOTHING_TO_UNDO,
                "There's nothing recent to put back.",
                detail=f"run {target} holds no pre-image",
            )

        client = sign_in()
        try:
            with undo.open_run() as reversal:
                for pre_image in pre_images:
                    write.restore(client, pre_image, run=reversal)
                changed = reversal.changed()
                names = reversal.landed_names()
        finally:
            client.close()
        return succeeded(attempted, changed=changed, data={"put_back": names})

    _run(attempted, work)


@undo_app.command("list")
def undo_list() -> None:
    """List what could be put back, by what it changed rather than by name."""
    attempted = "listing what could be put back"

    def work() -> Envelope:
        runs = [
            {
                "changed": summary.changed,
                "names": summary.names,
                "when": round(summary.ended_at) if summary.ended_at else None,
            }
            for summary in undo.recent_runs()
        ]
        return succeeded(attempted, data={"runs": runs})

    _run(attempted, work)


@profile_app.command("show")
def profile_show() -> None:
    """Report the standing facts a plan is drawn against."""
    attempted = "reading your household"

    def work() -> Envelope:
        read = profile.read()
        data: dict[str, Any] = {
            # Nothing here claims anything when the file could not be read.
            # Silence about a safety fact must not look like an all-clear.
            "readable": read.readable,
            "allergies_answered": read.allergies_answered,
            "allergies": list(read.allergies),
            "people": {
                name: {"dislikes": list(person.dislikes), "loves": list(person.loves)}
                for name, person in read.people.items()
            },
            "household_size": read.household_size,
            "fast_nights": list(read.fast_nights),
            "away": list(read.away),
            "targets": dict(read.targets),
        }
        return succeeded(attempted, data=data)

    _run(attempted, work)


@write_profile_app.command("set")
def write_profile_set(
    changes: Annotated[
        list[str] | None,
        typer.Argument(help="path=value, path+=value or path-=value."),
    ] = None,
    none: Annotated[
        bool,
        typer.Option(
            "--no-allergies",
            help="Record that the household has none, which is an answer.",
        ),
    ] = False,
) -> None:
    """Change one standing fact about the household.

    A path expression rather than a file, for the same reason a recipe write
    takes a patch rather than an object: if this accepted a whole household
    file, the comments she wrote in it would be one careless caller away from
    gone.

    Args:
        changes: The named changes to apply.
        none: Record that there are no allergies at all.
    """
    attempted = "noting something about your household"

    def work() -> Envelope:
        named = changes or []
        if not named and not none:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "Nothing was asked for, so nothing was noted.",
                detail="empty profile write",
            )
        if none:
            profile.record_no_allergies()
        for change in named:
            profile.apply(change)
        # Her household is hers, and it is not her Paprika library — so nothing
        # of Paprika's moved, and `changed` says so.
        return succeeded(attempted, data={"noted": named})

    _run(attempted, work)


def main() -> None:
    """Run the CLI, exiting with a code that agrees with the envelope."""
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
