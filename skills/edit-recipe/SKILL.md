---
name: edit-recipe
description: Use when the user wants to change something about a recipe they already have — a serving size, an ingredient, a time, a note, a rating — or wants to fill in something that was left blank or unreadable.
---

# Changing one thing

She describes a change and it happens. **Nothing else about the recipe moves.**

That is not a nicety. This is the operation that, in a shipping tool people
actually used, wiped the rating, the categories, the source, the nutrition notes
and the photos off a recipe on **every single edit** — and pushed the damage to
every device she owned. Her library is a decade of work. Treat an edit as
something that can destroy it, because in the wrong shape it is.

## Find it, show the change, then make it

1. **`paprika recipe index`** and read it, or `paprika recipe search` if she has
   described an ingredient rather than a title. `/paprika:find-recipe` is the
   longer version of this if she is vague.
2. **`paprika recipe get <handle>`** to see what is actually there now.
3. **Show her the change before making it** — the old value and the new one, not
   the whole recipe. When the value is free text, that means **both of them
   whole**: every line of the old notes and every line of the new. Narrow is
   about which fields, never about how much of one she gets to read.
4. **Make it on her yes.**

> **Nana's Soda Bread** — servings: `8` → `12`. Change it?

## Making it

```bash
paprika write recipe set <handle> --set "servings=12" --done
```

Name **only** the fields she asked to change. Everything else is carried over
untouched by the write itself, and naming a field you were not asked about is
how a small edit becomes a big one.

For categories, `--add` and `--remove` work on the list:

```bash
paprika write recipe set <handle> --add "categories=Bread" --done
```

## What you may not change

Some things are not editable by name and asking for them is refused: how the
recipe is identified, anything about how it syncs, and whether it is in the
trash. **Trashing is `paprika write recipe trash`**, which puts it in Paprika's
own trash where she can get it back herself.

## Giving one a picture

**A recipe that has none** takes one from a file she names:

```bash
paprika write recipe photo <handle> --file "<path>"
```

What goes up is a square thumbnail, which is what the recipe object itself
carries. It is not the full-size gallery picture — that is a different thing and
the plugin cannot set it, so say "a thumbnail" rather than implying otherwise.

**A recipe that already has one is refused**, and the refusal is the true reason:
swapping a picture could not be undone, because what was there before cannot be
kept. Tell her to take the old one off in Paprika first. Do not offer to work
around it.

## Filling in a gap

A recipe read from a photo or a page may carry a marker in its own text where a
line could not be read. It sits in the ingredients or the method, in her recipe,
so she can see it in the kitchen with the book open.

Replacing it is an ordinary edit: read the field, replace the marked line, write
the field back whole. Keep every other line exactly as it is — you are replacing
one line, not retyping the list.

## Rules that do not bend

- **Only the fields she named.** Never "while I was in there".
- **Show the change before making it**, old and new.
- **Never rewrite her wording** in a field you were not asked to change.
- **Never guess at a value** to fill a blank she has not mentioned. Blank means
  the source did not say.
- **If she wants it gone, that is trash**, and say it is recoverable in her app.

## When you are about to break one of those

| The thought | What is actually true |
|---|---|
| "The ingredients are messy, I'll tidy them while I'm here" | She cooks from those words. Change what she named. |
| "The prep time is obviously about 15 minutes" | Blank means the source didn't say. A guess looks like a fact. |
| "Sending the whole recipe back is safer" | The write already carries everything. Naming extra fields is the risk, not the safety. |
| "She said delete it" | Trash it. She can undo that herself, in her own app. |
| "It's one small formatting fix" | This is the operation that wiped five fields off every recipe in a shipping tool. |

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Tidying the ingredients while changing the servings | Change what she named |
| Showing the whole recipe back to confirm one field | Old value → new value |
| "I also filled in the prep time for you" | Blank means the source didn't say |
| Retyping the ingredient list to fix one line | Replace the line, keep the rest |
| Deleting a recipe outright | Trash it; she can undo that herself |
