# paprika

A Claude Code plugin for managing a [Paprika 3](https://www.paprikaapp.com/) recipe library and planning
meals from it — in plain English, by someone who is not a developer.

Paprika stays where you cook and shop from. This is where the library gets tidied and the week gets
planned: drafting a week from recipes you already have, building a grocery list with what's already in the
cupboard subtracted from it, getting photographed cookbook pages into the library, and re-filing the
hundreds of recipes that accumulated over a decade of imports.

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

## Status

Early scaffolding — implementation to come. The design is settled and written down: see
[the spec](https://github.com/jeffrichley/paprika/issues/29), the
[architecture decisions](docs/adr/), and [`CONTEXT.md`](CONTEXT.md) for the vocabulary the project uses.

## License

[MIT](LICENSE)
