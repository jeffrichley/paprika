# Can `menuitems` hold a weekly plan?

Research for issue #5. Sources are third-party reverse-engineering projects and the official
user guide; no live API calls were made and no credentials were used. Every claim below is
tagged **Confirmed** (stated by a primary source, usually corroborated across two or more) or
**Inferred** (my reasoning from the evidence, not directly stated anywhere).

## TL;DR

**The question rests on a false premise, and the answer is better than the ticket feared.**

`menuitems` is **not** the weekly-plan resource and cannot carry a weekly plan — it has no date
field and requires a real recipe. But that doesn't matter, because a *different* endpoint,
**`/api/v2/sync/meals/`**, is the meal planner, and it carries everything a weekly plan needs:
a date, a meal slot, an optional recipe reference, and free text.

**Verdict: a weekly plan round-trips into the Paprika app.** No degraded fallback is required,
and the plan does **not** have to live only in `~/.paprika`.

## The resource model

Paprika's meal planning is **four distinct resources**, not one. This is confirmed by the sync
status endpoint, which returns a separate change counter for each — `meals`, `mealtypes`,
`menuitems`, and `menus` all appear as sibling keys in the same response object.

| Resource | Endpoint | What it actually is |
|---|---|---|
| `meals` | `/api/v2/sync/meals/` | **The meal planner.** One entry = one meal on one calendar date in one slot. |
| `mealtypes` | `/api/v2/sync/mealtypes/` | The slot definitions themselves (Breakfast/Lunch/Dinner/Snack + user-created ones). |
| `menus` | `/api/v2/sync/menus/` | A reusable, **undated** named template ("Thanksgiving", "Standard Week"). |
| `menuitems` | `/api/v2/sync/menuitems/` | The recipes *inside* a menu template, placed on a relative day offset. |

So yes — **`menus` and `menuitems` are two distinct resources** (Confirmed), and both are
distinct from `meals`.

The product guide confirms the intended relationship: a Menu is a way to "group your favorite
recipes into reusable menus," which you then "add to the meal planner" to populate several days
at once. A menu is a **stamp**; the meal planner is the **calendar it stamps onto**. Menus are
an input to the plan, not the plan.

### Why the ticket's premise misfired

Whoever documented `/api/v2/sync/menuitems/` as "meal planning" was describing the feature area,
not the resource. kappari's own notes make the same slip, calling menu items "planned meals
linking recipes to specific days" — but its `day` field is an integer offset within a template,
not a calendar date. kappari also explicitly lists the "distinction between menu and menu items
semantics" as an open gap in its docs, so it is not a reliable source on this point. The
Postgres and OpenAPI models below settle it.

## `meals` — field list

Fields are consistent across three independent sources: the OpenAPI spec in `paprika-tools`, the
`PaprikaMeal` struct in `paprika-rs`, and its Postgres `meal` table. (Confirmed)

| Field | Type | Notes |
|---|---|---|
| `uid` | string | Client-generated **uppercase UUID4**. Primary key. |
| `recipe_uid` | string \| **null** | Recipe link, **or `null` for a text-only meal**. |
| `date` | string | `"YYYY-MM-DD HH:MM:SS"`, e.g. `"2026-02-01 00:00:00"`. Time is zeroed in practice. |
| `type` | integer | `0 = Breakfast, 1 = Lunch, 2 = Dinner, 3 = Snack`. |
| `name` | string | Display name — **this is the free-text carrier**. |
| `order_flag` | integer | Display order within the same date + type. |
| `type_uid` | string | FK to a `mealtypes` entry. Needed for custom slots. |
| `scale` | string \| null | Serving-size adjustment. Defaults null. |
| `is_ingredient` | boolean | Entry is an ingredient rather than a full recipe. Defaults false. |
| `deleted` | boolean | Soft-delete flag. Defaults false. |

Note `type` (integer) and `type_uid` (FK) coexist. (Inferred) `type` is the legacy fixed
enum and `type_uid` points at the user's actual, renameable/reorderable meal type; the
`mealtypes` schema carries an `original_type` integer, which looks like exactly the
back-compat bridge between the two. Safest write strategy is to set both consistently — read
`mealtypes` first and use a real `type_uid` rather than inventing one.

