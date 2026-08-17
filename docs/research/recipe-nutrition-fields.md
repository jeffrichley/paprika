# Recipe nutrition fields in Paprika

Research for issue #6. Sources are the public reverse-engineered specs and clients listed
at the bottom; no live API calls and no credentials were used.

## Short answer

A Paprika recipe carries exactly one nutrition-related field: `nutritional_info`. It is a
**single free-text string** — not structured, not parsed, not computed by the app. It is
fully writable through the sync API. Of the existing open-source servers, one reads and
writes it, one silently destroys it, and two ignore it entirely.

There is **no structured nutrition foothold in Paprika's data**. Per-recipe nutrition must
be computed from the ingredient list.

## The field

From the OpenAPI spec in `aarons22/paprika-tools` (`openapi.yaml`, `Recipe` schema):

```yaml
nutritional_info:
  type: string
  description: Nutritional data (free text).
  default: ""
```

Properties worth pinning down:

| Property | Value |
| --- | --- |
| Type | `string` (never null in the spec; defaults to `""`) |
| Structure | None. No sub-schema, no key/value convention, no units |
| `maxLength` | Not specified anywhere in the spec |
| `readOnly` | No — it appears in both the response body and the upsert request body |
| Storage | `nutritional_info TEXT` in the app's local SQLite `recipes` table |

`johnwbyrd/kappari`'s `schema.md`, which documents the on-device SQLite database, lists it
as `nutritional_info | TEXT | Nutritional information data | NULL (observed)`. The
"NULL (observed)" is the interesting part: across the sampled real database, the field was
empty on every recipe. It is a field almost nobody fills in.

There is nothing else. No `calories`, no `macros`, no `nutrition` object, no per-ingredient
nutrition, no serving-weight field. `servings` is itself free text (`"12 muffins"`,
`"One serving"`, `"8 1-cup servings"`), so even normalizing computed nutrition to a
per-serving basis requires parsing that string.

## What the app does with it

Per the Paprika iOS help, `nutritional_info` is an optional recipe field described as
"Any nutritional information you would like to record for this recipe." The app:

- lets the user type or paste anything into it,
- optionally shows or hides it when printing a recipe,
- does **not** parse it,
- does **not** compute it from ingredients,
- does **not** total it across a meal plan or a day.

So it is inert reference text. Whatever goes in comes back out verbatim, and the app never
disagrees with it. Web import may populate it as a blob of scraped text when a source site
publishes one, but there is no normalization.

## Writability, and the two hazards

The field is writable, but only via a full-object write. From `API_REFERENCE.md` in
`paprika-tools`:

> POST `/v2/sync/recipe/{uid}/`
> 1. Data must be gzip-compressed JSON of the **full recipe object** (not partial)
> 2. Send as `multipart/form-data` with field name `data`
> 4. Must include ALL fields — empty strings for unused text fields, `false` for booleans,
>    `0` for rating, `[]` for categories
> 5. Update the `hash` field whenever recipe content changes (any 64-char hex string works)

That yields two hazards that matter more than the field itself.

**Hazard 1 — partial writes are destructive.** Because the POST replaces the whole object,
any writer that constructs a recipe from a subset of fields wipes everything it omitted.
This is not hypothetical: `soggycactus/paprika-3-mcp`'s `update_paprika_recipe` handler
builds a fresh `paprika.Recipe{}` from ten tool arguments and calls `SaveRecipe` with it.
`SaveRecipe` does no read-modify-write merge — it stamps `created`, a UUID and a hash, then
gzips and POSTs exactly what it was handed. `nutritional_info` is not among the ten
arguments, so every update through that server silently blanks the field (along with
`rating`, `categories`, `source`, `source_url`, `photo`, and favorites). Any writer we build
must fetch the recipe, mutate one field, and write the whole thing back.

**Hazard 2 — third-party clients drop the field on round-trip.** `Syfaro/paprika-rs` does
not model `nutritional_info` at all. Its `PaprikaRecipe` struct (28 fields) omits it, and so
does the `recipe` table in `migrations/20210730041040_recipes.up.sql`. A round-trip through
that client loses the field. This is a general warning: `nutritional_info` is the field
integrators forget, so anything we store there is more fragile than it looks.

