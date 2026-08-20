---
name: find-recipe
description: Use when the user is trying to find a recipe they think they already have, describes a dish vaguely or from memory, asks what they could cook with something, or asks whether they have a recipe for a particular thing.
---

# Finding a recipe she already has

She describes something half-remembered — *"that chicken thing with the lemons"* —
and gets it back. Her own recipes are tried first, always, and the internet only
if she says so.

## Why there is no search engine here

**You are the search.** Her library is small enough to read: one line per recipe,
about sixteen tokens each, so the whole thing costs roughly eight thousand.

Read it. Recognise what she means. Nothing is matching strings, which is why a
misspelling simply dissolves — you are reading `Mediterranean Chicken` and
recognising it, not correcting her spelling of it.

There is no similarity score anywhere in this plugin, and you must not invent
one. A number that says *87% match* is a second opinion competing with your own,
arriving with nothing behind it and no way to show her why it thought so.

## How to do it

1. **`paprika recipe index`** — the whole library, one line per recipe: handle,
   name, categories, rating, total time.
2. **Read it and shortlist.** Usually a handful. Judge on names and her own
   categories.
3. **`paprika recipe get <handle> <handle> …`** for the shortlist, in one call,
   when the question needs more than a title — *"not too spicy"* needs the
   ingredients.
4. **Answer.** One recipe if it is obvious; a short list if it genuinely isn't.

The index deliberately carries no ingredients. When the question is
ingredient-shaped across the whole library — *"anything with tahini?"* —
use **`paprika recipe search tahini`**, which looks through the text of every
recipe without fetching any of them. It matches words literally, so try the word
she would have typed into her own recipe.

## When it isn't there

Say so plainly, and **ask before going to the internet.** Her library first is
not a preference, it is the point.

> I can't see anything like that in your recipes. Want me to look online?

Only search the web on a yes.

## Two rules about anything found online

**Never blend it with hers.** A web result and one of her recipes must never
appear in the same list, be compared field by field, or be merged into a third
thing she did not write. Show hers, or show the web one, and say which is which
every time.

**Nothing is saved without an explicit yes covering exactly what you showed
her.** Not "shall I save these", not a yes she gave to something else a moment
ago. Render the one recipe, ask about that one recipe, save on that answer. If
she wants three of them, that is three questions or one question naming all
three — and browsing must never leave a mark on her library.

Saving is `/paprika:add-recipe`'s job, not this skill's.

## Rules that do not bend

- **Her library before the internet, every time.** Even when the request sounds
  like it obviously isn't in there.
- **Never invent a score, a percentage or a ranking number.** Say why you think
  it is the one, in words, or say you are not sure.
- **Never say a recipe is hers when it came from the web**, or the reverse.
- **A vague description is not a reason to ask her to be precise.** Read the
  library and make a judgement. Ask only when two recipes genuinely both fit.
- **Show a handle only when she needs one to point at something.** It is how you
  name a recipe to the program, not how she names it to you.

## When you are about to break one of those

| The thought | What is actually true |
|---|---|
| "That's clearly not in her library" | Read the index. It costs almost nothing and you are often wrong. |
| "I'll show hers and a web one so she can compare" | Two separate answers, each labelled. Never one list. |
| "This web version is better, I'll combine the best bits" | That is a third recipe she never wrote. |
| "She seemed happy with it, I'll save it" | An explicit yes, covering what you showed her. |
| "Saying 90% match is helpful precision" | It is a number with nothing behind it. Say why, in words. |

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Asking her to spell it correctly | Read the library; the misspelling stops mattering |
| Going to the web because the wording was odd | Try her library first, always |
| Pulling every recipe body | Shortlist from the index, then pull a handful |
| Showing a web result beside hers in one list | Two separate answers, each labelled |
| Saving because she sounded pleased | An explicit yes, covering what you showed |
| Reporting a match percentage | Say what makes you think so, in words |
