# A recipe is named in the session by a handle derived from its uid

[ADR 0006](0006-the-cli-splits-on-determinism.md) puts Paprika's mechanics on the far side of
the CLI, and a `uid` is squarely one of them. But a skill still has to be able to say *which*
recipe it means — to pull a body after reading the index, and later to aim a write at one. So
the fence creates a problem it also has to solve: an identifier that is stable, unambiguous, and
not a mechanic.

Passing the uid anyway was rejected on arithmetic as much as on principle. Five hundred
uppercase UUIDs is roughly ten thousand tokens of the exact string the fence exists to keep out,
spent on every whole-library read — which, since
[#20](https://github.com/jeffrichley/paprika/issues/20) decided the library is small enough to
read rather than search, is the common case rather than an edge one.

**A recipe is named by a handle: the first six hex characters of its uid, lengthened only for
the recipes that would otherwise collide.** Six characters is about one token. Being *derived*
rather than *assigned*, it needs no mapping table, survives a Mirror being discarded and rebuilt,
and is identical on two machines syncing the same account — none of which is true of a counter
or a generated name.

## Alternatives considered

- **A sequence number** (`recipe 7`). Cheapest to read, but it is a position rather than an
  identity: it changes when the library is re-sorted or a recipe is trashed, so a handle she saw
  a minute ago can silently mean a different dish. Deletions leave no tombstone
  ([#19](https://github.com/jeffrichley/paprika/issues/19)), so nothing would even detect the
  shift.
- **A slug from the name** (`roast-lemon-chicken`). Readable, and wrong: her library has genuine
  duplicates — finding them is a whole job in
  [ADR 0005](0005-the-library-scan-is-the-only-agent.md) — so names collide precisely where
  precision matters most, and a rename would move the handle.
- **A mapping table** from short id to uid. Solves collisions, but adds durable state that can
  drift from the Mirror and has to be rebuilt whenever the Mirror is. Derivation makes the
  question not arise.

## Consequences

- **Uniqueness is a property of the whole Library, not of one recipe.** Handles are therefore
  assigned once at the end of a sync, when every uid is known, rather than per recipe as it
  lands.
- **Collisions lengthen rather than clash.** Six hex characters is ~16.7M values; at 500 recipes
  a collision is unlikely but not impossible, and the answer is a longer handle for the colliding
  pair alone rather than for all five hundred.
- **A handle is stable for as long as the uid is**, which is forever — Paprika's uid is
  client-generated and immutable once created. It is not stable across a recipe being deleted and
  re-created, which is correct: that is a different recipe.
- **The CLI accepts handles and never uids.** A caller that has somehow obtained a uid cannot use
  it, which is the fence holding rather than an inconvenience.
