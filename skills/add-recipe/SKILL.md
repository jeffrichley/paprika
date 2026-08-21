---
name: add-recipe
description: Use when the user pastes a recipe link, dictates or pastes a recipe as text, asks to add or save a recipe, or points at a file or folder of scanned or photographed recipes by name.
---

# Getting a recipe in

Two ways in here: **a link she pastes**, and **a recipe she says or pastes as
text**. Both end the same way — a drafted recipe she reads, corrects, and says
yes to.

A **file or folder she names** is the third way in, and it has its own section
below. **Inventing one** is the fourth, and the only one where the recipe is
ours rather than hers.

## Structure is ours, words are hers

Splitting a blob into ingredient lines, deciding what is an ingredient and what
is a step, putting the steps in order — do all of that silently. That is
structure, and it is ours.

**Rewriting what she wrote is not.** `1 c.` stays `1 c.`. Abbreviations stay
abbreviated. Her phrasing stays her phrasing. She is going to cook from this,
and she wants the recipe she gave you.

## What she said to you is not part of the recipe

A field's content is **what she put under that field's label**, and nothing else.

Text that sits outside any label — after the last labelled block, or between
them — is her talking to you. *"Yes, both categories are deliberate."* *"Once
it's saved, put this picture on it."* Those are instructions. The second was
read correctly as one; the first was saved into her notes.

**When you cannot tell whether a line is an aside or content, ask.** That is a
scope question and it is always fair. Do not resolve it by where the line
happens to sit.

| The thought | What is true |
|---|---|
| "She typed it, so she wants it in the recipe" | She typed it to **you**. |
| "It came after the notes, so it is a note" | Position is not a label. She wrote the labels. |
| "It's harmless, leave it in" | She reads this in a kitchen in two years and has no idea why it is there. |

## Anything not there stays empty

If the page or the dictation does not say how many it serves, **leave servings
empty**. Same for times, difficulty, everything. Blank means *she did not say
it*, and that is information. A guess looks exactly like a fact she gave you.

There is no exception here for a missing title — a recipe with no name cannot be
saved, so ask her for one.

## Check whether she already has it

**Before offering to save**, look:

```bash
paprika recipe search "soda bread"
```

Search her actual library, by the words in the title and by a distinctive
ingredient. This is lexical and it is against what she really has, which is why
it can be trusted.

If something comes back, **show it with the difference** — what hers has that
this one does not, or the other way round — and offer two choices:

> You've already got a **Soda Bread**. Yours uses buttermilk and bakes at 200°C;
> this one uses yoghurt and 220°C. Add this as well, or leave it?

**Add anyway, or skip. Never merge.** Merging decides which version of her
recipe survives, and that is not a decision to make on her behalf.

## Render it whole, then ask

Show the drafted recipe in full and ask about **that recipe**. Not "shall I save
these", not a yes she gave earlier.

**In full means every field you are about to write, whole.** Show, in this order:

1. **The title**, as it will be saved.
2. **Every ingredient line**, verbatim.
3. **Every step**, verbatim.
4. **The notes**, verbatim — every line of them.
5. **Every other field you are setting**: servings, difficulty, the three times,
   source, source URL, nutrition, categories. With its value, not its name.
6. **What you left blank**, and that it was blank because she did not say it.

**Never a count.** Not "all four notes", not "the usual fields", not "everything
you gave me". A count is not a showing, and she cannot agree to text she has not
read. That failure has happened here: a line addressed to the assistant was
saved into her notes and the confirmation reported the number four rather than
the four lines, so the one she would have objected to went past her.

Free text is where this matters most — notes, ingredients, directions. Those are
the fields where a wrong line survives for years and is read in a kitchen.

## Saving

```bash
paprika write recipe create \
  --set "name=Nana's Soda Bread" \
  --set "ingredients=450g flour
1 tsp bicarb
400ml buttermilk" \
  --set "directions=Mix. Bake at 200C for 40 minutes." \
  --set "source=Nana" \
  --add "categories=Bread" \
  --done
```

Use `--set source` and `--set source_url` for a link. **Do not mark it as
coming from us** — she found it, or she wrote it, and a year from now the source
should say so honestly.

File it under a category only if one obviously fits. Guessing a category is
worse than leaving it out, because a wrong one is harder to notice than a
missing one.

## A folder she points at

Same gesture as a single file, and the same rule: **you never open it.** Dispatch
the **file-reader** agent with the path. It reads everything, one draft per file,
saving each as it lands.

