# The plugin never opens a file into the session

[ADR 0005](0005-the-library-scan-is-the-only-agent.md) shipped one agent and justified it by weight: the
Scan reads several hundred recipes, and you do not want four hundred recipes in her chat.
[#21](https://github.com/jeffrichley/paprika/issues/21) asked whether folder-scale file intake — she points
at forty photographed cookbook pages — earns a second agent on the same grounds. The proposed answer was
*single file inline, a folder dispatches an agent*: the seam is scale.

That was wrong, and the correction is the decision. **Anything the plugin opens itself, it opens in a
subagent — one file or forty.** A single cookbook photo is still a page of image tokens landing in a
context that has a week-planning conversation to hold, and it buys nothing to have it there. More
importantly, a rule with a threshold in it is a rule contributors argue with: *big jobs get an agent*
invites the question of what counts as big, and every answer to that question is a judgement call made at
the wrong moment. A rule with no threshold survives.

The boundary is **where she points, not what the file is**. What she puts directly in front of us — an
image pasted into the CLI, a recipe typed or dictated — is already in the context before any skill runs,
and a subagent cannot un-see it; there is nothing to protect, so it is read in place. A path or a folder
she *names* has not been opened yet, and never should be.

## What follows

- **`agents/` holds two files, not one.** The Scan reads the library; the **Reader** reads files. They
  share the property that matters and nothing else: a large read, a small return, and **no write tool at
  all**. Everything either produces is a Draft that a skill turns into a Run on her yes, so 0005's safety
  model is unchanged — this widens the roster it applies to, it does not weaken it. Their judgement has
  nothing in common, which is why they are two agents under one rule rather than one agent with two jobs.
- **The return is fields and named gaps, and nothing else.** No confidence number, no page coordinate, no
  `OCR returned null` crosses back — the same fence [ADR 0006](0006-the-cli-splits-on-determinism.md) puts
  on `hash` and HTTP status, for the same reason: a session cannot leak what it was never handed. The
  structural evidence that made something a gap goes to the log. **Rendering stays in the skill**, because
  how to say it to her is judgement, and judgement is the one thing that does not belong on the far side
  of a dispatch.
- **It amends [#18](https://github.com/jeffrichley/paprika/issues/18) retroactively.** A pasted shelf photo
  is read inline as #18 described. *"The pantry photos are in `~/Desktop/shelf/`"* routes through the
  Reader like anything else. #18 decided a photo is evidence rather than a mode; this decides only who
  holds the file while reading it.
- **Reads commit incrementally to disk.** The Reader writes each draft as it finishes it, into
  [#13](https://github.com/jeffrichley/paprika/issues/13)'s disposable tier — its own directory, not the
  Mirror, because work in progress and a stale copy of Paprika are two different kinds of staleness.
  Forty images is the most expensive read in the plugin to have to do twice, and this is what makes 0006's
  *resumable because it commits incrementally, never because it is timed* true here rather than
  decorative.
- **Enforcement is the allowlist, not a convention.** 0006 put every mutating command under one
  `paprika write …` prefix so that "holds no write tool" is one deny rule. Both agents sit behind it.