Note also that the recipe `hash` is a change-detection token the client sets, and any
64-character hex string is accepted — the server does not verify that it is a real digest of
the content. Writing to `nutritional_info` therefore requires bumping `hash` so other
devices pick the change up on sync.

## Which existing servers touch it

| Project | Reads it | Writes it | Notes |
| --- | --- | --- | --- |
| `briantkatch/paprika-mcp` | Yes | Yes | The only server that does both properly |
| `aarons22/paprika-tools` | Passthrough | Passthrough | Returns the raw recipe dict; no nutrition-specific logic |
| `soggycactus/paprika-3-mcp` | Modeled only | **Destroys it** | `NutritionalInfo` exists on the struct but no tool sets it; updates blank it |
| `Syfaro/paprika-rs` | No | No | Field absent from both the struct and the Postgres schema |
| `johnwbyrd/kappari` | Documents it | n/a | Local-DB schema documentation, not a client |
| `radicalrob/paprika-mcp` | — | — | Repository returns 404; does not exist publicly |

`briantkatch/paprika-mcp` is the useful precedent. Its `read_recipe` tool renders the field
as a `## Nutritional Info` markdown section when non-empty, and lists it among the
selectable `fields` so a caller can request nutrition alone. Its `update_recipe` tool
accepts `nutritional_info` as one of its writable fields and mutates it by find/replace on a
recipe object it first fetched from the remote — the correct read-modify-write shape. It
relies on a fork of the `paprika-recipes` library, whose `Recipe` dataclass declares
`nutritional_info: str = ""`, confirming the field is a plain string end to end.

So: writing computed nutrition into `nutritional_info` is demonstrably possible, and someone
already does the read half of it.

## Recommendation

**Compute nutrition from the ingredient list. Do not depend on `nutritional_info` as an
input. Do write a rendered summary back into it as a secondary, best-effort output.**

Three parts:

1. **Not an input.** The field is empty on essentially every real recipe, unstructured when
   present, unattributed as to serving basis, and unverifiable. Parsing it would be guessing
   at a blob a human or a scraper typed. The plugin's nutrition numbers must come from the
   ingredient list, where quantities and units are at least regularly shaped.

2. **Not the system of record.** Computed nutrition that the plugin rolls up daily against
   targets needs to be structured, versioned, and re-derivable. Round-tripping it through a
   free-text field means re-parsing our own output, and any third-party client (paprika-rs
   today, others tomorrow) can drop it without warning. Keep the authoritative computed
   values in the plugin's own store, keyed by recipe `uid` plus a content hash of the
   ingredient text so staleness is detectable.

3. **A good write-back target.** The field is exactly the right place for the *human-facing*
   rendering — a few lines of "Per serving: 520 cal, 31 g protein, 44 g carbs, 24 g fat"
   with a marker line noting it was computed by the plugin and when. That makes the numbers
   visible in Cindy's app on her phone, which is where she actually cooks, at zero cost to
   the plugin's own model. It is inert text the app will never fight us over, and it is the
   one field where clobbering the user's own content is nearly risk-free — though the writer
   should still preserve any pre-existing human text rather than overwrite it blindly.

Write-back must be implemented as fetch-full-recipe → set `nutritional_info` → bump `hash` →
gzip → POST full object. Anything less destroys unrelated recipe data.

## Sources

- `aarons22/paprika-tools` — `openapi.yaml` (`Recipe` schema), `API_REFERENCE.md`
  (write protocol, field table), `paprika_mcp/`, `paprika/cmd/recipes_upsertRecipe.go`
- `johnwbyrd/kappari` — `schema.md` (local SQLite `recipes` table)
- `Syfaro/paprika-rs` — `paprika-client/src/lib.rs`,
  `migrations/20210730041040_recipes.up.sql`
- `briantkatch/paprika-mcp` — `tools/read_recipe.py`, `tools/update_recipe.py`,
  `pyproject.toml`; and `briantkatch/paprika-recipes` `paprika_recipes/recipe.py`
- `soggycactus/paprika-3-mcp` — `internal/mcpserver/server.go`, `internal/paprika/client.go`
- Paprika iOS help — <https://www.paprikaapp.com/help/ios/>
- `radicalrob/paprika-mcp` — 404, no such public repository