### What to say before the first screen

1. **What was found** — *"40 files across 3 folders."*
2. **Roughly how long the walk is**, so she knows what she is committing to.
3. **That stopping partway is fine**, because it is.

Say all three, then start. `paprika intake list` gives you the counts.

### The order is not yours to choose

`intake list` returns them in review order: **clean ones first, gapped ones
last.** Do not reorder them, and do not interleave. Stopping a third of the way
through should leave her ahead, and it only does if the good ones came first.

**Name the lane boundary out loud when you reach it**, as a stopping point:

> That's all 27 clean ones. The remaining 6 each have a line I couldn't read —
> worth carrying on, or leave them for now?

### What one screen is made of

One recipe per screen, by default. In this order:

1. **The recipe, whole** — title, ingredients, steps.
2. **Any gap**, pointed at where it sits in the text.
3. **Anything it looks like**, from `looks_like`, with the difference.
4. **One question about this recipe.**

**Offer the lighter form; never assume it.** *"Want me to go one at a time, or
just list the clean ones and you say which to keep?"* How carefully she looks at
her own pages is her call.

### Her answers

- **Yes** — save it, and it is **its own Run**, so undo reverses that recipe.
- **No** — drop it, move on. Do not ask again and do not ask why.
- **A correction** — edit the draft and stay on this screen. A correction is not
  a no.

Then `paprika intake done --source <path>` so a resumed walk does not re-offer
it.

### Ending

`--done` on the last save, so her phone hears once rather than forty times.

Then **one closing count**, including what was skipped:

> Saved 22. Skipped 3 I couldn't open: `page_07.jpg`, `page_19.jpg`,
> `notes.txt`.

Then `paprika intake done --all`. The drafts are finished with.

### If she stops and comes back

`intake list` still has everything — nothing is read twice. But the duplicate
check runs again, because she may have saved something since, and it may now
match. Do not carry forward what it said last time.

## Inventing one

When nothing she has fits and she wants something new. This path is different
from the other three in exactly two ways, and both come from the same fact: the
recipe is **ours**.

### Render it whole first

Show the entire recipe — title, every ingredient, every step — **before** you
offer to save it. Not a summary, not the idea of it.

Everywhere else, showing before asking is good manners. Here it is the whole
safeguard: she is about to put something in her library that nobody wrote, and
the only way she can judge it is by reading it.

Then ask about that recipe.

### Mark it

```bash
paprika write recipe create --set "name=…" --set "ingredients=…"   --set "directions=…" --invented --done
```

`--invented` is what makes it ours in the record. You do not write the source
yourself and you cannot — the command applies the mark, and trying to type it by
hand is refused. A year from now she should be able to see which recipes in her
library came from a conversation, and that only works if the mark cannot be
forgotten.

It also cannot be edited away afterwards. Where a recipe came from is not
something to change later.

### Never a filler

An invented recipe is something she asked for. It is never how a gap gets
quietly closed — not a night in a plan, not a hole in a folder walk. If nothing
fits, the honest answer is that nothing fits.

## Rules that do not bend

- **Never tidy her wording.**
- **Never fill in something the source did not say.**
- **Never merge two recipes.** Add anyway or skip.
- **Never save without a yes covering the recipe you just showed her.**
- **Mark a recipe as ours only when we invented it**, and only with
  `--invented`. The other three ways in are hers.
- **Never offer to save an invented recipe you have not shown her whole.**
- **Never invent one to fill a gap she did not ask you to fill.**
- **Never open a named file or folder yourself.** Dispatch the Reader.
- **Never reorder the walk**, and never skip the lane boundary.

## When you are about to break one of those

| The thought | What is actually true |
|---|---|
| "`1 c.` will confuse her later" | It is how she wrote it, and how her book writes it. |
| "Every recipe should say how many it serves" | Blank means the page didn't say. That is information. |
| "She already has one but this is the better version" | Add anyway or skip. Which survives is hers to decide. |
| "The duplicate check is slow, the title is clearly new" | It is one command against her real library. Run it. |
| "It obviously belongs under Baking" | A wrong category is harder to notice than a missing one. |

## Common mistakes

| Mistake | Instead |
| --- | --- |
| "1 c." → "1 cup" | Leave her words alone |
| Guessing servings from the ingredients | Leave it empty |
| Saving before checking for a duplicate | Search first, every time |
| Offering to combine two versions | Add anyway, or skip |
| Filing it under a plausible category | Only if it obviously fits |
