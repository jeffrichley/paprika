---
name: pantry
description: Use when the user says what they have bought or brought home, mentions running out of something, wants to check or update what is in the house, or asks what they already have before shopping.
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

- **Never mark something gone unless she said so.** Not from a photo, not from a
  plan, not from an inference.
- **Never invent a quantity, a size or a date.**
- **Never ask about more than a handful at a time** in a check.
- **Never split one shop into several confirmations.**
- **Never say she has something without saying how old that is**, once it is more
  than about a week old.

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Removing what she didn't mention | Only she says gone; ask if you're unsure |
| "How many did you get?" | Names only |
| Twelve yes/no questions | A handful, or one grouped list |
| Splitting a shop into batches | One list grouped by aisle, one yes |
| Announcing the pantry is fresh | Say nothing when it is |
| Treating never-confirmed as empty | Say you don't know yet |
