# The CLI splits on determinism, and it is where Paprika's mechanics stop

Ten skills reach Paprika through one `paprika` console script. The question was what that surface is
shaped like. Mirroring the API — `recipe get`, `meals list`, one command per endpoint — walks into the
gap [#8](https://github.com/jeffrichley/paprika/issues/8) found in all six existing projects, where
cross-entity reasoning exists nowhere. Mirroring the skills — `plan-week`, `grocery-list` — puts cooking
judgement inside a Python program, which is the one place it cannot live.

Neither axis is the real one. **The line is between what must be identical every time and what needs
judgement.** Everything deterministic belongs in the CLI *even when it spans entities*: the write
chokepoint, the setup preconditions, pre-image capture, the plan-minus-pantry subtraction, the nutrition
rollup, the library health report. Everything requiring judgement — which dish fills Friday, whether a
cluster is a real category, how to say any of it to her — stays in the skill. The deterministic half is
then testable in pytest instead of re-derived by a model each week, and the axis predicts where a command
nobody has imagined yet belongs.

The second half of the decision is a contract rather than a shape: **the CLI is where Paprika's mechanics
stop.** No `hash`, no sync counter, no HTTP status, no token, no `in_trash`-versus-`deleted` ever crosses
into the session; those go to the log. Envelopes speak the glossary's language and `error.message` is a
sentence already fit to say to her. [ADR 0003](0003-no-advisory-agents.md)'s companion,
[#11](https://github.com/jeffrichley/paprika/issues/11), fences Claude *out* of the API; this fences the
mechanics out of Claude. It is what makes
[the prototype's](../prototypes/PROTOTYPE-week-planning-conversation.md) result structural: *uid, hash,
sync, token, API, cache, tier, provenance, 200* never appeared in a whole session, and a skill cannot leak
what it was never handed.

## What follows

- **Writes take a patch, never an object.** [ADR 0004](0004-one-chokepoint-for-every-write.md)'s
  `write(uid, mutate_fn)` cannot cross a process boundary — Claude cannot pass a closure. So a write names
  keys and values (`--set`, `--add`, `--remove`) and the core does the fetch, the merge, the `hash`
  regeneration, the `photo_url` strip and the pre-image. **The transport physically cannot carry a whole
  object**, which makes 0004's "unenforceable exception" impossible rather than merely discouraged.
  Anything a patch cannot express is a missing command, not grounds for accepting an object.
- **Every mutating command sits under one `paprika write …` prefix.** Read-versus-write becomes visible in
  the command string, greppable in the log, and — the reason it wins — expressible as *one* deny rule, so
  [ADR 0005](0005-the-library-scan-is-the-only-agent.md)'s "the Scan holds no write tool at all" is
  enforced by the allowlist rather than by a list somebody maintains. `sync` stays outside the prefix: it
  moves the mirror, not her data, and a prefix that means two things means neither.
- **The envelope names which kind of thing moved.** `{ok, attempted, changed: {recipes: 3}, complete,
  error: {code, message}}`. Rule 4's third fact — *did her library change* — is a map by kind, not a
  boolean, because [#16](https://github.com/jeffrichley/paprika/issues/16) found the single word "library"
  flattened the exact distinction that decided whether she dared retry. `{}` means nothing moved;
  `complete: false` with a non-empty `changed` is the partial run. The exit code always agrees with `ok` —
  never trusting a status code is a complaint about Paprika, not a habit to reproduce one layer down.
- **Freshness is established by asking.** A read serves the mirror and fires one request at `/sync/status/`
  first; unchanged counters prove the mirror current. This is not an optimisation over a TTL —
  [#19](https://github.com/jeffrichley/paprika/issues/19) found deletions leave **no tombstone**, so a
  moved counter is the only signal that a recipe she deleted on her phone is gone. A clock-based mirror
  would serve a recipe that no longer exists and never learn otherwise. Warm cost is one request; changed
  is two plus however many actually differ.
- **Long work is resumable because it commits incrementally, not because it is timed.** There are no
  timeouts and no budgets anywhere. The mirror writes each recipe as it arrives and a run records each
  landed write as it goes, so anything that kills the process costs a slice rather than the run. The
  estimate shown before a long wait is **measured from the logged per-request durations on her own
  machine**, falling back to the published ~200 ms only on a first run.
- **There is no local semantic search, because the library is small enough to read.** A one-line index
  entry is ~16 tokens, so all 500 recipes cost ~8k — the model *is* the semantic engine, and it shortlists
  from the index then pulls a handful of bodies to judge ingredients. Misspellings dissolve rather than
  being corrected. Embeddings were rejected on the same ground 0003 rejected the nutritionist: a
  similarity score is a **second judge competing with the model**, returning a confident number with no
  provenance — [#7](https://github.com/jeffrichley/paprika/issues/7)'s matcher failure in a new hat, with
  no honest way to show her why a vector thought a dish was mild.
- **Two commands deliberately do not exist.** No `write recipe remove` — 0004 reserves `deleted: true` for
  objects the plugin created, so it stays core-internal and unreachable from the session, and what she
  calls deleting is `trash`, recoverable in the app itself. No `write category delete` — her scheme wins,
  and a command that can dismantle a 104-node tree has no caller in the roster.
- **This reopens if the library grows.** The index decision is arithmetic over a *measured* 500 recipes.
  Somewhere in the low thousands the whole-library read stops being free and local semantic search becomes
  worth its cost. That is the trigger to revisit — not a caveat to discover in production.
