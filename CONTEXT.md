# Paprika

A Claude Code plugin that manages a Paprika 3 recipe library and plans meals from it, driven by a non-developer typing at Claude Code. Paprika itself stays the cooking and shopping surface; this plugin is where the library is managed and the week is planned.

## Language

### Her data

**Library**:
The full set of recipes saved in her Paprika account. Our word, not hers — never surface it in a skill name or prompt.
_Avoid_: Collection, cookbook, recipe book

**Recipe**:
One saved dish: ingredients, method, and metadata, identified by a `uid`. Always read and written as a whole object; a recipe is never partially constructed.

**Pantry**:
What she currently has on hand, and how long ago that was last confirmed — the age is part of the fact, not metadata about it. The thing a grocery list is subtracted against, and never inferred from what was planned. Evidence may add to it or confirm it; **only she can say something is gone**, because not seeing a thing is not the same as it not being there.
_Avoid_: Stock, inventory, supplies

**Profile**:
The standing household facts a plan is drawn against — allergies, targets, the people, and the household's *rhythm*: which nights are fast, which are slow, who is away. Hers to state, ours to remember. Never inferred silently; the plugin may notice and ask, and writes only on her yes.
_Avoid_: Preferences, settings, config

**Person**:
Someone the household cooks for, with their own dislikes and loves. Allergies are deliberately *not* per-person: they are household-wide, because the cook only gets one pot.
_Avoid_: User, member, eater

**Mirror**:
Our local copy of what Paprika stores. Never authoritative and never written to directly — Paprika is the truth for everything it holds, so a mirror is only ever fresh or stale, never in conflict. Refreshed, or discarded and rebuilt.
_Avoid_: Cache, local database, sync state

### Planning

**Plan**:
The meal entries covering a date range. Distinct from a *menu*, which is a Paprika feature this plugin does not use.
_Avoid_: Menu, schedule, calendar

**Slot**:
One `(date, meal type)` pair — the addressable position a plan fills. Breakfast, Lunch, Dinner, or Snack.
_Avoid_: Entry, cell, spot

**Swap**:
Changing what occupies a slot, whether or not the plan has been saved yet. Correcting a draft and changing a saved plan are the same gesture to her; the distinction that matters is *Draft* versus saved, which is about whether her data has moved.
_Avoid_: Replace, reschedule, edit

### How work enters and lands

**Intake path**:
One of the ways a recipe enters the library — a URL, dictation or paste, files, or *invented*. A property of how the recipe arrived, distinct from what it becomes. Invented is the only path whose source is us, so it is the only one that marks the saved recipe permanently and the only one that must render the recipe whole before asking to save it.
_Avoid_: Import method, source type

**Reviewable batch**:
The unit a single confirmation is allowed to cover: exactly what she was just shown, never more. The floor under every write. The measure is *shown*, not *few* — eighty ingredient names she can scan are one batch; forty recipes she would have to read are not.
_Avoid_: Bulk operation, batch job

**Draft**:
Proposed changes shown for correction before any confirmation is asked. A draft has not touched her data.
_Avoid_: Preview, dry run, staged

### Nutrition

**Provenance**:
The labelled origin of a nutrition number and how far it can be trusted — which tier it came from. Derived only from structural evidence we can check ourselves, never from a matcher's self-reported score. Mandatory on every number; a total inherits the provenance of its worst ingredient.
_Avoid_: Source, confidence, quality

**Tier**:
One of the four grades a provenance can take: Measured, Derived, Estimated, Unquantified. A tier decides whether a number renders as a plain value, a range, or not at all. Internal vocabulary — the tier itself is never shown to her.
_Avoid_: Confidence score, accuracy rating, grade

**Rollup**:
Nutrition totalled across a week rather than a single recipe. Computed on request, never journaled and never volunteered alongside a plan.
_Avoid_: Summary, aggregate, daily total

### Who acts

**Skill**:
A capability she invokes, by name or in plain English. Skills are the only things that write.

**Cooking judgement**:
Knowing what goes with what, what a household will actually eat, and what makes a week work as a week. Shared across the skills that need it rather than owned by one, and never a thing she summons by name. Replaces the "nutritionist" and "chef" agents, which the plugin does not have.
_Avoid_: The chef, advisory agent, assistant, expert
