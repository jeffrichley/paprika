# Writing a skill for this plugin

What the audit in [#67](https://github.com/jeffrichley/paprika/issues/67) found,
so the next skill starts from it rather than rediscovering it.

**Read `superpowers:writing-skills` before writing or editing one.** Not from
memory — the first ten skills here were written from a single reading and drifted
in four measurable ways, all listed below. This file is the local supplement, not
a replacement.

## The one departure this project makes

`superpowers:writing-skills` mandates RED-GREEN-REFACTOR: pressure-test a skill
against subagents, watch it fail without the skill, watch it comply with it.

**That is out of scope here, by project decision.**
[#29](https://github.com/jeffrichley/paprika/issues/29) says so directly:

> Model behaviour is not unit-tested. […] **Do not build an eval harness that
> poses as a test suite** — it would give false assurance about the half of this
> system that is judgement.

What we do instead: verify a skill by **walking its own instructions end to end**
against the fake, the way [#16](https://github.com/jeffrichley/paprika/issues/16)
verified its prototype. That has caught real bugs four times — a stale Mirror
after a write, a phone notified per night, a health finding that vanished, a
duplicate check defeated by an apostrophe — none of which any test had caught.

Everything else the skill says is in scope.

## Match the form to the failure

The single most useful thing in that skill, and the thing this plugin got wrong
in three documents before the audit.

| The failure | The form | Not |
|---|---|---|
| Knows the rule, breaks it under pressure | Prohibitions + a rationalization table | Soft guidance |
| Complies, but the **output is the wrong shape** | A positive recipe: *say these parts, in this order* | A prohibition list |
| Omits a required element | A required slot in a template | Prose reminders |
| Behaviour depends on a condition | A conditional on something observable | A rule plus exemptions |

Prohibitions **measurably backfire** on shaping problems: under a competing
incentive an agent negotiates with "don't X". A recipe leaves nothing to
negotiate — the output matches the stated shape or it does not.

`help`, `organize` and `plan-week` were all written as ban lists when their real
failure was output shape. `nutrition` has both kinds and is written with both.

## A rationalization table is not a common-mistakes table

They are different instruments and this plugin conflated them for ten documents.

- **Common mistakes** names the *violation*: "Asking her to spell it correctly →
  read the library instead."
- **Rationalization table** names the *thought that precedes it*: "'That's
  clearly not in her library' → read the index, it costs almost nothing and you
  are often wrong."

Discipline skills need the second. `pantry`, `edit-recipe`, `find-recipe`,
`add-recipe` and `nutrition` have one, because breaking their rules damages her
data or her trust.

## No `unless` hanging off a rule

"Never X unless Y" reopens the negotiation. Three of these existed here. Each
became a conditional on an observable predicate:

- ~~Never mark something gone unless she said so~~ → **Mark something gone only
  when she has said it is gone, in words, in this conversation.**

## Descriptions

- **"Use when…", triggers only, no workflow summary.** A description that
  summarises the process becomes a shortcut agents take *instead of* reading the
  body. `agents/library-scan.md` had one and it was removed.
- **Say what the user would say**, not what the domain calls it — *"how many
  calories"*, not *"nutritional analysis"*.
- **Third person, and no assumed gender.** A description is read about whoever
  installed this. The skill *bodies* use "she" because the spec is written about
  one cook; the descriptions must not.

There are conformance tests for the first of these and for the roster.

## Length

The skill's target is under 500 words for a skill that loads on trigger. Most
here run 600–900, and that is a deliberate deviation: these documents are the
only thing standing between a non-developer's decade-old library and a confident
mistake, and cutting behaviour rules to hit a word count is the wrong trade.

The budget that **does** bind is `using-paprika`, which is injected into every
session and holds a **35-line ceiling**, asserted by a test. That ceiling was set
before its content, so a new idea there has to trade against an existing one
rather than append to it.

Where there is genuine fat, it is usually **"Rules that do not bend" restating
"Common mistakes"**. Check for that before adding words.

## Cross-references

Use the name with an explicit marker — `**REQUIRED READING:** load
skills/shared/cooking-judgement.md`. Never `@`-links: they force-load
immediately and burn context before anyone needs the file.
