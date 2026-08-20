"""The ``paprika`` command — and the line Paprika's mechanics stop at.

Everything that must be identical every time lives on this side. Everything that
needs judgement lives in a skill on the other side. What crosses is one envelope,
as JSON on stdout, and an exit code that always agrees with it.

``--human`` re-renders that same envelope with Rich for whoever is maintaining
this. It is one renderer over one contract, not a second output path.
"""

from __future__ import annotations

import datetime as dt
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer

from paprika_core import (
    bulk,
    freshness,
    groceries,
    health,
    intake,
    pace,
    pantry,
    plan,
    profile,
    setup,
    store,
    sync,
    undo,
    write,
)
from paprika_core import (
    categories as categories_module,
)
from paprika_core import (
    primer as primer_module,
)
from paprika_core.envelope import Envelope, ErrorDetail, failed, succeeded
from paprika_core.errors import Code, PaprikaError
from paprika_core.http import RECIPE_INDEX_PATH, PaprikaClient
from paprika_core.log import log_event
from paprika_core.mirror import Mirror
from paprika_core.patch import Patch
from paprika_core.recipes import differences, index_lines, rendered, search
from paprika_core.session import sign_in

#: Where this file sits when it is a checkout rather than an install, which is
#: the only case where the plugin can be found by looking upwards from the code.
#: The hook always passes the real one.
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent

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
write_category_app = typer.Typer(no_args_is_help=True, help="Extend her filing scheme.")
write_app.add_typer(write_category_app, name="category")

# Reading what could be put back changes nothing, so it stays outside the
# prefix. Actually putting it back is a write like any other, and sits inside.
undo_app = typer.Typer(no_args_is_help=True, help="What could be put back.")
app.add_typer(undo_app, name="undo")

write_groceries_app = typer.Typer(
    no_args_is_help=True, help="Change her shopping list."
)
write_app.add_typer(write_groceries_app, name="groceries")

pantry_app = typer.Typer(no_args_is_help=True, help="Read what is in the house.")
app.add_typer(pantry_app, name="pantry")
write_pantry_app = typer.Typer(
    no_args_is_help=True, help="Change what is in the house."
)
write_app.add_typer(write_pantry_app, name="pantry")

plan_app = typer.Typer(no_args_is_help=True, help="Read the week's plan.")
app.add_typer(plan_app, name="plan")
write_plan_app = typer.Typer(no_args_is_help=True, help="Change the week's plan.")
write_app.add_typer(write_plan_app, name="plan")

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


def _mirror_is_now_stale() -> None:
    """Forget that freshness was recently established.

    Called after **any** write. The Mirror is out of date by our own hand, and
    the stamp that collapses a burst of reads into one question must not let the
    next read serve what we just replaced. Every path that changes something in
    Paprika has to come through here, which is why it is one function rather
    than a line each of them remembers.
    """
    with Mirror(store.mirror_path()) as mirror:
        mirror.mark_stale()


def _after_write(client: PaprikaClient, done: bool) -> None:
    """Settle up after changing something in Paprika.

    Args:
        client: A signed-in client.
        done: Whether this finished the job, in which case her other devices are
            told to pull. Never per write: seven nights must not buzz her phone
            seven times.
    """
    _mirror_is_now_stale()
    if done:
        plan.notify(client)


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


