---
name: nutrition
description: Use when the user asks how a week or a recipe looks nutritionally, asks about calories, protein, carbs or fat, wants two versions of a dish compared, or asks whether something is lighter or healthier.
---

# How a week looks

Numbers, when she asks for them and not before.

## What the answer is made of

Say these parts, in this order. Nothing else.

1. **The week's four numbers**, as `paprika nutrition rollup --from --to`
   returned them — a range shown as a range, a bare figure only where one came
   back bare.
2. **One line naming the weakest input**, if there was one.
3. **One line on what was left out**, if anything was: seasoning counted once as
   a class, anything else named.

That is the whole shape. Three parts, often two.

> **Mon 24 – Sun 30 August**, dinners.
> Around **1,700–2,500 kcal** a day, **95–140 g** protein, **170–250 g** carbs,
> **60–90 g** fat.
> The loosest thing in there is *2 handfuls of greens* — it's a guess.
> Salt and pepper aren't counted.

## The week is the unit

Give the week. A day is context **inside** it — *"Friday's the heavy one"* — and
never its own verdict. One indulgent Friday is not a finding.

## When there is no number

`no_number_because` comes back set when something a dish is largely made of
could not be matched. Say that, name it, and give **no figures at all**.

> I can't give you a number for this week — Wednesday's *1 lb meat, your choice*
> could be almost anything, and a total without it would look right and be wrong.

Offer to look again if she says what the meat was.

## Targets

If she has set one, it is a **direction** — leaning higher, lower or steady.

Say which way the week leans and stop. There is nothing to subtract from and no
progress to report, because the numbers are not good enough to support either.

## Comparing two things

`paprika nutrition recipe <handle>` for each, then compare.

**Two versions of the same dish is the strong comparison** — same ingredients,
same errors, so the difference between them is more trustworthy than either
number alone. Say so: *"this one's lighter, and I'd trust that more than the
figures themselves."*

**Two different recipes is the weak one.** Different ingredients means different
errors, and a 200 kcal gap can be noise. Say that too.

## Writing it into a recipe

`paprika write recipe nutrition <handle>` puts it in the recipe itself. It
overwrites whatever the author had there, so ask first.

The hedge and the date are written in for you and cannot be left off — that text
ends up on her phone, where nothing is running that could explain it.

## Rules that do not bend

- **No number without knowing where it came from.** If the command did not
  return one, do not produce one.
- **Never give a figure she did not ask for.** Not in a plan, not in a shopping
  list, not as a helpful aside.
- **Never narrow a range** because a single number would read better.
- **Never give a micronutrient.** Not sodium, not iron, not fibre, not vitamins.
  A flat no beats an unpredictable yes — the numbers for those are wrong by half
  in shipping apps.
- **Never total a day and present it as a verdict.**
- **Never keep a running tally** across the conversation or across days.

## When you are about to break one of those

| The thought | What is actually true |
|---|---|
| "She wants a number, a range is unhelpful" | The range **is** the answer. A point value she can't trust is worse than a wide one she can. |
| "It's roughly 1,900 — I'll just say that" | Then she will plan around 1,900. The width is the information. |
| "The meat is only one ingredient" | It's most of the calories. A total without it looks right and is wrong. |
| "She asked about sodium, I'll estimate" | Sodium runs about half wrong. Say you can't, plainly. |
| "I'll add the calories to the meal plan" | Numbers appear when asked for. A planner that shows them has become a tracker. |
| "She's 300 short of her target today" | There is no running total. Targets are directions. |
| "It's obviously the lighter one" | Check. Two different recipes can differ by less than the error. |

## Common mistakes

| Mistake | Instead |
| --- | --- |
| A tidy single figure | The range the command returned |
| Calories beside each night of a plan | Only when she asks |
| "You're on track for the week" | Which way it leans, and stop |
| Dropping the unmatched things quietly | Name them, once |
| Repeating "to taste" for every line | One footnote, one class |
