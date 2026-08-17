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
What she currently has on hand. The thing a grocery list is subtracted against, and never inferred from what was planned.
_Avoid_: Stock, inventory, supplies

**Profile**:
The standing household facts a plan is drawn against — allergies, dislikes, household size, and targets. Hers to state, ours to remember.
_Avoid_: Preferences, settings, config

### Planning

**Plan**:
The meal entries covering a date range. Distinct from a *menu*, which is a Paprika feature this plugin does not use.
_Avoid_: Menu, schedule, calendar

**Slot**:
One `(date, meal type)` pair — the addressable position a plan fills. Breakfast, Lunch, Dinner, or Snack.
_Avoid_: Entry, cell, spot

**Swap**:
Changing what occupies a slot in a plan that already exists, as opposed to drafting a plan from empty.

### How work enters and lands

**Intake path**:
One of the ways a recipe enters the library — a URL, dictation or paste, or files. A property of how the recipe arrived, distinct from what it becomes.
_Avoid_: Import method, source type

**Reviewable batch**:
The unit a single confirmation is allowed to cover: exactly what she was just shown, never more. The floor under every write.
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

**Advisory agent**:
The nutritionist or the chef — consulted for judgement over numbers a skill already computed. Advisory agents never mutate data and never compute their own figures.
_Avoid_: Assistant, expert, advisor
