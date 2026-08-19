# Paprika

A Claude Code plugin that manages a Paprika 3 recipe library and plans meals from it, driven by a non-developer typing at Claude Code. Paprika itself stays the cooking and shopping surface; this plugin is where the library is managed and the week is planned.

## Language

### Her data

**Library**:
The full set of recipes saved in her Paprika account. Our word, not hers — never surface it in a skill name or prompt. Small enough to be read whole rather than searched — which is what makes finding something a matter of judgement rather than of matching.
_Avoid_: Collection, cookbook, recipe book

**Recipe**:
One saved dish: ingredients, method, and metadata, identified by a `uid`. Always read and written as a whole object; a recipe is never partially constructed.

**Pantry**:
What she currently has on hand, and how long ago that was last confirmed — the age is part of the fact, not metadata about it. The thing a grocery list is subtracted against, and never inferred from what was planned. Evidence may add to it or confirm it; **only she can say something is gone**, because not seeing a thing is not the same as it not being there.
_Avoid_: Stock, inventory, supplies

**Filed loosely**:
A recipe carrying only a root category when the recipes it belongs with live at a leaf. Distinct from *uncategorised*, which means no categories at all. The distinction matters because filing loosely is often deliberate, so the two are never treated as one problem.
_Avoid_: Badly categorised, misfiled, orphaned

**Profile**:
The standing household facts a plan is drawn against — allergies, targets, the people, and the household's *rhythm*: which nights are fast, which are slow, who is away. Hers to state, ours to remember. Never inferred silently; the plugin may notice and ask, and writes only on her yes.
_Avoid_: Preferences, settings, config

**Person**:
Someone the household cooks for, with their own dislikes and loves. Allergies are deliberately *not* per-person: they are household-wide, because the cook only gets one pot.
_Avoid_: User, member, eater

**Mirror**:
Our local copy of what Paprika stores. Never authoritative and never written to directly — Paprika is the truth for everything it holds, so a mirror is only ever fresh or stale, never in conflict. Refreshed, or discarded and rebuilt. Which of the two it is, is established by **asking** rather than by a clock: a mirror that merely looks recent can still be missing something she deleted.
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

**Group**:
The unit of bulk review — the recipes sharing one proposed destination, shown whole, corrected if she wants, covered by a single yes. A group is a *Draft* until she answers it, and lands as one *Run*. How a several-hundred-recipe job is made reviewable without becoming forty screens.
_Avoid_: Batch, chunk, page

**Draft**:
Proposed changes shown for correction before any confirmation is asked. A draft has not touched her data.
_Avoid_: Preview, dry run, staged

**Run**:
One write operation from start to finish — a single edit or three hundred re-filings. The unit that gets verified, notified, and undone. A run that stops partway is still one run, and is reported as one.
_Avoid_: Batch, job, transaction

**Pre-image**:
The whole object exactly as it stood immediately before we wrote to it, captured on every write. Whole, never a diff — only a whole object can be restored, because every write is a full-object write. What an undo replays.
_Avoid_: Backup, snapshot diff, version

**Trashed**:
What she means by deleting a recipe: it goes to the Paprika app's own trash, where she can see and restore it herself. Distinct from *removed*, which takes an object out of Paprika altogether and leaves her no recovery path but ours. Trashed recipes still sync — her other devices have to render their own trash — so the mirror filters them rather than expecting them to be gone.
_Avoid_: Deleted, archived, hidden

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
Knowing what goes with what, what a household will actually eat, and what makes a week work as a week. Shared across the skills that need it — and the one agent — rather than owned by any of them, and never a thing she summons by name. Replaces the "nutritionist" and "chef" agents, which the plugin does not have.
_Avoid_: The chef, advisory agent, assistant, expert

**Scan**:
The read-only pass over the whole library that clusters recipes and finds duplicates, and the plugin's only agent. It proposes and never writes — it holds no write tool — so everything it produces is a Draft that a skill turns into a Run on her yes.
_Avoid_: The cleanup agent, the organiser, the bot
