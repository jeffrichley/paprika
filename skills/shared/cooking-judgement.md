# Cooking judgement

The shared reference the skills load when they have to decide what somebody
should actually eat. It is **not an agent** — there is no nutritionist and no
chef in this plugin, because an advisor that returns an opinion is a second
judge competing with yours, arriving with nothing behind it.

This is the knowledge, held in one place so that `plan-week`, `add-recipe` and
the rest do not each grow their own slightly different version of it.

## The week is the unit

A week is what a household eats, not seven independent decisions. Judge the
shape of the whole thing:

- **Repetition is about the week, not the recipe.** Chicken twice is fine.
  Chicken twice in the same form is not. Roast chicken Monday and chicken curry
  Thursday are two different meals; two sheet-pan chicken traybakes are one meal
  cooked twice.
- **Vary what the cooking actually is.** Something braised, something roasted,
  something raw or barely cooked, something from the freezer. A week of five
  oven dishes is exhausting in a way no single dish is.
- **Vary the base.** Not five nights of potatoes, not five nights of pasta.
- **One ambitious night is a treat. Three is a punishment.** Look at total time
  and at how much of it is hands-on.

## What a fast night means

A fast night is not a lesser night. It is a different problem: **under about
thirty minutes, mostly unattended or mostly one pan**, and made of things that
are in the house or bought without a special trip.

The failure to avoid is proposing something that *looks* quick because its
stated time is short, while actually needing a marinade, a rested dough, a
soaked bean or a shopping trip. Read the ingredients, not just the time.

## What recently means

Recently is **the last two or three weeks**, and the thing to avoid repeating is
the *dish*, not the ingredient. She will notice the same dinner coming round
again long before she notices eating carrots twice.

If the library is small enough that avoiding repetition is impossible, say so
rather than silently repeating. That is a fact about her library, and she may
want to do something about it.

## Allergies are not preferences

An allergy is a hard constraint and it binds **every plate at that meal**,
because the cook only gets one pot and nobody is handed a separate dinner. Never
propose something against one. Never propose something where an obvious version
of the dish contains it and you are assuming she will leave it out.

**One pot is an argument about a meal, not about a week.** Two kinds of person
appear in the Profile and they differ only in which meals they are at:

- **Family** — they live here. Their allergies are in `always_avoid` and hold at
  every meal, with nothing to ask and nothing to work out.
- **Guests** — they come sometimes. Their allergies bind the meals they attend
  and no others. Constraining a Tuesday because somebody is coming on Sunday is
  how a real allergy ends up unrecorded, which is worse than either.

**Some allergies put more than the ingredient list in scope.** When the Profile
marks one *traces matter*, the knife, the board, the oil, the pan and the serving
spoon are part of the answer — so is cooking order, and so is anything fried in
the same fat. A recipe that never lists the ingredient can still be unsafe, and
"this one doesn't have any in it" is not the whole check.

That is a flag rather than a scale on purpose. Medicine grades these finely;
exactly one distinction changes what a cook does.

Which meals a guest is at is **hers to say**:

| | |
|---|---|
| Planning a **week** | Ask who is joining, once, before drafting. `guests_to_ask_about` is who to ask about. |
| A **single meal** | Assume family — and say so, in a clause: *"for the four of you"*. A wrong assumption she can see is one she can correct. |
| She **names** somebody | They bind that meal. Do not ask; she has answered. |
| You asked and do not know | Apply every guest's allergies. Not knowing is never a reason to relax one. |

If the allergy line is absent, that means **nobody has been asked** — it does
not mean there are none. Ask, or stay well clear.

**Nothing screens ingredients for you.** No command filters a recipe by allergy;
the list in the primer is the whole of what you are given, and reading each
recipe against it is your job on every single proposal. So the work is yours
where it is hardest: an allergy names a food, and a recipe names *products made
of* that food. Tomato means passata, ketchup, sugo, salsa, pizza sauce and tinned
chopped. Milk means butter, cream, cheese and most breads worth eating. Read the
ingredients for what they are made of, not for the word she typed.

An allergy she named that you have never heard of gets **more** care, not less.
It is recorded exactly as she said it, because a word this plugin cannot spell is
still a thing that can put somebody in hospital. When you cannot tell whether an
ingredient contains it, say so and ask — that is a scope question, and it is
always fair.

Dislikes are the opposite: advisory, per person, and worth weighing against
everything else. Somebody disliking mushrooms is a reason not to make the
mushroom thing on a night they are eating; it is not a reason to never cook
mushrooms.

## Leaving a night empty

**An empty night with an honest reason is better than a meal nobody wanted.**
This is the moment trust is earned, not a cost to be minimised.

Leave it empty when nothing in her library genuinely fits — the night is fast
and everything left is slow, or everything that fits was eaten last week, or the
only candidates run into an allergy. Say in one line why, and offer two or three
short options so the gap is a choice rather than a dead end.

Do not fill a night by lowering the bar and hoping she does not notice. She will
notice, and the next draft will be trusted less.

## Judging in one pass

Draft the week **once, properly**. Do not produce a quick draft and then improve
it — a first pass made without judgement and a second pass applying it produces
something worse than one pass made carefully, and it wastes her time twice.

Hold the whole week in mind as you go: what is already on Tuesday changes what
belongs on Wednesday.

## Say why, in her words

When a choice needs explaining, explain it as a cook would — *"Thursday's fast
so this one's a traybake"*, *"you had the chilli last week"*. Never as a system
would. There are no scores here, no percentages, no confidence, and nothing to
report about how a decision was reached beyond the reason a person would give.
