# PROTOTYPE — a week-planning conversation

> **Throwaway.** Written to answer [#16](https://github.com/jeffrichley/paprika/issues/16) on map
> [#3](https://github.com/jeffrichley/paprika/issues/3). Not a spec, not a script, not code. It exists
> to be reacted to and then thrown away; the decisions it settles live in the ticket's resolution.
>
> Everything here is invented — the recipes, the household, the numbers. The only things that are
> *not* invented are the behaviours, which are drawn from the closed tickets: the skill roster and its
> five rules (#10), the primer and its four facts (#11), nutrition rendering (#12), the store (#13),
> cooking judgement and the invented intake path (#15).

---

## How to read this

| Marker | Meaning |
| --- | --- |
| **Her** / **Claude** | What is actually on screen. |
| `⟨ … ⟩` | Machinery she never sees — hook injection, which skill fired, what went over the wire. |
| ▸ **What changed** | State after a write. Nothing is written except where one of these appears. |

**Today is Monday 17 August 2026.** The household is her, Jeff, and two kids — **Ellie** (11) and
**Max** (7). Names are stand-ins.

---

## Session open

```
⟨ SessionStart hook (matcher: startup|clear|compact) injects skills/using-paprika/SKILL.md,
  ~27 lines, inside one <EXTREMELY_IMPORTANT> block. She sees none of it. ⟩

  Paprika state
    Setup: complete.
    Plan for Mon 24 Aug–Sun 30 Aug: none.
    Pantry last checked 9 days ago.
    Allergies: peanuts, shellfish.
```

Two of those four facts do real work below. Watch the shellfish line and the nine days.

---

## 1. The opening request

> **Her:** can you plan our dinners for next week

```
⟨ routes to /paprika:plan-week. She did not type a skill name and will not type one all session. ⟩
```

> **Claude:**
>
> Next week — **Monday 24 to Sunday 30 August**, dinners only. Say so if you meant a different week.
>
> Here's a draft. Nothing is saved yet.
>
> | | |
> | --- | --- |
> | **Mon 24** | Sheet-pan chicken thighs, lemon and potatoes |
> | **Tue 25** | Black bean and sweet potato tacos |
> | **Wed 26** | Beef and broccoli with rice |
> | **Thu 27** | Baked ziti |
> | **Fri 28** | *— empty, see below* |
> | **Sat 29** | Slow-cooker pulled pork with slaw |
> | **Sun 30** | Lentil soup and soda bread |
>
> Sunday is deliberately a nothing-dish — Saturday's pork takes the whole afternoon and you don't
> usually want two of those in a row.
>
> **Friday I left empty.** You tend to want Friday fast, and everything fast in your recipes is either
> shellfish or a repeat of Tuesday. I can make something up, or go looking properly — or you can tell
> me what you had in mind.

**What just happened, and what didn't.** It never asked *which week* — it stated the week and drafted
against it, so a wrong guess costs her one word instead of a round trip (#10 rule 1: ask scope, draft
content). It never asked what she felt like eating. It did not fill Friday with something plausible.
It did not offer nutrition numbers.

---

## 2. She corrects the draft

> **Her:** we had ziti like two weeks ago. something else thursday

> **Claude:**
>
> Swapping Thursday for **turkey meatballs with orzo** — quicker than the ziti anyway.
>
> That's it changed: **Thu 27 — turkey meatballs with orzo.** Still nothing saved.

No re-display of all seven, because one line changed and she is looking at the table. The full
re-display is owed at the confirmation, not here.

---

## 3. Friday: the slot her library cannot fill

> **Her:** ok. friday just make something up

> **Claude:**
>
> **Crispy gochujang tofu with quick cucumber salad** — about 25 minutes, one sheet pan and a bowl.
>
> Worth being clear: **I made this up.** Nobody has cooked it, including me. I can put it on Friday as
> just a name, or save it into your recipes properly — if I save it, it gets marked
> `Created with Claude — 17 Aug 2026` so a year from now it isn't mistaken for one you found.

> **Her:** save it, sure

> **Claude:**
>
> Before I do — here it is in full, since "save it" should mean you've seen it.
>
> **Crispy gochujang tofu with cucumber salad** · 25 min · serves 4
>
> - 400 g firm tofu, pressed and cubed
> - 2 tbsp cornstarch
> - 2 tbsp gochujang
> - 1 tbsp honey · 1 tbsp soy sauce · 2 tsp rice vinegar · 2 cloves garlic, grated
> - 1 large cucumber, smashed · pinch of salt · 1 tsp sesame oil
> - rice, to serve
>
> 1. Heat oven to 220°C. Toss the tofu in cornstarch and a little oil, spread on a sheet pan, roast
>    20 min, turning once.
> 2. Whisk gochujang, honey, soy, vinegar and garlic.
> 3. Smash the cucumber, salt it, drain 10 min, dress with vinegar and sesame oil.
> 4. Toss the hot tofu in the sauce. Serve over rice with the cucumber alongside.
>
> No photo — it doesn't have one and I'm not going to give it a fake one.
>
> Save this to your recipes?

> **Her:** yeah

▸ **What changed** — one recipe created in Paprika.
`source = "Created with Claude — 17 Aug 2026"`, `photo = null`, no category yet.
Written as a full object; nothing else in the library touched.

```
⟨ This is /paprika:add-recipe's invented intake path, fired from inside plan-week. ⟩
```

---

## 4. Saving the week

> **Her:** ok save the week

> **Claude:**
>
> Here's the whole thing as it now stands — this is exactly what I'll save:
>
> | | |
> | --- | --- |
> | **Mon 24** | Sheet-pan chicken thighs, lemon and potatoes |
> | **Tue 25** | Black bean and sweet potato tacos |
> | **Wed 26** | Beef and broccoli with rice |
> | **Thu 27** | Turkey meatballs with orzo |
> | **Fri 28** | Crispy gochujang tofu with cucumber salad |
> | **Sat 29** | Slow-cooker pulled pork with slaw |
> | **Sun 30** | Lentil soup and soda bread |
>
> Save these seven dinners to Paprika?

> **Her:** yes

The re-display is not politeness — it is the confirmation floor (#10 rule 2). The plan changed twice
since she last saw it whole, so a yes against the *first* table would have covered two things she
never approved.

---

## 5. The write goes partly wrong

```
⟨ 7 × POST to the meals resource: date, type=2 (Dinner), recipe_uid.
  Six come back clean. The seventh returns HTTP 200 with {"error": …} in the body. ⟩
```

> **Claude:**
>
> **Six of the seven saved.** Wednesday — beef and broccoli — didn't go through, and I don't have a
> reason for it; Paprika took the other six without complaint.
>
> Your recipes are untouched: this only writes the plan, so nothing was edited, and nothing was
> deleted. Wednesday is simply empty in Paprika right now.
>
> Try Wednesday again?

> **Her:** yeah try again

> **Claude:** Done — Wednesday's in. All seven dinners are on your phone.

▸ **What changed** — seven meal entries for 24–30 Aug. Recipes and categories unchanged.

The three sentences are #10 rule 4 in order: what she was doing, what didn't happen, **whether her
library changed**. The third one is the one that decides whether she dares retry.

---

## 6. The grocery list, and the nine-day-old pantry

> **Claude:** Want the grocery list for it?

> **Her:** yes please

```
⟨ /paprika:grocery-list — asks nothing about scope, the plan already fixed it. ⟩
```

> **Claude:**
>
> **Grocery list, Mon 24 – Sun 30** — 23 items.
>
> **Produce** — 2 lemons · 3 lb potatoes · 2 sweet potatoes · 1 head broccoli · 1 large cucumber ·
> 1 bag slaw mix · 2 onions · garlic · parsley
> **Meat** — 3 lb chicken thighs · 1 lb flank steak · 1 lb ground turkey · 4 lb pork shoulder
> **Dairy** — feta · parmesan
> **Pantry** — black beans · gochujang · honey · rice vinegar · sesame oil · dried lentils ·
> orzo · corn tortillas
>
> Nine more things are in the recipes but not on this list, because your pantry says you already have
> them: **rice, olive oil, soy sauce, cumin, cornstarch, canned tomatoes, brown sugar, flour, baking
> soda**. That reading is nine days old, so it's the part of this list most likely to be wrong.
>
> Want to run through those nine before I send it?

> **Her:** ugh yes. we're out of tortillas and feta i think

> **Claude:**
>
> Tortillas and feta are already **on** the list — you're covered there.
>
> The nine I left off: rice, olive oil, soy sauce, cumin, cornstarch, canned tomatoes, brown sugar,
> flour, baking soda. Any of those actually gone?

> **Her:** rice for sure. and i think the soy sauce is nearly empty

> **Claude:**
>
> Adding **rice** and **soy sauce**. Marking the other seven as checked today, so this stops being a
> nine-day-old guess.
>
> **25 items.** Send to Paprika?

> **Her:** yes

▸ **What changed** — 25 grocery items created in Paprika. Pantry timestamp reset to today; seven
items confirmed present, two removed.

---

## 7. Something Claude noticed

> **Claude:**
>
> One other thing. Fish has come off the plan three weeks running — I've been leaving it out on the
> assumption that's not an accident. Is that a real thing I should remember, or a coincidence?

> **Her:** yeah ellie won't touch it

> **Claude:** Noted — **Ellie: no fish.** That's the only thing I've written down about her.

▸ **What changed** — `profile.toml`, people table: `Ellie.dislikes = ["fish"]`. Comments preserved.
Nothing else in the Profile touched.

It noticed, it asked, it wrote nothing until she said yes — the confirmation floor applying one level
up, to a Profile write rather than a library write (#15). The alternative, silently learning it, forms
an opinion about her daughter that she never agreed to and cannot see.

---

## 8. She asks about nutrition — and only then

> **Her:** is that week ok on protein?

```
⟨ /paprika:nutrition. First time numbers appear in the entire session. ⟩
```

> **Claude:**
>
> Across the seven dinners: **660–890 g of protein for the week**, which is roughly **95–125 g a day**
> if you spread it evenly — though you won't, since Tuesday's tacos are the lightest night by a
> distance and Saturday's pork the heaviest.
>
> Your profile says you're pushing protein up. **This week points that way.** I can't tell you by how
> much — the width of that range is bigger than the difference you'd be measuring.
>
> The number that moves this most is the **pulled pork**: the recipe says "pork shoulder, 4–5 lb" and
> never says bone-in or boneless, which is a bigger swing than everything else in the week combined.
>
> Two ingredients I couldn't match to anything and left out entirely: *adobo sauce* and *everything
> bagel seasoning*. Both small.

> **Her:** fine. thanks

No goal-minus-total. No letter grades, no "confidence: 0.82", no per-day verdicts. A range everywhere
except where nothing could be said at all, one named weakest input, and the unmatched ingredients
said out loud rather than quietly dropped (#12).

---

## What landed in Paprika, in total

| Thing | Count | When |
| --- | --- | --- |
| Recipe created (invented, marked) | 1 | §3, on an explicit yes |
| Meal entries, 24–30 Aug | 7 | §4–5, on an explicit yes, one retried |
| Grocery items | 25 | §6, on an explicit yes |
| Recipes edited or deleted | **0** | — |
| Categories created | **0** | — |

Four writes, four explicit yeses, and every yes covered exactly what had just been on screen.

**Words she never saw:** uid, hash, sync, token, API, cache, JSON, tier, provenance, request, 200,
library. **Tracebacks:** none, including on the write that failed.

---

## What this exposed

The point of the transcript. Nine things surfaced; the first five want a decision.

**1. `plan-week` states scope, it does not ask it.** #10 says it "asks the one scoping question" and
also that it "states the dates it chose in its first line." Written out, those are different skills.
The transcript picks *state and draft* — it is strictly better under rule 1, since the week is
inferable and a wrong guess costs one word. If that is right, #10's wording should be corrected.

**2. Correcting a draft is not a Swap.** `CONTEXT.md` defines **Swap** as changing what occupies a
slot in a plan *that already exists*. Sections 2 and 3 are neither drafting from empty nor swapping —
they are a correction loop over something unsaved, and they are where most of the conversation lives.
Either Swap widens to cover it or the loop needs its own name and its own contract.

**3. The confirmation floor bites harder on invented recipes than expected.** She said "save it, sure"
about a *name*. Rule 2 means the yes cannot cover more than was shown, so the full recipe had to be
rendered before the real ask — which reads as Claude second-guessing her, and is still right. The
invented intake path should carry this explicitly: **an invented dish is rendered whole before the
save is offered.**

**4. `plan-week` called `add-recipe` mid-flow.** Saving the invented Friday dish is `add-recipe`'s job,
happening inside `plan-week`'s conversation. Do skills invoke each other, or does the core expose a
save that both use? This is a direct constraint on [#20](https://github.com/jeffrichley/paprika/issues/20).

**5. A stale pantry versus "`grocery-list` asks nothing."** The transcript resolves it by building the
list anyway and naming the nine subtractions it is least sure about — scope was never in question, so
rule 1 holds, and the check is offered rather than demanded. The alternative is a hard rule with a
number in it ("past N days, stop subtracting"). Rendered, the offered check reads better and needs no
number, but it does mean **every** grocery list carries a paragraph about what it left off.

**6. "Whether her library changed" needed a distinction the rule does not make.** In §5 the plan
changed and the recipes did not, and the sentence that mattered was the one separating them. Rule 4
says "library"; the transcript needed *plan* and *recipes* as two different nouns. Hands
[#17](https://github.com/jeffrichley/paprika/issues/17) a requirement: a write report has to say which
kind of thing moved.

**7. The empty Friday held — but it needed a fact with no home.** Leaving the slot empty worked because
the reason was one sentence and the options were three words each. But it rested on *she wants Friday
fast* — a household rhythm fact. That is not an allergy, not a target, not a person's dislike, so
`profile.toml` as specified in #13 has nowhere to put it. Either the Profile grows a fourth kind of
fact, or cooking judgement is re-deriving this from the plan history every time.

**8. The injected facts earned their place.** Two of the four (shellfish, nine days) directly changed
what happened. Neither was quoted at her.

**9. She typed no skill name, all session.** Ten skills, three of them fired, zero named. Worth
knowing when weighing what `/paprika:help` is for.
