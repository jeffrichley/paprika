---
name: plan-week
description: Use when the user wants meals planned for a week or a stretch of days, asks what they should cook, wants to change or swap what is planned for a particular night, or asks what is already planned.
---

# Planning a week

She says *"plan next week"* and gets a whole week drafted from her own recipes,
built around what they actually ate lately, which nights are fast, and who is
away.

**REQUIRED READING:** load `skills/shared/cooking-judgement.md` before drafting.
It holds what makes a week good rather than merely full, and this skill assumes
it.

## State the week, don't ask for it

Say which days you are planning. Do not ask her which week she meant.

> Next week — **Monday 24 to Sunday 30 August**, dinners only. Say so if you
> meant something else.

The common case costs no round trip, and she can correct you in one sentence.
Dinners unless she says otherwise.

## Before you draft

Three reads, and they are cheap:

1. **`paprika profile show`** — allergies, who lives here and what they dislike,
   which nights are fast, who is away.
2. **`paprika plan show --from <a> --to <b>`** over the *last* two or three
   weeks — what they have had recently.
3. **`paprika recipe index`** — the whole library, one line each.

Pull a handful of bodies with `paprika recipe get` when a night's choice turns
on ingredients rather than titles.

**Ask who is joining before you draft anything.** `guests_to_ask_about` names
the people whose presence changes what is safe. Ask once, for the week, using
what the Profile already knows so it is a checkable question rather than an open
one — *"Monica on Sunday as usual, or is it a different night?"* Their allergies
then bind those nights and no others.

If she does not know yet, **apply their allergies to the whole week**. A week she
can loosen later is better than one that has to be redrawn.

**Before you show her the week, run `paprika recipe check` over every recipe in
it** — with `--for` naming the guests' allergies on the nights they are at, as
well as what the household always avoids. After your own reading, never instead
of it. A live test had two careful readings of the same recipes both miss
something, and the one that mattered was named in a notes field.

**If the allergy line is absent, nobody has been asked.** That is not the same
as none. Ask before drafting anything that could go wrong.

## What the draft is made of

One pass, holding the whole week in mind — not a quick draft you then improve.
Cooking judgement is applied *while* drafting, not afterwards.

Say these parts, in this order:

1. **Which days you planned**, stated rather than asked.
2. **The week as a table** she can read at a glance, one row per night.
3. **A short reason on the nights where one helps** — *"Thursday's fast so this
   is a traybake"*, *"you had the chilli last week"*. Not one per night; that
   reads like a machine justifying itself.
4. **One line saying nothing is saved yet.**

A night nothing fits gets, in its own row: **the word empty, one line of why,
and two or three short options.**

> **Wed 26** — *empty*. Everything quick enough for a fast night, you've had in
> the last fortnight. Could do: eggs on toast, a shop-bought pizza, or I could
> find something new.

An empty night with an honest reason is the moment she learns the drafts can be
trusted. Filling it by lowering the bar is what costs that.

## Changing a night

She says *"not Tuesday, we're out"* or *"swap Wednesday for something lighter"*.
Redraft that night and show it. It is the same whether or not the plan has been
saved yet — a saved plan is changed with the same sentence.

Show the night that changed. Show the whole week again only if she asks for it.

## Inventing a dish mid-plan

If she likes one of the options offered against an empty night — or just says
*"make something up"* — do it **here**. Do not send her to another skill; the
week is what she is thinking about.

**Render the recipe whole before offering to save it.** Every ingredient, every
step. She is about to put something in her library that nobody wrote, and
reading it is the only way she can judge it.

Then save it with `--invented`, which marks it as ours, and put it on the night
— joining both to the same Run so one undo reverses both:

```bash
paprika write recipe create --set "name=…" --set "ingredients=…"   --set "directions=…" --invented
paprika write plan set --date … --slot dinner --recipe <handle> --run <run> --done
```

**Never invent one to fill an empty night she has not asked you to fill.** An
empty night with a reason is the honest answer; a made-up dish nobody asked for
is the opposite of what leaving it empty was for.

## Saving it

**One yes covering exactly the week you showed her.** Not "shall I save this
going forward", not a yes she gave to something earlier. Show the week, ask
about that week, save on that answer.

Then, per night:

```bash
paprika write plan set --date 2026-08-24 --slot dinner --recipe <handle>
paprika write plan set --date 2026-08-25 --slot dinner --name "Leftovers" --run <run>
paprika write plan set --date 2026-08-27 --slot dinner --recipe <handle> --run <run> --done
```

Use `--recipe` for one of hers and `--name` for anything else — a takeaway, an
evening out, leftovers.

**Join the nights together** by passing the `--run` value the first command
returns, so putting the week back is one action rather than seven. Put `--done`
on the **last** one only: it tells her other devices to pick the week up, and a
week saved night by night must not make her phone buzz seven times.

Leave empty nights empty. Do not write a placeholder into one.

It reaches her phone by itself; you do not have to do anything for that, and you
should not mention it unless she asks.

## Rules that do not bend

- **Never propose something against a household allergy.** Not "she can leave it
  out". Not once.
- **Never fill a night just to avoid an empty one.**
- **Never save without a yes that covered what was on screen.**
- **One reason at most per night, and only where it helps.**
- **Never mention how any of this works.** Not the program, not what was
  written, not what was read, not where anything is kept. She asked for dinner.

## Common mistakes

| Mistake | Instead |
| --- | --- |
| "Which week did you mean?" | State the week; she'll correct you if it's wrong |
| A draft, then a second pass to improve it | One pass with judgement applied throughout |
| Filling Wednesday with something mediocre | Leave it empty, one line of why, two or three options |
| Re-showing the whole week after one swap | Show the night that changed |
| Saving each night as its own Run | One Run, so one undo puts the week back |
| Explaining that it synced | She only needs to know it's on her phone if she asks |
