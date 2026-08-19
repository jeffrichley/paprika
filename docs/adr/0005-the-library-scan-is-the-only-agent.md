# The library scan is the plugin's only agent, and it cannot write

[ADR 0003](0003-no-advisory-agents.md) rejected both agents this plugin was designed around and said explicitly that it was not a blanket rule, leaving one call open: the bulk duplicate-and-cleanup scan. It ships as an agent. It is the only one.

The scan is the inverse shape of the nutritionist and the chef. Both of those wanted the opposite of a fresh context — one needed to stay inside a conversation that already held its output, the other needed to be everywhere at once. The scan wants a fresh context for the reason subagents exist: it reads several hundred recipes to cluster them, and **you do not want four hundred recipes in her chat**. It is mechanical, token-heavy, non-conversational, and it runs once and returns.

It has **no write tool at all**. It receives the mirror, the category tree, and the cooking-judgement reference, and returns a proposal — clusters, destinations, duplicate sets. Every write still goes through a skill and through the [one chokepoint](0004-one-chokepoint-for-every-write.md), so the confirmation floor is untouched: the agent proposes, she says yes, the skill writes.

The read-only property is stated in the agent's own definition rather than left as a convention, because the failure mode is a future contributor noticing that the agent could just apply its own proposal and save a round trip. That round trip is the entire safety model.

## Consequences

- ~~**`agents/` holds exactly one file.**~~ **Superseded by [ADR 0007](0007-the-plugin-never-opens-a-file-into-the-session.md):**
  `agents/` holds two — the Scan and the **Reader**, which reads any file the plugin opens for itself. The
  title of this ADR is narrower than it was; everything under it still holds, and now applies to both. A
  reader arriving from ADR 0003 is still looking at that ADR's explicitly-deferred call, resolved — the
  count changed, the rule did not.
- **The cooking-judgement reference travels with it.** Proposing that a dish is a weeknight thing is cooking judgement, and an agent reasoning about her food without that reference would invent its own taxonomy. This is the one place where "an agent is a place" is not a problem, because the place is exactly where the judgement is needed.
- **The health report does not use the agent.** Counting recipes with no category, recipes filed only at a root, empty categories, and missing photos is arithmetic over the mirror. The agent is dispatched only once she picks a job, so the report is instant, deterministic, free, and cannot be wrong in an interesting way.
- **A no is not a failure to route around.** Because the agent only proposes, a rejected cluster costs one dispatch and nothing else — which is what makes it safe to drop a rejected group and never re-propose it.
