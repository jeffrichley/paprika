# Paprika owns the truth; our local copy is a mirror

Paprika is the single source of truth for every entity it stores — recipes, categories, meals, groceries, pantry. `~/.paprika` is authoritative only for what Paprika has no home for: the Profile, nutrition memos, credentials, and logs. The local copy is a **mirror**, never a write buffer, so it can only ever be fresh or stale — never in conflict.

This holds because every mutation is read-modify-write on a *freshly fetched* object: we re-read immediately before writing, so a local copy never accumulates edits the server hasn't seen.

## Considered options

The reference implementation in this ecosystem, `coddingtonbear/paprika-recipes`, does the opposite: it clones the library to local files you edit offline, and therefore needs `sync.py` (32 KB), `merge.py`, and a 54 KB `test_sync.py` implementing three-way merge against a stored base copy. It is the only conflict handling anywhere in the Paprika ecosystem, and it is genuinely good work.

We decline it — not by hoping conflicts won't happen, but by never creating the second writer that causes them.

## Consequences

- **There is deliberately no merge algorithm, no conflict resolution, and no stored base copy.** A reader who notices the gap should not fill it; the gap is the design.
- **Stale is resolved by discarding, not reconciling.** Refresh gates on `GET /sync/recipes/` — one request returning the whole-account `uid → hash` index — and re-fetches only what moved.
- **This decision depends on the safe-write strategy staying read-modify-write.** If a partial-write path is ever introduced, a second writer exists again and this ADR must be reopened, not worked around.
- Nothing offline-editable can be built on top of the mirror without revisiting this first.
