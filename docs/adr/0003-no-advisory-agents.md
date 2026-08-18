# No advisory agents; cooking judgement is shared, not summoned

This plugin was designed around two advisory agents — a nutritionist and a chef. It ships neither. A Claude Code subagent has three real properties: a fresh context, its own tool allowlist, and its own prompt. Neither job wants them, so cooking judgement became a **shared reference the skills load**, and the nutrition rules became **rules inside `/paprika:nutrition`**.

The nutritionist wanted the opposite of a fresh context. `/paprika:nutrition` renders provenance-bearing output — ranges, a weakest-input line — directly into the conversation, so the main thread already holds it. A subagent would have to be re-handed that text, inserting a summarisation step exactly where the design forbids one: a range collapsed to its midpoint destroys the whole mechanism. And an agent asked to discuss numbers it cannot quite see is under standing pressure to compute its own.

The chef wanted to be everywhere, and an agent is a place. Cooking judgement is needed while a week is drafted, while a search result is judged against the household, and while a scanned page is read. A personal chef who exists only when summoned by name is a worse chef than one that is simply how the kitchen works — and the chef's real mode is conversational ("not that, we had it Tuesday"), which cold subagent dispatches cannot sustain.

## Consequences

- **A reader who finds no `agents/` directory should not add one for these two.** The absence is the design.
- **The rule "advisory agents read skill output, never recompute" has no home, and needs none.** It restates as *numbers come from `/paprika:nutrition`, or they do not exist* — enforced by the `using-paprika` fence plus the *no provenance means no number* backstop.
- **`/paprika:plan-week` drafts with this judgement, not mechanically.** Rejected: a cheap mechanical draft plus an optional "improve it" pass — that builds the logic twice and makes the first week she sees the worse one.
- **This is not a blanket no-agents rule.** The bulk duplicate-and-cleanup scan is token-heavy, mechanical, and non-conversational over hundreds of recipes; a fresh context genuinely earns its keep there. That call belongs to the bulk-cleanup decision, not to this ADR.