@recipe_app.command("get")
def recipe_get(
    handles: Annotated[list[str], typer.Argument(help="Which recipes.")],
    fresh: Annotated[bool, FRESH_OPTION] = False,
) -> None:
    """Read whole recipes, to judge them on more than their titles.

    Args:
        handles: Which recipes. Several at once, because a shortlist is pulled
            in one go rather than a round trip at a time.
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "reading a recipe"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            found = [(handle, rendered(mirror, handle)) for handle in handles]
        missing = [handle for handle, recipe in found if recipe is None]
        if missing:
            raise PaprikaError(
                Code.NOTHING_MIRRORED,
                "That isn't a recipe we know about.",
                detail=f"unknown handles: {missing}",
            )
        recipes = [recipe for _handle, recipe in found if recipe is not None]
        data: dict[str, Any] = {"recipes": recipes}
        # One asked for is one handed back, rather than a list of one to unwrap.
        if len(recipes) == 1:
            data["recipe"] = recipes[0]
        return succeeded(attempted, data=data)

    _run(attempted, work)


@recipe_app.command("compare")
def recipe_compare(
    handles: Annotated[list[str], typer.Argument(help="The recipes to compare.")],
    fresh: Annotated[bool, FRESH_OPTION] = False,
) -> None:
    """Show what differs between recipes that look like copies of each other.

    For choosing which copy to keep. Here a name is not enough to judge by — she
    is deciding which one survives, and she can only do that if she can see what
    each has that the others do not.

    Args:
        handles: The recipes to compare.
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "comparing recipes"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            found = differences(mirror, handles)
        if found["missing"]:
            raise PaprikaError(
                Code.NOTHING_MIRRORED,
                "That isn't a recipe we know about.",
                detail=f"unknown handles: {found['missing']}",
            )
        return succeeded(attempted, data=found)

    _run(attempted, work)


@recipe_app.command("search")
def recipe_search(
    term: Annotated[str, typer.Argument(help="A word to look for.")],
    fresh: Annotated[bool, FRESH_OPTION] = False,
) -> None:
    """Find recipes whose text contains a word.

    For the one question the whole-library index cannot answer — an ingredient
    across every recipe without fetching any of them. It matches text and
    nothing else: there is no score here, and a near miss is not a hit.

    Args:
        term: A word to look for.
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "looking through your recipes"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            found = search(mirror, term)
        return succeeded(attempted, data={"recipes": found, "count": len(found)})

    _run(attempted, work)


@plan_app.command("show")
def plan_show(
    since: Annotated[str, typer.Option("--from", help="First day, YYYY-MM-DD.")] = "",
    until: Annotated[str, typer.Option("--to", help="Last day, YYYY-MM-DD.")] = "",
    fresh: Annotated[bool, FRESH_OPTION] = False,
) -> None:
    """Report what is planned between two dates.

    Args:
        since: First day.
        until: Last day.
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "reading your plan"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            meals = [
                {
                    "date": meal.date,
                    "slot": _SLOT_NAMES.get(meal.meal_type, "dinner"),
                    "name": meal.name,
                    # Present only when it is one of her recipes; a free-text
                    # meal is an ordinary case rather than a missing one.
                    "recipe": meal.recipe_handle,
                }
                for meal in mirror.meals(since, until)
            ]
        return succeeded(attempted, data={"meals": meals, "count": len(meals)})

    _run(attempted, work)


@write_plan_app.command("set")
def write_plan_set(
    date: Annotated[str, typer.Option("--date", help="YYYY-MM-DD.")],
    slot: Annotated[str, typer.Option("--slot", help="breakfast/lunch/dinner/snack.")],
    recipe: Annotated[
        str | None, typer.Option("--recipe", help="One of her recipes.")
    ] = None,
    name: Annotated[
        str | None, typer.Option("--name", help="Free text, when it is not a recipe.")
    ] = None,
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Put one meal on one day.

    Args:
        date: Which day.
        slot: Which meal of the day.
        recipe: One of her recipes.
        name: Free text, for a meal that is not a recipe.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "saving your plan"

    def work() -> Envelope:
        if bool(recipe) == bool(name):
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "A meal is either one of your recipes or something written out, "
                "not both and not neither.",
                detail="exactly one of --recipe/--name is required",
            )
        recipe_uid: str | None = None
        shown = name or ""
        if recipe:
            found, _categories = _resolve([recipe])
            recipe_uid, shown = found[0]

        client = sign_in()
        try:
            with undo.open_run(run) as opened:
                plan.set_slot(
                    client,
                    date=date,
                    slot=slot,
                    name=shown,
                    recipe_uid=recipe_uid,
                    run=opened,
                )
                changed, joined = opened.changed(), opened.id
            _after_write(client, done)
        finally:
            client.close()
        return Envelope(
            ok=True,
            attempted=attempted,
            changed=changed,
            data={"run": joined, "planned": {date: shown}},
        )

    _run(attempted, work)


