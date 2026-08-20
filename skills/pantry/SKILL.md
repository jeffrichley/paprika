---
name: pantry
description: Use when the user says what they have bought or brought home, sends or points at a photo of a shelf, cupboard or fridge, mentions running out of something, wants to check or update what is in the house, or asks what they already have before shopping.
---

# What's in the house

Two jobs: **after a shop**, she says what she bought and it all goes in at once.
**Between shops**, a short conversation keeps it honest.

## The rule everything else follows from

**A camera can say "this is here". Only she can say "this is gone".**

Something not mentioned is not something she has run out of. The jar is behind
the cereal. So this only ever *adds* and *confirms* — nothing is removed because
it went unmentioned, because a day it was planned for has passed, or because a
photo did not show it.

The fix for a stale item is **to ask about it**, never to work it out.

## After a shop

She says what she bought, however she says it. Take the names — not the
quantities, not the brands, not the sizes.

Show her the list grouped by aisle so she can scan it, and ask **once**:

> That's 23 things — cans and jars: black beans, chopped tomatoes, coconut milk…
> Produce: onions, garlic, lemons… Look right?

**Eighty names is one legitimate yes**, and it should be. She can read eighty
words in ten seconds. Do not split it into several confirmations, and do not ask
about them one at a time.

On her yes:

```bash
paprika write pantry add "black beans" "chopped tomatoes" onions --done
```

## Between shops

Ask about a handful at a time, and keep it short. Good things to ask about: what
a plan is about to need, and what has been sitting there a long time.

> Quick check — still got rice, cumin and the fish sauce?

Then record what she actually said:

```bash
paprika write pantry confirm rice cumin
paprika write pantry gone "fish sauce" --done
```

**Do not ask about everything.** A dozen questions to tidy a list is a chore she
will not do twice.

## A photo of a shelf

**A photo is evidence, not a mode.** Accept one anywhere what-she-has is in
question — including in the middle of a shopping list, where a picture is the
fastest possible answer to *"are any of those nine actually gone?"*

There is nothing to set up and nowhere to put an image. She sends it, or she
points at where it is. If she **pasted** it, read it here — it is already in
front of you. If she **named a path or a folder**, dispatch the Reader; that
file has not been opened yet and should not be opened here.

### An image that arrives with no words

Say what you think it is in the **opening line**, then draft against it. The
draft is the verification — she will correct a wrong guess instantly.

> Looks like a spice shelf. I can see: cumin, smoked paprika, turmeric, dried
> oregano, bay leaves…

Only ask first when it is a genuine coin-flip — a photo that could as easily be
a shopping receipt as a cupboard.

### What goes in the list, and what goes in the question

**A legible label goes in the list.** You can read the jar; that is evidence.

**A guess at a shape or a colour goes in the closing question, never the list.**
*"There's a green tin at the back I can't read — is that the fennel?"* A guess
promoted into the list becomes a fact nobody checked.

### What you could not see

**A camera can say "this is here". It cannot say anything is gone.** The jar is
behind the cereal.

So the photo only ever **adds and confirms**. At the end — once, at the
confirmation, not per photo — ask about the rest:

```bash
paprika pantry unseen cumin "smoked paprika" turmeric
```

> I didn't see these five — still there? Rice, fish sauce, cornflour, honey, bay
> leaves.

**The unit is the conversational turn, not the photo.** If she sends a second
picture — *"here's the other cupboard"* — that extends the same draft. Merge-only
makes that free. Asking after the first photo about things that are in the
second is how this becomes annoying.

### When you cannot read it

**Say what you could and could not see.** A short list that poses as a complete
one is worse than an admission.

> I could only make out the front row — there's a second row behind it I can't
> read.

**Nothing legible at all is a plain sentence, not an empty draft.**

> I can't make anything out in that one, sorry — too dark to read the labels.

### No mark

Do not record where this came from. The content is her shelf; we only looked at
it. That is different from a recipe we invented.

## Quantities, dates and sizes

**Names only.** Do not record how much, what size, or when it was bought.

What is stored is whether she has a thing, because that is the only part
anything uses, and her own words are already binary — *"the soy sauce is nearly
empty"* means take it off the list. "Two tins of black beans" is a number that
is wrong within a week and that nothing ever reads.

## How old the belief is

Every read tells you how many days since she last confirmed anything.

- **Fresh** — say nothing about it. A working feature should not narrate itself.
- **More than about a week** — say what you are assuming, so a stale assumption
  is visible rather than hidden. *"Going on what you had a fortnight ago…"*
- **Never confirmed** — that is not the same as *empty* and not the same as
  *today*. Say you do not know yet.

## Rules that do not bend

- **Mark something gone only when she has said it is gone**, in words, in this
  conversation. Not from a photo, not from a plan, not from an inference.
- **Never invent a quantity, a size or a date.** A photo shows six tins; it
  cannot show that two are out of date.
- **Never put a guess in the list.** Guesses go in the closing question.
- **Never ask about unseen items more than once**, and never before she has
  finished sending pictures.
- **Never ask about more than a handful at a time** in a check.
- **Never split one shop into several confirmations.**
- **Never say she has something without saying how old that is**, once it is more
  than about a week old.

## When you are about to break one of those

| The thought | What is actually true |
|---|---|
| "She didn't mention the rice, so it must be gone" | She mentioned what she bought. Absence is not evidence. |
| "The photo clearly shows no cumin" | It shows one shelf. The jar is behind the cereal. |
| "The plan used the last of it on Tuesday" | She may not have cooked it, or not all of it. Ask. |
| "Recording the size makes it more useful" | Nothing reads the size, and it's wrong within a week. |
| "I'll just check all forty with her" | She'll do that once and never again. A handful. |

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Removing what she didn't mention | Only she says gone; ask if you're unsure |
| "How many did you get?" | Names only |
| Twelve yes/no questions | A handful, or one grouped list |
| Splitting a shop into batches | One list grouped by aisle, one yes |
| Announcing the pantry is fresh | Say nothing when it is |
| Removing what a photo didn't show | It shows one shelf; ask at the end |
| "2 cans of black beans" from a photo | Names only |
| Asking about unseen items after each picture | Once, at the confirmation |
| Treating never-confirmed as empty | Say you don't know yet |
