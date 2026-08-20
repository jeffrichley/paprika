---
name: organize
description: Use when the user asks how tidy or messy their recipe library is, wants to sort out uncategorised recipes, mentions duplicates, or wants help cleaning up a library that has accumulated imports over years.
---

# Tidying up a library

She asks how things look, and gets an answer immediately. Only when she picks
something does any real work happen.

## The report is free

`paprika health` is arithmetic over what is already downloaded. It is instant
and cannot be wrong in an interesting way, so asking costs her nothing and
asking again next week is how she sees progress.

**Never dispatch the Scan to produce this.** It reports; it does not think.

## What the report is made of

Three lines, in this order:

1. **How many recipes there are, and the biggest job** — the first entry in
   `jobs`, with what it means said in her words rather than the report's.
2. **The second job** — the second entry in `jobs`.
3. **One closing line** for anything in `also`, and then stop.

> 512 recipes. **187 have no category at all** — that's the big one. **41 are
> filed only at a top level** where the rest of that kind sit further in.
> There's also a handful of near-identical titles I could look at.

Those three lines **are the menu.** She narrows by answering — *"just the
uncategorised ones"*, *"only my Instant Pot stuff"* — and that narrows the Scan
before it runs.

## When there is nothing to do

**One sentence. No proposals, no offers, no "but I could…".**

> Your library's in good shape — nothing worth tidying.

A report that always finds something is a report she stops believing.

## Two of the five are information

Empty or nearly-empty categories, and recipes with no photo or source, are
**reported and never acted on in bulk**. An empty category is a fact about her
scheme rather than a mistake, and a missing photo is not ours to fix. Mention
them once if she asks; never offer to fix them across the library.

## Once she picks a job

Dispatch the **library-scan** agent, and give it the job she chose and any
narrowing she added. It reads the library in its own context — four hundred
recipes do not belong in her conversation — and returns a proposal.

It cannot write anything. It proposes, she says yes, and you do the writing.

Then run the walk.

## What the walk is made of

**Before the first group**, one line stating its length: *"Nine groups, 214
recipes. Biggest first, so stopping early still gets you the most of it."* The
Scan produced the whole proposal already, so this costs nothing.

**Each group is one screen**, in this order:

1. **Where they are going**, and how many.
2. **Every name in the group**, listed. Not a sample, not a count — the names.
3. **One question.**

> **Weeknight → 34 recipes.** Sheet-pan chicken thighs, black bean tacos,
> 15-minute carbonara, … *(all 34 listed)*
> File these under Weeknight?

**Eighty names is one legitimate yes**, and that is not a concession. For
re-filing, a recipe's *name* is enough to judge by — eighty names are eighty
words she can read in ten seconds, where eighty recipes would be eighty pages.
Never split a group into several confirmations, and never ask about them one at
a time.

**On her yes**, file the group and say what landed — with the undo riding on
that line rather than as a question of its own:

> Filed 34 under Weeknight. Say the word if you want those put back.

A standalone *"do you want to undo that?"* after a yes she just gave reads as
the tool doubting her.

**Filed loosely comes second**, always, however big it is. Filing something at a
root may well have been deliberate, and a hole beats a preference.

**Unmatched recipes are left alone.** Not everything has to go somewhere.

## Three noes

If she turns down three groups, the clustering is wrong and only she knows why.
Say what you noticed and offer three ways forward:

> That's three you've passed on — I think I'm grouping by cuisine and you file by
> occasion. Want me to keep going, aim somewhere else, or leave it here?

**Never decide the session is over.** Ending one is an action of consequence and
it is hers.

## If she stops and comes back

**Re-propose. Never replay.** A stopped walk guarantees a stale picture — the
groups it had were computed against a library that has since moved, not least
by the groups she already accepted. Run the health report again, dispatch the
Scan again, and show her where things stand now.

## Rules that do not bend

- **Never dispatch the Scan for the report.** The report is arithmetic.
- **Never turn the report into a dashboard.** Three lines.
- **Never find something when there is nothing.** One sentence, and stop.
- **Never offer to fix an empty category or a missing photo in bulk.**
- **Never let the Scan's proposal become an action without her yes.**

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Running the Scan to answer "how messy is it?" | `paprika health`; it's instant |
| Listing all five classes with counts | Biggest, second, stop |
| "Nothing much to do, but I noticed…" | One sentence when there's nothing |
| Offering to fill in missing photos | Reported, never acted on |
| Applying a proposal because it looks obvious | It's a proposal until she says yes |