@write_plan_app.command("clear")
def write_plan_clear(
    date: Annotated[str, typer.Option("--date", help="YYYY-MM-DD.")],
    slot: Annotated[str, typer.Option("--slot", help="breakfast/lunch/dinner/snack.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Empty one meal on one day.

    Args:
        date: Which day.
        slot: Which meal of the day.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "clearing a day on your plan"

    def work() -> Envelope:
        client = sign_in()
        try:
            with undo.open_run(run) as opened:
                was = plan.clear_slot(client, date=date, slot=slot, run=opened)
                changed, joined = opened.changed(), opened.id
            _after_write(client, done)
        finally:
            client.close()
        return Envelope(
            ok=True,
            attempted=attempted,
            changed=changed,
            data={"run": joined, "cleared": was},
        )

    _run(attempted, work)


@pantry_app.command("list")
def pantry_list(fresh: Annotated[bool, FRESH_OPTION] = False) -> None:
    """Report what is in the house, and how old that belief is.

    The age rides along rather than being a command of its own, so nothing can
    read the Pantry without also learning how much to trust it.

    Args:
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "reading what you have in"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            items = [
                {"ingredient": item.ingredient, "aisle": item.aisle}
                for item in mirror.pantry()
            ]
        age = store.pantry_age_days()
        return succeeded(
            attempted,
            data={
                "have": items,
                "count": len(items),
                # Null rather than zero when she has never confirmed it: never
                # checked and checked today are not the same claim.
                "confirmed_days_ago": round(age, 1) if age is not None else None,
            },
        )

    _run(attempted, work)


@pantry_app.command("unseen")
def pantry_unseen(
    seen: Annotated[list[str], typer.Argument(help="What was actually seen.")],
    fresh: Annotated[bool, FRESH_OPTION] = False,
) -> None:
    """Report what is recorded but was not among these.

    A photograph shows one shelf, so what it does not show is a **question**
    rather than a finding. This works out which question to ask, once, rather
    than leaving it to whatever was remembered — a closing line that misses an
    item is how something quietly stays on a list forever.

    Args:
        seen: What was actually seen.
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "working out what wasn't in the picture"

    def work() -> Envelope:
        spotted = {name.strip().casefold() for name in seen if name.strip()}
        with _current_mirror(fresh) as (mirror, _checked):
            recorded = [item.ingredient for item in mirror.pantry()]
        missing = [
            ingredient
            for ingredient in recorded
            if ingredient.strip().casefold() not in spotted
        ]
        return succeeded(
            attempted,
            data={
                # Never removed on this evidence. Asked about, once, at the end.
                "not_seen": missing,
                "seen": sorted(spotted),
            },
        )

    _run(attempted, work)


def _pantry_write(
    attempted: str, ingredients: list[str], in_stock: bool, run: str | None, done: bool
) -> Envelope:
    """Record that she has, or no longer has, each of these.

    Args:
        attempted: What is being tried.
        ingredients: What she named.
        in_stock: Whether she has them.
        run: An earlier Run to join.
        done: Whether this finishes the job.

    Returns:
        Envelope: The result.
    """
    client = sign_in()
    try:
        with Mirror(store.mirror_path()) as mirror, undo.open_run(run) as opened:
            recorded = pantry.set_stock(
                client, ingredients, in_stock=in_stock, mirror=mirror, run=opened
            )
            changed, joined = opened.changed(), opened.id
        store.mark_pantry_checked()
        _after_write(client, done)
    finally:
        client.close()
    return Envelope(
        ok=True,
        attempted=attempted,
        changed=changed,
        data={"run": joined, "noted": recorded},
    )


@write_pantry_app.command("add")
def write_pantry_add(
    ingredients: Annotated[list[str], typer.Argument(help="What she bought.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Record what she bought, all of it at once.

    Args:
        ingredients: What she bought.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "noting what you bought"
    _run(attempted, lambda: _pantry_write(attempted, ingredients, True, run, done))


@write_pantry_app.command("confirm")
def write_pantry_confirm(
    ingredients: Annotated[list[str], typer.Argument(help="What is still there.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Record that she still has these.

    Args:
        ingredients: What is still there.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "noting what you still have"
    _run(attempted, lambda: _pantry_write(attempted, ingredients, True, run, done))


@write_pantry_app.command("gone")
def write_pantry_gone(
    ingredients: Annotated[list[str], typer.Argument(help="What has run out.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Record that she has run out of these.

    The only way something leaves the Pantry. Nothing infers it — not a photo
    that did not show it, not a planned day that has passed.

    Args:
        ingredients: What has run out.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "noting what you have run out of"
    _run(attempted, lambda: _pantry_write(attempted, ingredients, False, run, done))


@app.command("health")
def health_report(fresh: Annotated[bool, FRESH_OPTION] = False) -> None:
    """Report how tidy her library is.

    Arithmetic over what is already downloaded — instant, and incapable of being
    wrong in an interesting way. No agent is dispatched here; the Scan runs only
    once she has picked a job.

    Args:
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "looking over your library"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            findings = health.report(mirror)
            total = mirror.count_recipes()
        return succeeded(
            attempted,
            data={
                "recipes": total,
                # The two she could pick, biggest first, and then everything
                # worth saying — which is not the same list.
                "jobs": [
                    {"kind": job.kind, "recipes": job.recipes}
                    for job in health.jobs(findings)
                ],
                # Everything else worth saying — the jobs that did not make
                # the top two as well as the information. Without this the
                # third line has nothing to close on.
                "also": [
                    {
                        "kind": f.kind,
                        "recipes": f.recipes,
                        "actionable": f.actionable,
                    }
                    for f in findings
                    if f.kind not in {job.kind for job in health.jobs(findings)}
                ],
                "tidy": health.is_tidy(findings),
            },
        )

    _run(attempted, work)


intake_app = typer.Typer(
    no_args_is_help=True, help="Drafts read out of files, before they are recipes."
)
app.add_typer(intake_app, name="intake")


@intake_app.command("save")
def intake_save(
    source: Annotated[str, typer.Option("--source", help="The file it came from.")],
    set_: Annotated[list[str] | None, typer.Option("--set", help="field=value")] = None,
    gap: Annotated[
        list[str] | None, typer.Option("--gap", help="A line that could not be read.")
    ] = None,
    unusable: Annotated[
        str | None,
        typer.Option("--unusable", help="Why there is no draft, when there is none."),
    ] = None,
) -> None:
    """Write one draft, immediately.

    Outside the write prefix on purpose: a draft moves nothing of hers, which is
    what lets the Reader hold no write tool and still have somewhere to put what
    it read. A draft becomes a recipe only through the chokepoint, on her yes.

    Args:
        source: The file it came from.
        set_: What was on the page.
        gap: Lines that could not be read.
        unusable: Why there is no draft.
    """
    attempted = "keeping what was read"

    def work() -> Envelope:
        fields: dict[str, str] = {}
        for raw in set_ or []:
            name, _, value = raw.partition("=")
            if not _:
                raise PaprikaError(
                    Code.REFUSED_LOCALLY,
                    "That wasn't written in a way we could keep.",
                    detail=f"expected field=value, got {raw!r}",
                )
            fields[name.strip()] = value
        draft = intake.save(source, fields, tuple(gap or []), unusable)
        # Nothing of hers moved: a draft is ours and disposable.
        return succeeded(
            attempted,
            data={"source": draft.source, "usable": draft.unusable is None},
        )

    _run(attempted, work)


@intake_app.command("list")
def intake_list() -> None:
    """Report what has been read, in the order it should be reviewed.

    Clean recipes first and gapped ones last, because stopping a third of the
    way through a folder should still leave her ahead. Files that produced no
    recipe are not in the walk at all — they are counted at the end.
    """
    attempted = "reading what has been drafted"

    def work() -> Envelope:
        drafts = intake.waiting()
        reviewable = intake.in_lanes(drafts)
        # The duplicate check reads her Library, so it establishes freshness
        # like any other read — the files are static but the Library is not,
        # and a recipe saved earlier in this same walk has to count.
        try:
            with _current_mirror(False) as (mirror, _checked):
                library = {r.handle: r.name for r in mirror.recipes()}
        except PaprikaError as unread:
            if unread.code is not Code.NOTHING_MIRRORED:
                raise
            # Nothing downloaded means nothing to be a duplicate of. The drafts
            # still list; they simply cannot be checked against anything.
            library = {}
        return succeeded(
            attempted,
            data={
                "drafts": [
                    {
                        "source": draft.source,
                        "name": draft.fields.get("name", ""),
                        "lane": intake.lane_of(draft),
                        "gaps": list(draft.gaps),
                        # Both directions: the folder can hold the same recipe
                        # twice, and it can hold one she already has.
                        "looks_like": intake.matches_for(draft, library, drafts),
                    }
                    for draft in reviewable
                ],
                "count": len(reviewable),
                "clean": sum(
                    1 for d in reviewable if intake.lane_of(d) == intake.CLEAN
                ),
                # Named, never silently dropped.
                "skipped": [
                    {"source": draft.source, "why": draft.unusable}
                    for draft in drafts
                    if intake.lane_of(draft) == intake.SKIPPED
                ],
            },
        )

    _run(attempted, work)


@intake_app.command("done")
def intake_done(
    source: Annotated[
        str | None, typer.Option("--source", help="One draft, by its file.")
    ] = None,
    everything: Annotated[
        bool, typer.Option("--all", help="Every draft, because the walk ended.")
    ] = False,
) -> None:
    """Forget drafts that have been dealt with.

    Args:
        source: One draft, by the file it came from.
        everything: Every draft.
    """
    attempted = "clearing what has been dealt with"

    def work() -> Envelope:
        if everything:
            return succeeded(attempted, data={"dropped": intake.clear()})
        if not source:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "Say which one, or say all of them.",
                detail="neither --source nor --all",
            )
        intake.done(source)
        return succeeded(attempted, data={"dropped": 1})

    _run(attempted, work)


nutrition_app = typer.Typer(
    no_args_is_help=True, help="Work out nutrition, only when asked."
)
app.add_typer(nutrition_app, name="nutrition")


def _rolled(since: str, until: str, handle: str | None) -> dict[str, Any]:
    """Work out nutrition over a stretch of days, or for one recipe.

    The index and the memos are opened once around the whole job, because
    opening them is the expensive part.

    Args:
        since: First day.
        until: Last day.
        handle: One recipe instead of a stretch, when she asked about one.

    Returns:
        dict[str, Any]: The envelope payload.
    """
    from paprika_core.nutrition import analysis, rollup

    with analysis.opened() as (index, memos):

        def analyse(lines: list[str]) -> Any:
            return analysis.analyse(lines, index, memos)

        with Mirror(store.mirror_path()) as mirror:
            if handle is not None:
                body = mirror.recipe_body(handle)
                if body is None:
                    raise PaprikaError(
                        Code.NOTHING_MIRRORED,
                        "That isn't a recipe we know about.",
                        detail=f"unknown handle {handle!r}",
                    )
                from paprika_core.groceries import _ingredient_lines

                made = rollup.of_lines(_ingredient_lines(body), analyse)
            else:
                made = rollup.over(mirror, since, until, analyse)
    return rollup.as_data(made)


@nutrition_app.command("rollup")
def nutrition_rollup(
    since: Annotated[str, typer.Option("--from", help="First day, YYYY-MM-DD.")] = "",
    until: Annotated[str, typer.Option("--to", help="Last day, YYYY-MM-DD.")] = "",
) -> None:
    """Work out what a stretch of days comes to.

    The week is the unit. Nothing here is journaled and nothing is attached to
    a plan — it is computed when she asks and not before.

    Args:
        since: First day.
        until: Last day.
    """
    attempted = "working out how the week looks"
    _run(attempted, lambda: succeeded(attempted, data=_rolled(since, until, None)))


@nutrition_app.command("recipe")
def nutrition_recipe(
    handle: Annotated[str, typer.Argument(help="Which recipe.")],
) -> None:
    """Work out what one recipe comes to.

    Args:
        handle: Which recipe.
    """
    attempted = "working out what a recipe comes to"
    _run(attempted, lambda: succeeded(attempted, data=_rolled("", "", handle)))


@write_category_app.command("create")
def write_category_create(
    name: Annotated[str, typer.Option("--name", help="What she would call it.")],
    parent: Annotated[
        str,
        typer.Option("--parent", help="The category it belongs under, by name."),
    ],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Add one category under an existing one.

    The parent is required rather than defaulted, because a default would be
    taken and a new top-level category flattens the tree she built.

    Args:
        name: What she would call it.
        parent: The category it belongs under.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "adding a category"

    def work() -> Envelope:
        client = sign_in()
        try:
            with Mirror(store.mirror_path()) as mirror, undo.open_run(run) as opened:
                categories_module.create(
                    client, name=name, parent=parent, mirror=mirror, run=opened
                )
                changed, joined = opened.changed(), opened.id
            _after_write(client, done)
        finally:
            client.close()
        return Envelope(
            ok=True,
            attempted=attempted,
            changed=changed,
            data={"run": joined, "added": name},
        )

    _run(attempted, work)


@write_category_app.command("file")
def write_category_file(
    handles: Annotated[list[str], typer.Argument(help="The recipes in this group.")],
    into: Annotated[str, typer.Option("--into", help="Where they go, by name.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """File a whole group of recipes under one category.

    One group is one screen and one yes, so it is also one Run — undo reverses
    what she just agreed to rather than the whole evening. The Run stops at the
    first failure and names what did not go through.

    **Additive only.** Nothing here removes a category she chose.

    Args:
        handles: The recipes in this group.
        into: Where they go, by name.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "filing a group of recipes"

    def work() -> Envelope:
        patch = Patch.parse(adds=[f"categories={into}"])
        found, category_names = _resolve(handles)
        mutate = patch.as_mutation({"categories": category_names})
        return _perform(
            attempted, [(uid, name, mutate) for uid, name in found], run, done
        )

    _run(attempted, work)


@app.command("grocery-draft")
def grocery_draft(
    since: Annotated[str, typer.Option("--from", help="First day, YYYY-MM-DD.")] = "",
    until: Annotated[str, typer.Option("--to", help="Last day, YYYY-MM-DD.")] = "",
    fresh: Annotated[bool, FRESH_OPTION] = False,
) -> None:
    """Work out the week's shopping, minus what she already has.

    Computed here rather than in a conversation, because it has to come out the
    same every time.

    Args:
        since: First day.
        until: Last day.
        fresh: Force the freshness check rather than reusing a recent answer.
    """
    attempted = "working out your shopping list"

    def work() -> Envelope:
        with _current_mirror(fresh) as (mirror, _checked):
            made = groceries.draft(mirror, since, until)
        age = made.pantry_age_days
        return succeeded(
            attempted,
            data={
                "buy": [
                    {"line": item.line, "for": item.recipe} for item in made.wanted
                ],
                "count": len(made.wanted),
                # Named always; what changes with age is whether the list is
                # expected to say so out loud, never whether it subtracted.
                "already_have": made.subtracted,
                "pantry_age_days": round(age, 1) if age is not None else None,
                "pantry_stale": made.pantry_stale,
            },
        )

    _run(attempted, work)


@write_groceries_app.command("push")
def write_groceries_push(
    since: Annotated[str, typer.Option("--from", help="First day, YYYY-MM-DD.")] = "",
    until: Annotated[str, typer.Option("--to", help="Last day, YYYY-MM-DD.")] = "",
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Put the week's shopping into Paprika's own list.

    The plugin builds no list of its own. This is her list, in the app she
    already shops from, rendered by the app.

    Args:
        since: First day.
        until: Last day.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "adding to your shopping list"

    def work() -> Envelope:
        client = sign_in()
        try:
            with Mirror(store.mirror_path()) as mirror:
                made = groceries.draft(mirror, since, until)
            with undo.open_run(run) as opened:
                added = groceries.push(client, made.wanted, run=opened)
                changed, joined = opened.changed(), opened.id
            _after_write(client, done)
        finally:
            client.close()
        return Envelope(
            ok=True,
            attempted=attempted,
            changed=changed,
            data={"run": joined, "added": added, "already_have": made.subtracted},
        )

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
DONE_OPTION = typer.Option(
    "--done", help="This finishes the job, so tell her other devices to pull."
)

#: The four slots, as she says them.
_SLOT_NAMES = {number: name for name, number in plan.SLOTS.items()}


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
    done: bool = False,
) -> Envelope:
    """Run a set of writes as one Run and turn the outcome into an envelope.

    Args:
        attempted: What is being tried.
        targets: What to change.
        run_id: An open Run to join, or ``None`` to start one.
        done: Whether this finishes the job.

    Returns:
        Envelope: The result, carrying the Run so a stopped one is addressable.
    """
    client = sign_in()
    try:
        with undo.open_run(run_id) as run:
            outcome = bulk.apply_all(client, targets, run=run)
            joined = run.id
        _after_write(client, done)
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


@write_recipe_app.command("create")
def write_recipe_create(
    set_: Annotated[list[str] | None, typer.Option("--set", help="field=value")] = None,
    add: Annotated[
        list[str] | None, typer.Option("--add", help="categories=Name")
    ] = None,
    invented: Annotated[
        bool,
        typer.Option("--invented", help="This one is ours, so mark it as ours."),
    ] = False,
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Save a new recipe.

    Built from the core's own blank rather than from anything a caller supplied,
    so a create obeys the same rule as an edit: fields may be filled in, and may
    never be chosen.

    Args:
        set_: Fields to fill in.
        add: Categories to file it under, by name.
        invented: Whether this recipe is one we made up rather than one of hers.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "saving a new recipe"

    def work() -> Envelope:
        patch = Patch.parse(sets=set_ or [], adds=add or [])
        with Mirror(store.mirror_path()) as mirror:
            categories = {
                name.casefold(): uid for uid, name in mirror.category_names().items()
            }
        mutate = patch.as_mutation({"categories": categories})

        client = sign_in()
        try:
            with undo.open_run(run) as opened:
                _uid, name = write.create(
                    client,
                    mutate,
                    run=opened,
                    invented_on=dt.date.today().isoformat() if invented else None,
                )
                changed, joined = opened.changed(), opened.id
            _after_write(client, done)
        finally:
            client.close()
        return Envelope(
            ok=True,
            attempted=attempted,
            changed=changed,
            data={"run": joined, "saved": name},
        )

    _run(attempted, work)


@write_recipe_app.command("nutrition")
def write_recipe_nutrition(
    handle: Annotated[str, typer.Argument(help="Which recipe.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Write what a recipe comes to into the recipe itself.

    A command of its own rather than a field anyone can set, because the string
    it writes **escapes to her phone**, where no skill is running and nothing
    can explain it. The hedge and the date are composed here so that they cannot
    be left off, and this overwrites whatever the recipe's author had put there.

    Args:
        handle: Which recipe.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "writing the nutrition into a recipe"

    def work() -> Envelope:
        from paprika_core.nutrition import rollup as rollup_module

        with Mirror(store.mirror_path()) as mirror:
            uid = mirror.uid_for(handle)
            name = mirror.recipe_body(handle)
        if uid is None or name is None:
            raise PaprikaError(
                Code.NOTHING_MIRRORED,
                "That isn't a recipe we know about.",
                detail=f"unknown handle {handle!r}",
            )
        made = _rolled("", "", handle)
        rebuilt = rollup_module.Rollup(
            nutrients=tuple(
                rollup_module.Nutrient(
                    name=n["name"], low=n["low"], high=n["high"], exact=n["exact"]
                )
                for n in made["nutrients"]
            ),
            excluded=tuple(made["excluded"]),
            refused=made["no_number_because"],
        )
        try:
            text = rollup_module.written_back(rebuilt, dt.date.today().isoformat())
        except ValueError as unearned:
            raise PaprikaError(
                Code.REFUSED_LOCALLY,
                "There isn't a number worth putting in that recipe.",
                detail=str(unearned),
            ) from unearned

        def mutate(recipe: dict[str, Any]) -> None:
            recipe["nutritional_info"] = text

        client = sign_in()
        try:
            with undo.open_run(run) as opened:
                write.write(client, uid, mutate, run=opened)
                changed, joined = opened.changed(), opened.id
            _after_write(client, done)
        finally:
            client.close()
        return Envelope(
            ok=True,
            attempted=attempted,
            changed=changed,
            data={"run": joined, "written": str(name.get("name") or "")},
        )

    _run(attempted, work)


@write_recipe_app.command("trash")
def write_recipe_trash(
    handles: Annotated[list[str], typer.Argument(help="Which recipes.")],
    run: Annotated[str | None, RUN_OPTION] = None,
    done: Annotated[bool, DONE_OPTION] = False,
) -> None:
    """Put recipes in Paprika's trash, where she can get them back herself.

    Several at once, because *keep this one and trash the rest* is one act and
    should be one Run. Her recovery is the app's own trash and does not depend
    on our snapshot surviving.

    Args:
        handles: Which recipes.
        run: An earlier Run to join.
        done: Whether this finishes the job.
    """
    attempted = "moving recipes to the trash"

    def work() -> Envelope:
        found, _categories = _resolve(handles)

        def mutate(recipe: dict[str, Any]) -> None:
            recipe["in_trash"] = True

        return _perform(
            attempted, [(uid, name, mutate) for uid, name in found], run, done
        )

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
            _mirror_is_now_stale()
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


@app.command()
def primer(
    root: Annotated[
        Path,
        typer.Option(
            help="The plugin's own directory, which is where the skills live.",
        ),
    ] = PLUGIN_ROOT,
) -> None:
    """Print what a session is told before she has said anything.

    **The one command with no envelope, and deliberately so.** Its reader is a
    shell hook that injects stdout verbatim into the session; wrapping this in
    JSON would mean the hook needed a parser before it could say anything, and a
    hook that can fail is a hook that eventually takes Claude Code down with it.

    ``--root`` exists because the two halves live apart: the skills sit in the
    plugin directory, this command sits in its own environment, and neither can
    find the other by looking upwards.

    Args:
        root: The plugin's root directory.
    """
    sys.stdout.write(primer_module.build(root) + "\n")


def main() -> None:
    """Run the CLI, exiting with a code that agrees with the envelope."""
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
