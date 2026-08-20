---
name: grocery-list
description: Use when the user wants a shopping list for a planned week, asks what they need to buy, or wants the week's ingredients added to their shopping list.
---

# The shopping list

The week's ingredients, with what she already has taken off, put into the
shopping list she already shops from.

## Do not build a list

`paprika grocery-draft --from <a> --to <b>` works out what to buy and what she
already has. **The subtraction is not yours to do** — it comes out the same
every time because it is arithmetic, not judgement, and doing it in the
conversation would make it different every week.

Likewise, do not format a shopping list of your own. Paprika renders it, on her
phone, sorted into her own aisles. Anything you draw here is a second list she
has to reconcile against the real one.

## What to say

The draft returns `pantry_stale`. That single flag decides how much explaining
the list does — **and it never changes what was subtracted.**

**Fresh** — say nothing about what was taken off. Subtracting silently is the
feature working; narrating it is noise.

> Added 14 things to your shopping list.

**Stale** — name what was left off and how old that is, so a stale assumption is
visible rather than hidden.

> Added 11 things. I left off cumin, rice and olive oil — that's going on what
> you had a fortnight ago, so check if you're not sure.

**Never confirmed** — say you have not got anything to go on yet, rather than
implying the cupboard is empty.

## Fixing it mid-flow

If she says *"actually I've got the rice"* or *"the cumin's gone"*, record it and
redraft. She does not have to go anywhere else to do this:

```bash
paprika write pantry add rice
paprika write pantry gone cumin
paprika grocery-draft --from 2026-08-24 --to 2026-08-30
```

Then say what changed, not the whole list again.

## Putting it in

```bash
paprika write groceries push --from 2026-08-24 --to 2026-08-30 --done
```

One yes covers the list you showed her. `--done` goes on the last command of the
job so her phone picks it up once.

## Rules that do not bend

- **Never do the subtraction yourself**, and never second-guess it. If it looks
  wrong, the fix is to correct what she has, not to overrule the arithmetic.
- **Never format a shopping list.** Her app already does, better, in her aisles.
- **Never narrate a silent subtraction.** Fresh means say nothing.
- **Never hide a stale one.** Name what was left off and how old it is.
- **Never treat never-confirmed as an empty cupboard.**

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Working out what she has from the recipes | `grocery-draft` did it; read its answer |
| Printing a tidy list in the chat | It's in her app, in her aisles |
| "I subtracted 6 things you already had" (fresh) | Say nothing; it just worked |
| Staying quiet about a three-week-old cupboard | Name what was left off, and its age |
| Sending her elsewhere to fix the pantry | Record it and redraft, right here |
