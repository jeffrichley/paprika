# The Paprika password is stored at rest, not in a keyring

Credentials live in `~/.paprika/.env` at mode 0600, loaded by the CLI. The password persists — not just the JWT — because re-authentication must be transparent: Paprika's token lifetime is undocumented, and no client in the ecosystem knows when a token expires.

The primary user is not a developer. A token that dies mid-week and drops her at a credentials prompt is the failure that ends her use of the tool.

## Considered options

**A system keyring** (as `coddingtonbear/paprika-recipes` uses) is the more secure answer and was rejected on the merits: it raises an OS prompt she has no context for, and it makes remote repair impossible — the person who fixes her install is on the phone, not at her keyboard.

## Consequences

- **This is a real security concession, and it is named as such in the README** in plain language. The person accepting the risk should be told they are accepting it.
- The JWT is stored separately, in `state.toml`, so the CLI rewriting a token on every re-auth can never clobber a password that was just fixed by hand.
- Anyone with read access to the user's home directory can read the Paprika password. On a single-user personal machine that is the accepted threat model; it would not be acceptable on a shared or managed host.
