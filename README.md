# paprika

A Claude Code plugin for managing a [Paprika 3](https://www.paprikaapp.com/) recipe library and planning
meals from it — in plain English, by someone who is not a developer.

Paprika stays where you cook and shop from. This is where the library gets tidied and the week gets
planned.

> **You talk to it in your own words.** You never type a command, and you never need to know one. The
> commands in this file are for installing it and for anyone poking at the code.

## What it can do

| | |
| --- | --- |
| **Plan a week** | Drafts dinners from your own recipes, avoiding what you ate recently, giving fast nights fast meals, and leaving a night **empty with a reason** rather than filling it with something nobody wanted. |
| **Build the shopping list** | The week's ingredients with what's already in your cupboard taken off, pushed into Paprika so you shop from the app you already shop from. |
| **Keep track of what's in** | Tell it what you bought, or send a photo of a shelf. It only ever adds and confirms — only you can say something has run out. |
| **Get recipes in** | Paste a link, say a recipe out loud, or point at a folder of forty scanned cookbook pages and work through them. |
| **Find one you already have** | *"That chicken thing with the lemons."* Misspellings don't matter — it reads your library rather than searching it. |
| **Change one** | Describe the change. Nothing else about the recipe moves. |
| **Tidy up** | Ask how messy your library is and get an answer instantly. Re-file hundreds of recipes in groups, and see duplicates side by side. |
| **Ask how a week looks** | Four numbers — energy, protein, carbs, fat — by the week, only when you ask, always with the uncertainty visible. |

Say what you want in your own words. *"Plan next week."* *"What can I make with the lamb?"* *"I bought
rice, cumin and two tins of tomatoes."* *"Is this one lighter than the other?"*

If you're not sure what to ask for, say **"what can you do?"**

## Installing it

Two steps: the command it runs on, and the plugin itself.

### 1. Install `uv`

`uv` is the tool that installs and runs the Python part. If you already have it, skip this.

**macOS or Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen your terminal afterwards, then check it worked:

```bash
uv --version
```

### 2. Install the `paprika` command

```bash
uv tool install git+https://github.com/jeffrichley/paprika
```

That downloads everything it needs and puts one command on your machine. Check it:

```bash
paprika status
```

It should answer that Paprika isn't set up yet. That's the right answer at this point.

If your shell says `paprika: command not found`, run `uv tool update-shell` and open a new terminal.

### 3. Add the plugin to Claude Code

In Claude Code:

```
/plugin marketplace add jeffrichley/paprika
/plugin install paprika@paprika
```

Then start a new session, so it picks the plugin up.

### Updating

```bash
uv tool upgrade paprika-plugin
```

and `/plugin update paprika` in Claude Code.

## Setting it up

Say **"set up Paprika"** and answer the questions. It will ask for the email and password you use to sign
in to Paprika itself, then copy your recipes down to this machine.

That copy takes a few minutes — it fetches your recipes one at a time, because Paprika's API has no way to
ask for them in bulk. It'll tell you roughly how long before it starts. **Closing your laptop partway is
safe**; it picks up where it stopped rather than starting over.

You only do this once.

## Where your things are kept

Everything lives in a folder called `.paprika` in your home directory, and what a file is called tells you
what you'd lose by deleting it:

| | |
| --- | --- |
| `.env`, `profile.toml` | **Yours.** Your sign-in, and your household — who lives here, allergies, what people don't like. Never deleted automatically. `profile.toml` is the one file you can safely edit by hand, and it explains itself in its own comments. |
| `undo.sqlite3` | **Precious.** A copy of everything before it was changed, which is what undo puts back. |
| `nutrition.sqlite3` | **Expensive.** Nutrition working-out that took a while and doesn't need doing twice. |
| `cache.sqlite3`, `usda.sqlite3`, `logs/`, `intake/` | **Disposable.** Copies and working files. Deleting any of them costs you time, never data. |

Your recipes themselves live in Paprika, not here. This folder is a copy plus your own settings.

## Uninstalling

```bash
uv tool uninstall paprika-plugin
```

and `/plugin uninstall paprika` in Claude Code.

**Your `.paprika` folder is left alone**, so reinstalling doesn't mean setting up again. Delete it
yourself if you want it gone.

## When something's wrong

Ask **"is Paprika set up?"** — there are four answers and they mean different things.

| | |
| --- | --- |
| **Set up** | Everything's fine. |
| **Not finished** | It'll tell you what's left. Say "finish setting up Paprika". |
| **Never set up** | Say "set up Paprika". |
| **Can't be read** | Something on this machine is damaged. **Your recipes in Paprika are untouched.** Don't start setup over — say "help" and it'll take it from there. |

If a command failed, it'll have told you what it tried, what didn't happen, and whether your library
actually changed. If something got changed that you didn't want, say **"undo that"**.

## How it keeps your recipes safe

Worth knowing, because the risk is real: Paprika's API replaces a whole recipe on every edit, and at least
one other tool out there wipes ratings, categories, sources and photos every time it saves anything.

- **Every change goes through one place** that reads the recipe first and writes it back whole. There's no
  way to send a partial recipe, so there's no way to lose a field by forgetting it.
- **Everything is copied before it's changed**, so undo can put it back — by name, in your own words.
- **Deleting means Paprika's own trash**, so you can restore it from the app without asking anyone.
- **Nothing is ever saved without you saying yes** to exactly what you were shown.
- **Two background helpers** read your library and read files you point at. Neither of them can write
  anything at all — they suggest, you decide.

## Unaffiliated

This is an unofficial community project. It is **not affiliated with, endorsed by, or supported by
Hindsight Labs LLC**, the makers of Paprika Recipe Manager.

It works through Paprika's sync API, which is not a documented or supported interface. It may change or
stop working at any time, and this project has no relationship with the people who maintain it. The name
"Paprika" is used only to identify the app this plugin works with.

## How your credentials are stored

Setting up paprika saves your Paprika **email and password** to a file on your own computer, readable only
by your user account. Your password is saved — not just a login token — because Paprika's tokens expire on
a schedule nobody outside Paprika knows, and being asked to log in again mid-week is exactly the
interruption this plugin exists to avoid.

**This is a deliberate trade-off.** Storing your password in your system keyring would be more secure. It
was not chosen because it prompts with dialogs that are hard to interpret, and because it makes it
impossible for someone else to help you repair a broken setup remotely — the person fixing your install is
usually on the phone, not at your keyboard.

What this means in practice: **anyone who can read files in your user account can read your Paprika
password.** On a personal machine that only you log into, that is the accepted trade-off. If you share a
computer login with someone you would not hand your Paprika password to, don't install this.

The reasoning is recorded in full in
[ADR 0002](docs/adr/0002-password-stored-at-rest.md).

## What it deliberately doesn't do

- **Help while you're cooking.** The app already owns the kitchen.
- **Merge duplicate recipes.** It shows you them side by side; which version survives is your call.
- **Micronutrients.** Sodium, iron and the rest are wrong by half in tools that report them, so it refuses
  rather than guessing.
- **Anything to your library without asking.**

## For developers

Requires [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/).

```bash
just install     # one venv, one lockfile
just check       # Black, Ruff, mypy, Vulture, pytest, and the 80% coverage floor
just format      # rewrite with Black and Ruff's autofixes
```

`just check` is what has to be green before anything is pushed. CI runs the same gate on 3.11, 3.12 and
3.13.

**No test can reach the network.** Two autouse fixtures see to it: one puts a fake Paprika in front of
every request, and the other fails the test loudly if a real socket is ever opened. The fake reproduces
the API's actual misbehaviour — errors returned at success statuses, a bare 500 for a malformed write, no
bulk recipe endpoint — rather than an idealised version of it, because wire-format code is the riskiest
code here and a tidy fake would skip exactly the parts that matter.

The design is written down and worth reading before changing anything: [the
spec](https://github.com/jeffrichley/paprika/issues/29), the [architecture decisions](docs/adr/),
[`CONTEXT.md`](CONTEXT.md) for the vocabulary, and
[`docs/agents/skill-writing.md`](docs/agents/skill-writing.md) before writing a skill.

## License

[MIT](LICENSE)
