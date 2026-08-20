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

## Say it in three lines

Biggest win, second, then stop. Not a dashboard.

> 512 recipes. **187 have no category at all** — that's the big one. **41 are
> filed only at a top level** where the rest of that kind sit further in.
> There's also a handful of near-identical titles I could look at.

Those three lines **are the menu.** She narrows by answering — *"just the
uncategorised ones"*, *"only my Instant Pot stuff"* — and that narrows the Scan
before it runs.

Say what the numbers mean in her words, not the words the report uses.

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

Then run the walk, which is `/paprika:organize`'s other half and is covered by
the bulk re-filing rules: groups biggest-first, one group shown whole, one yes
per group, and never a proposal to remove filing she chose.

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
