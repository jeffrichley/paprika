---
name: add-recipe
description: Use when the user pastes a recipe link, dictates or pastes a recipe as text, or asks to add or save a recipe to their library.
---

# Getting a recipe in

Two ways in here: **a link she pastes**, and **a recipe she says or pastes as
text**. Both end the same way — a drafted recipe she reads, corrects, and says
yes to.

Photos and folders of scanned pages are a different skill. Inventing a recipe
from nothing is `/paprika:plan-week`'s job.

## Structure is ours, words are hers

Splitting a blob into ingredient lines, deciding what is an ingredient and what
is a step, putting the steps in order — do all of that silently. That is
structure, and it is ours.

**Rewriting what she wrote is not.** `1 c.` stays `1 c.`. Abbreviations stay
abbreviated. Her phrasing stays her phrasing. She is going to cook from this,
and she wants the recipe she gave you.

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

Show the drafted recipe in full — title, ingredients, steps — and ask about
**that recipe**. Not "shall I save these", not a yes she gave earlier.

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

## Rules that do not bend

- **Never tidy her wording.**
- **Never fill in something the source did not say.**
- **Never merge two recipes.** Add anyway or skip.
- **Never save without a yes covering the recipe you just showed her.**
- **Never mark a recipe as ours.** These two ways in are hers.

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