### The free-text finding, and why it's solid

This is the load-bearing fact for the wife's workflow, so it's worth showing the evidence is
independent and empirical rather than a single doc claim:

1. The OpenAPI spec says outright: `recipe_uid` is "UID of the associated recipe, **or null for
   text-only meals**," and the upload body repeats "Set `recipe_uid` to link a recipe, or null
   for a text-only meal."
2. `paprika-rs` types it `Option<String>` — and, more tellingly, shipped a dedicated migration
   (`20211006031842_optional_meal_recipe_uids`) whose entire body is
   `ALTER TABLE meal ALTER COLUMN recipe_uid DROP NOT NULL;`. The original schema assumed a
   recipe was mandatory; **real account data proved otherwise** and forced the constraint off.
3. The iOS guide confirms it at the product level: when adding to the planner you "choose
   between adding a Recipe, a Note, or an entire Menu." A Note is a free-text meal.

Three sources, one of them a bug-driven schema change against live data, and one of them
official. (Confirmed)

## `menuitems` — field list, and why it can't hold a plan

From `PaprikaMenuItem` and the Postgres `menu_item` table. (Confirmed)

| Field | Type | Notes |
|---|---|---|
| `uid` | string | Primary key. |
| `name` | string | Display name. |
| `order_flag` | integer | Display order. |
| `recipe_uid` | string, **NOT NULL** | Recipe link — **required**. |
| `menu_uid` | string | FK to the owning `menus` entry. |
| `type_uid` | string | FK to a meal type. |
| `day` | integer | **Relative day index within the template. Not a date.** |

And `menus`: `uid`, `name`, `notes`, `order_flag`, `days` (integer — template length).

Measured against what a weekly plan needs:

| Requirement | `menuitems` | `meals` |
|---|---|---|
| A date | **No** — only `day`, an integer offset | Yes — `date` |
| A meal slot | Yes — `type_uid` | Yes — `type` + `type_uid` |
| Recipe reference | Yes, but **mandatory** | Yes, and **optional** |
| Free-text entry | **No** — `recipe_uid` is NOT NULL | Yes — `name` with `recipe_uid: null` |

The contrast between the two `recipe_uid` columns is the sharpest signal in the whole
investigation: in the same schema, by the same author, `meal.recipe_uid` was deliberately made
nullable while `menu_item.recipe_uid` was left NOT NULL. Menu items are recipe collections by
design. A note cannot be a menu item.

## Writes: does it round-trip?

Yes. `meals` is read/write. (Confirmed)

- `GET /api/v2/sync/meals/` → `{"result": [ ...MealPlan ]}`
- `POST /api/v2/sync/meals/` → create **or update**, upsert by `uid`

Write mechanics (Confirmed, consistent across kappari and paprika-tools):

- `multipart/form-data`, single field named `data`.
- The field holds a **gzip-compressed JSON array** — an array, not a bare object, even for a
  single meal.
