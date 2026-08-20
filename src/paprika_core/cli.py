"""The ``paprika`` command — and the line Paprika's mechanics stop at.

Everything that must be identical every time lives on this side. Everything that
needs judgement lives in a skill on the other side. What crosses is one envelope,
as JSON on stdout, and an exit code that always agrees with it.

``--human`` re-renders that same envelope with Rich for whoever is maintaining
this. It is one renderer over one contract, not a second output path.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Annotated, Any

import typer

from paprika_core import store, sync
from paprika_core.envelope import Envelope, failed, succeeded
from paprika_core.errors import Code, PaprikaError
from paprika_core.http import PaprikaClient
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


@recipe_app.command("index")
def recipe_index() -> None:
    """List the whole Library, one line per recipe."""
    attempted = "reading your recipes"

    def work() -> Envelope:
        path = store.mirror_path()
        not_yet = PaprikaError(
            Code.NOTHING_MIRRORED,
            "Your recipes haven't been downloaded to this machine yet.",
            detail=f"no mirror at {path}",
        )
        if not path.exists():
            raise not_yet
        with Mirror(path) as mirror:
            lines = index_lines(mirror)
            age = mirror.age_seconds()
        # Never synced and synced-but-empty are different answers. An account
        # with no recipes is a true, successful, empty index — saying "not
        # downloaded yet" there would be a sentence that isn't true.
        if age is None:
            raise not_yet
        data: dict[str, Any] = {
            "recipes": lines,
            "count": len(lines),
            "mirror_age_seconds": round(age),
        }
        return succeeded(attempted, data=data)

    _run(attempted, work)


def main() -> None:
    """Run the CLI, exiting with a code that agrees with the envelope."""
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
