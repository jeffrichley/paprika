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

from paprika_core import freshness, pace, store, sync
from paprika_core.envelope import Envelope, failed, succeeded
from paprika_core.errors import Code, PaprikaError
from paprika_core.http import RECIPE_INDEX_PATH, PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.recipes import index_lines
from paprika_core.session import sign_in

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage a Paprika recipe library from Claude Code.",
)
recipe_app = typer.Typer(no_args_is_help=True, help="Read the Library.")
app.add_typer(recipe_app, name="recipe")

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
        store.clear_token()
        client = PaprikaClient()
        try:
            store.save_token(client.login(email, password))
        finally:
            client.close()
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
        # Nothing of hers moved: a sync moves the Mirror, not her library.
        return succeeded(attempted, data={"recipes_downloaded": count})

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
        set_up = True
        try:
            store.credentials()
        except PaprikaError as unset:
            if unset.code != Code.NOT_SET_UP:
                raise
            set_up = False

        with Mirror(store.mirror_path()) as mirror:
            age = mirror.age_seconds()
            if set_up and age is not None:
                age = _refresh(mirror, fresh).age_seconds
            count = mirror.count_recipes()

        # Before the first download the Mirror cannot say how big the Library
        # is — and that is precisely when the estimate matters. One cheap
        # request buys an honest number; without it we would report "no wait at
        # all" for what is really a hundred-second walk.
        expected = count if age is not None else (_library_size() if set_up else None)

        return succeeded(
            attempted,
            data={
                "set_up": set_up,
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


def main() -> None:
    """Run the CLI, exiting with a code that agrees with the envelope."""
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