- Client generates the `uid` as an **uppercase UUID4** for new entries.
- Delete by setting `deleted: true` and POSTing the entry again. Nothing is hard-deleted.
- **There is no per-uid endpoint for meals.** `POST /v2/sync/meals/{uid}/` returns `404 Not
  found` — always POST the array to the collection. (This differs from recipes, which *do* have
  a per-uid form. Worth encoding in the plugin so it isn't rediscovered painfully.)
- kappari notes a quirk in Paprika's multipart framing — `Content-Type` placed *before*
  `Content-Disposition`, and the field name unquoted. (Inferred) Some clients may be strict
  about this; if writes get rejected, look here first.

There is also `POST /api/v2/sync/notify`, which nudges other devices to pull. (Inferred, but
well-supported — it's what paprika-3-mcp calls after saving a recipe.) For this use case that's
the difference between the plan appearing on the phone promptly and appearing whenever the app
next decides to sync, so the plugin should call it after writing meals.

## Conflict behaviour

**This is the weakest-evidence section, and I want to be blunt about that.** kappari lists "Map
out conflict resolution patterns" as an explicit open **To Do**, and paprika-tools documents no
conflict semantics at all. Nobody has reverse-engineered this properly. What follows is
inference from the shape of the protocol, not documented behaviour.

What's **Confirmed**: sync is state-based, not a change log. Whole records are POSTed with all
fields populated. The sync status endpoint returns per-resource **change counters** that
increment on modification and are meant to be diffed against a previously stored value to
detect which resource types need re-pulling. Deletes are soft.

What's **Inferred** from that:

- **Last-write-wins per record, at whole-record granularity.** There is no ETag, no version
  field, no `If-Match`, and no per-field merge in any observed payload. If the plugin and the
  app both edit the meal with the same `uid`, whichever POST lands second overwrites the other
  wholesale — including fields the second writer never intended to touch, since it sends the
  full record.
- **The nastier failure mode is duplication, not overwriting.** If the wife adds "Tuesday
  dinner" in the app while the plugin independently adds its own "Tuesday dinner," the two
  entries have *different* client-generated UUIDs. Nothing reconciles them by (date, type).
  Both survive, and Tuesday shows two dinners. Since `uid` is minted client-side, this is the
  expected outcome of concurrent creation, and it is silent.
- The change counters only tell you *that* `meals` changed, not *which* meal. Detecting a
  specific remote edit means re-pulling the full `meals` collection and diffing locally.

Practical guidance for the plugin, given the phone-plus-desktop workflow:

1. **Always GET `meals` immediately before writing**, and reconcile on `(date, type_uid, name)`
   as well as on `uid`, so an app-created entry is matched instead of duplicated.
2. **Preserve unknown fields on update.** Read the existing record, mutate only what changed,
   POST it back whole. Do not construct meal objects from scratch when updating.
3. **Never blind-overwrite a day.** If a remote entry exists for a slot that the local plan
   also fills, surface it rather than clobbering it — the app side is a human who cooked from
   that entry.
4. Treat the last-write-wins model as unverified. It should be confirmed against a real account
   before the plugin relies on it for anything destructive.

## Fallback

**Not needed.** The premise of the fallback question was that meal planning might be
unrepresentable; it isn't. The plan should live in Paprika via `meals`, and `~/.paprika` should
hold at most a local cache/mirror for diffing and offline editing — not the system of record.

Recorded for completeness, if `meals` writes turn out to be blocked in practice:

- **Do not fall back to `menus`/`menuitems`.** It loses dates entirely and silently drops every
  free-text meal, which is precisely the lossy round-trip this ticket was worried about.
- The honest degraded path would be local-only storage plus human-readable export, with the
  loss stated plainly to the user rather than papered over.

## Open questions

- Meal type `type_uid` values are per-account. The plugin must GET `mealtypes` first; it can't
  hardcode them. Custom user-defined slots beyond 0–3 are supported by the product, and how
  those map onto the integer `type` field is unverified.
- Conflict resolution is genuinely undocumented (above). Highest-value thing to verify against
  a real account.
- `is_ingredient` and `scale` semantics are unclear; both appear safe to leave at defaults.
- Whether the server validates `recipe_uid` against existing recipes, or accepts dangling refs.

## Sources

- `johnwbyrd/kappari` — `endpoints.md`, `api.md`, `patterns.md`, `schema.md`
  (`schema.md` covers recipes only; it has no meal/menu tables)
- `aarons22/paprika-tools` — `openapi.yaml` (`MealPlan` schema, `/meals/` paths, sync status
  counters), `API_REFERENCE.md`
- `Syfaro/paprika-rs` — `paprika-client/src/lib.rs`, `migrations/20210730041040_recipes.up.sql`,
  `migrations/20211006031842_optional_meal_recipe_uids.up.sql`
- `soggycactus/paprika-3-mcp` — `internal/paprika/client.go` (recipes only; no meal support —
  useful only for the `sync/notify` pattern)
- Paprika iOS user guide — <https://www.paprikaapp.com/help/ios/> (Meal Planner; Recipe/Note/Menu;
  customizable meal types)
