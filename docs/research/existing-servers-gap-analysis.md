# Existing Paprika Servers: Coverage and Gap Analysis

Research for issue #8, incorporating leads from #9 (photo upload). Sources read: READMEs, OpenAPI
specs, tool/command definitions, HTTP clients, and database migrations, fetched read-only via the
GitHub contents API. No repository was cloned, no live Paprika API call was made, no credentials were
used. Every behavioural claim below was verified against source, not against a README.

Date: 2026-08-16

---

## 0. Corrections to the brief

**`https://github.com/radicalrob/paprika-mcp` does not exist publicly.** `GET /repos/radicalrob/paprika-mcp`
returns 404 and the account `radicalrob` (Rob Lewis, id 13987694) reports `public_repos: 0`. It was
either deleted, made private, or never public. Nothing in this document describes it, and no claim
about its "14 tools" is repeated as fact.

**There is a sixth project the brief did not name, and it is the most important one:**
[`coddingtonbear/paprika-recipes`](https://github.com/coddingtonbear/paprika-recipes) (Python, 83
stars). It is assessed as a full column throughout. It is the only implementation anywhere that
handles recipe photos, and one of only three that handle recipe updates without destroying data.

To keep the survey at a useful breadth I also read the two closest *public* Python/TS MCP servers in
place of the missing one:

| Slot | Project | Why |
| --- | --- | --- |
| (substitute) | [`sandordaroczi/paprika-mcp-python-server`](https://github.com/sandordaroczi/paprika-mcp-python-server) | Python, largest recipe-lifecycle MCP server in the wild (9 tools, ~48 KB server) |
| (substitute) | [`mcgilly17/paprika-mcp`](https://github.com/mcgilly17/paprika-mcp) | TypeScript, the only MCP server with recipes + groceries + meals + categories together |

---

## 1. Per-project summaries

### 1.1 `aarons22/paprika-tools` — OpenAPI spec + generated Go CLI + Python FastMCP server

**What it is.** Three artifacts of very unequal quality: a hand-written 27 KB OpenAPI 3.0.3 spec, a
34 KB `API_REFERENCE.md` (which actually documents *two* APIs — Paprika **and** Skylight Calendar,
because the repo's real purpose is a Paprika→Skylight bridge), a code-generated Go CLI, and a small
FastMCP server.

**Operations.** Read: `getSyncStatus`, `listRecipes`, `getRecipe`, `listCategories`,
`listGroceryLists`, `listGroceryItems`, `listMealPlans`, `listPantryItems`. Write: `upsertRecipe`
(spec + Go CLI only), `createGroceryItems`, `createMealPlans`. The Python MCP server exposes 9 tools
but only **one** of them writes — `add_grocery_item`. There is no `upsert_recipe` MCP tool despite
the spec defining one.

**Auth.** Best-documented flow of the six. `POST /api/v1/account/login/` with **both** HTTP Basic
(`base64(email:password)`) **and** a form body of the same credentials; token at `result.token`;
Bearer thereafter. Python side caches the token to
`~/Library/Application Support/paprika-mcp/.paprika_token.json` (chmod 0600) and — uniquely among
all projects surveyed — **retries once on 401 after re-authenticating**. Credentials themselves are
stored in plaintext TOML at `config.toml` (0600), macOS path hardcoded. The Go CLI is separate and
worse: it reads `PAPRIKA_TOKEN` from the environment or `~/.config/paprika/config.yaml` and never
refreshes.

**Sync/caching.** Documents the two-step pattern (`/sync/recipes/` returns `{uid, hash}` stubs →
fetch only changed `uid`s) and the `/sync/status/` change counters. **Documents it but does not
implement it.** There is no recipe cache anywhere in the codebase; `list_recipes` returns raw stubs
and hands the hash-diffing job to the LLM.

**Write safety.** Not applicable to the MCP server (no recipe write). The Go CLI's `upsertRecipe`
requires the *user* to hand it a pre-gzipped file on disk, so field completeness is entirely the
user's problem — the spec warns "must include ALL fields" and then offers no help meeting that bar.

**Photos.** None. The OpenAPI spec has no `/photos` path and no `photo_upload` concept; `photo`,
`photo_hash`, `photo_large`, `photo_url` appear as schema fields only.

**Where it stops.** No pantry write, no category write, no menus, no delete, no search, no cache, no
nutrition, no photos. The Go CLI is generated boilerplate: `internal/client/pagination.go` implements
page/offset/cursor auto-pagination for an API that has **no pagination at all** (dead code),
`execute()` never decompresses gzip responses and never handles 401. A 12 MB compiled binary is
committed to the repo.

### 1.2 `soggycactus/paprika-3-mcp` — Go, create/edit recipes

**What it is.** A Go MCP server (mark3labs/mcp-go, stdio transport), 35 stars, goreleaser'd.
Deliberately narrow: "MCP Server for creating/editing recipes in Paprika 3 with natural language."

**Operations.** Exactly **two tools**: `create_paprika_recipe` and `update_paprika_recipe`. Reads are
not tools — every non-trashed recipe is published as an **MCP resource** (`paprika://recipes/{uid}`,
`text/markdown`, via `Recipe.ToMarkdown()`), refreshed on a 1-minute ticker with a 10-concurrency
worker pool. `DeleteRecipe` exists on the client but is not wired to a tool.

**Auth.** `POST https://paprikaapp.com/api/v1/account/login` with a form body only (no Basic header) —
proving the Basic header is optional. Token held in memory for process lifetime; a `roundTripper`
injects `Authorization: Bearer` **and a `User-Agent`** on every request. Comment in source:
"As far as I can tell, this is a JWT with no expiration." No token persistence, no 401 retry.

**Sync/caching.** Full re-fetch of every recipe every 60 seconds. No hash comparison, no on-disk
cache. It *does* call `POST /v2/sync/notify` after writes — one of only two projects that tells
Paprika's other devices a change landed.

**Write safety — the worst in the survey.** `update_paprika_recipe` constructs a **fresh
`paprika.Recipe{}` from the ten tool arguments** and passes it to `SaveRecipe`, which gzips the whole
struct and POSTs it. Because a Paprika recipe write is a full-object replace, every field not among
those ten is transmitted as its Go zero value and **destroyed on the server**: `rating`→0,
`categories`→null, `source`, `source_url`, `image_url`, `nutritional_info`, `total_time`, `scale`,
`on_favorites`, `is_pinned`, and all four photo fields. Worse, `SaveRecipe` unconditionally calls
`recipe.updateCreated()`, which sets `created` to `time.Now()` — so **every edit also destroys the
recipe's original creation date**. There is no read-modify-write path anywhere in the client.
This is a data-loss bug on every single update, not an edge case.

**Photos.** None, and actively harmful: the `Recipe` struct carries `PhotoURL string json:"photo_url"`
and marshals it into the upload payload. `photo_url` is a **response-only** field the server fills
with a signed download link; echoing it back on write is exactly what `paprika-recipes` documents as
wrong. Combined with the clobber above, an update through this server strips a recipe's photo.

**The single best piece of code in the survey** is nonetheless here: `Recipe.updateHash()` — marshal
to a map, `delete` the `hash` key, sort keys, re-marshal, SHA-256, hex-encode.

### 1.3 `briantkatch/paprika-mcp` — Python, read/search/edit, built on a `paprika-recipes` fork

**What it is.** A thin Python MCP server (5 tools) over a **fork** of Adam Coddington's
`paprika-recipes`. The interesting engineering is inherited, not written here — and because it pins a
fork rather than upstream, it does not necessarily inherit upstream's later photo work.

**Operations.** `search_recipes` (multi-field text/regex search over name/ingredients/categories/
directions/notes, with N lines of context per match — the best search in the survey), `read_recipe`
(by id **or** exact title, with NFD unicode normalization so "café" matches "café"), `update_recipe`
(single-field **find/replace**, optionally regex, explicitly flagged DANGEROUS), `list_categories`,
`format_fraction` (local-only; renders `1/4` → `¼`, `31/200` → `³¹⁄₂₀₀`).

**Auth.** `PAPRIKA_EMAIL`/`PAPRIKA_PASSWORD` env vars → `~/.paprika-mcp/config.json` (plaintext,
chmod 0600). Deliberately *bypasses* `paprika-recipes`' keyring storage because "the process is
spawned by the AI app." Supports a configurable `PAPRIKA_USER_AGENT`, auto-detected from an installed
Paprika for Mac.

**Sync/caching.** The only MCP server surveyed with a **real on-disk cache**, inherited from
`paprika_recipes.cache.DirectoryCache`: recipe stubs (`{uid, hash}`) are always fetched fresh, then
each recipe body is served from `~/.paprika-mcp/cache/` keyed by uid and **validated by hash** —
refetched only when the hash moved. This is the two-step pattern `aarons22` documents, actually built.
Separately, categories are memoized process-lifetime into four indexes (`uid_to_name`, `name_to_uid`,
`by_uid`, `all`).

**Write safety — correct.** `update_recipe` fetches the full `RemoteRecipe` from `remote.recipes`,
mutates exactly one attribute with `setattr`, and calls `remote.upload_recipe(recipe)`. Genuine
read-modify-write: every untouched field survives because it was read back before being resent. It
also refuses to save when a category name doesn't resolve to a UID, rather than silently dropping it.

**Photos.** Excluded. `photo`, `photo_hash`, `photo_large` are absent from the tool's field enum, so
they are never edited — which is safe (read-modify-write preserves them) but means the server cannot
attach a photo to an imported recipe.

**Where it stops.** No create, no delete, no groceries, no meals, no pantry, no menus, no nutrition,
no bulk operations. `update_recipe` touches one field of one recipe per call. Prompts are supported
via a user-authored `~/.paprika-mcp/prompt.md` loaded at startup — the closest thing in the survey to
the Skills model.

### 1.4 `Syfaro/paprika-rs` — Rust client + custom API server, Postgres sync, GraphQL

**What it is.** The most *complete* and the most *inert* project of the six. A Rust `paprika-client`
crate plus a `paprika-api` server that mirrors an entire Paprika account into Postgres and exposes it
over GraphQL (juniper/actix, with `/playground` and `/graphiql`).

**Operations.** The **only project that covers Paprika's full entity surface**, all read:
`sync/status`, `sync/recipes`, `sync/recipe/{uid}`, `sync/meals`, `sync/groceries`,
`sync/groceryaisles`, `sync/menus`, `sync/menuitems`, `sync/photos`, `sync/mealtypes`, `sync/pantry`,
`sync/groceryingredients`, `sync/grocerylists`, `sync/bookmarks`, `sync/categories`. Its migrations
are effectively **a schema dump of the Paprika data model** — 14 tables plus a `recipe_category` join
table. `json_post` (gzip + multipart) is written but marked `#[allow(dead_code)]`.

**Auth.** `POST /account/login/` with a form body; `Bearer` token in default headers; the header value
is marked `set_sensitive(true)` so it is redacted from logs. Also supports constructing from a
pre-issued token, validated by calling `status()`. No token file, no 401 retry.

**Sync/caching.** By far the best sync design in the survey, and the reason to read this repo:
`check_for_updates` pulls `/sync/status`, which returns a **per-collection change counter**; each
counter is compared against a persisted `status` table and *only the collections whose counter moved
are re-fetched*. Each collection then runs a generic `update_collection<C: PaprikaId + Eq + UpdateItem>`
diff producing `Added / Changed / Deleted / Equal` sets, with `on_add`/`on_change`/`on_delete` hooks.
The whole pass runs in one Postgres transaction with `SET CONSTRAINTS ALL DEFERRED`, so a batch of
recipes and their category links commit atomically regardless of arrival order.

**Write safety.** Vacuously perfect — it never writes.

**Photos.** Metadata only. It reads `sync/photos` into a `photo` table (`uid, filename, recipe_uid,
order_flag, name, hash`) and exposes `Recipe.photos` in GraphQL. It never downloads image bytes and
never uploads. Still useful: it independently confirms the gallery-photo entity exists and its field
names.

**Where it stops.** Read-only, so no meal planning, no grocery generation, no cleanup. Requires
Postgres and a long-running server — wildly wrong shape for a non-developer. GraphQL is a query
surface for *other software*, not for a person or an agent.

### 1.5 `coddingtonbear/paprika-recipes` — Python library + `git`-flavored CLI **(the sixth project)**

**What it is.** Not an MCP server. A Python library plus a CLI that clones your Paprika account into
markdown files, lets you edit them, and pushes changes back — with a real three-way merge. Contains
`sync.py` (32 KB), `repository.py` (28 KB), `merge.py`, `markdown.py` (24 KB), `cache.py`,
`credentials.py` (keyring), `archive.py` (reads/writes `.paprikarecipes` export archives),
`images.py`, and ~130 KB of tests including a 54 KB `test_sync.py`. Commands: `pull`, `push`,
`status`, `clone`, `restore`, `create-archive`, `extract-archive`.

**Operations.** Recipes: list stubs, get by id (hash-validated), upload, add. Photos: full lifecycle
(below). Plus offline formats no one else touches — the `.paprikarecipes` export archive and
bidirectional markdown. `notify()`. No groceries, meals, pantry, menus, or categories-as-entities.

**Auth.** Notably different from every other project: `POST /api/v2/account/login/` — the **v2**
path, not v1 — with a form body only. A source comment records that Paprika's own app posts a third
field, `receipt` (its App Store purchase receipt), and that omitting it is fine because the field is
only validated when present and non-empty. Token lazily fetched and memoized. Credentials go through
**keyring**, the only project that doesn't put the user's password in a plaintext file.

**Sync/caching.** `get_recipe_index()` returns the whole account's `uid → hash` map in one request;
`get_recipe_by_id(id, hash)` serves from a pluggable `Cache` (`DirectoryCache`/`NullCache`) whenever
the hash matches, and only then hits the network. On top of that sits the real prize: `sync.py` +
`merge.py` implement a **three-way merge with a stored base copy**, so a local edit and a remote edit
to the same recipe reconcile instead of one silently winning. Nothing else in the ecosystem has any
concept of conflict.

It is also the only project with a **transport retry policy**: `requests.Session` mounted with
`urllib3 Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])`.
And the only one that checks for an `"error"` key in a **200-status** JSON body.

**Write safety — correct by construction.** `upload_recipe` takes a fully-populated `RemoteRecipe`
dataclass (every wire field is a declared field with a default), calls `update_hash()`, POSTs, then
**re-fetches and returns the server's version**. Callers obtain the object from `get_recipe_by_id`,
so read-modify-write is the only available idiom. `_recipe_upload()` additionally encodes two
spellings observed from the app's own traffic that nobody else knows: **an absent photo must be
`null`, never `""`**, and **`photo_url` must not be sent at all**.

`calculate_hash()` is `sha256(json.dumps(fields_without_hash, sort_keys=True))` — **the same
algorithm `soggycactus` derived independently in Go.** Two independent implementations agreeing is
the strongest evidence available that this is what Paprika actually does.

**Photos — the only correct implementation in existence.** Three separate mechanisms:

1. **The recipe's own thumbnail.** `upload_recipe(recipe, photo_upload=bytes)` sends the image as a
   **second multipart field named `photo_upload`, in the same request as `data`**. No other project
   knows this field exists. The caller sets `photo` to the filename and `photo_hash` to a digest of
   exactly those bytes.
2. **The gallery.** `GET /api/v2/sync/photos/` and `POST /api/v2/sync/photo/{uid}/` with a
   `RemotePhoto` (`uid, recipe_uid, filename, name, order_flag, hash, deleted`) gzipped into `data`
   plus optional `photo_upload` bytes; `deleted: true` with no bytes takes one down. The recipe's
   `photo_large` names the gallery copy.
3. **Image derivation** (`images.py`). Paprika's app never uploads a photo as-is. It sends a
   **280×280 square thumbnail** (`ImageOps.fit`) as the recipe `photo`, and a copy scaled into a
   **2048 px bounding box** as `photo_large`, both JPEG at **quality 85**, with EXIF orientation
   applied and transparency flattened onto white — and the original bytes passed through untouched
   when they already conform. This is reverse-engineered detail that would cost days to rediscover.

It also solves a problem nobody else has noticed: **`photo_url` is signed object storage with an
expiry measured in hours**, so a cached copy goes stale. `photo_download_url()` deliberately re-fetches
the recipe *around* the cache to mint a fresh signature, and `download_photo()` is a plain
unauthenticated GET (no bearer token, no JSON envelope).

**Where it stops.** Recipes and photos only. No groceries, meals, pantry, menus, or meal types — the
exact entities the plugin's differentiating features live in. It is a *recipe vault*, not a *kitchen
manager*. No nutrition parsing, no planning, no bulk operations.

### 1.6 Substitutes for the missing fifth

**`sandordaroczi/paprika-mcp-python-server`** (Python, 9 tools). `create_recipe`, `update_recipe`,
`list_recipes`, `read_recipe`, `delete_recipe`, `regenerate_recipe_image`, `search_recipes`,
`filter_recipes_by_ingredient`, `filter_recipes_by_time`. Recipes **only** — no groceries, meals,
pantry, categories. Notable for an actual `paprika-mcp setup` **wizard** that finds installed MCP
clients and writes their config (the only project taking non-developer onboarding seriously), and
AI food-photo generation via Flux/Replicate. Credentials are `PAPRIKA_USERNAME`/`PAPRIKA_PASSWORD`
env vars pasted into the client config JSON. No cache; `list_recipes` fetches bodies eagerly.

*Write safety — mostly correct, with two bugs.* The client contains **two** update methods.
`update_recipe()` builds a recipe from scratch via `_create_recipe_object()` and would clobber
exactly like `soggycactus` — but the MCP `update_recipe` tool routes to `update_recipe_partial()`,
which does GET → merge → rehash → POST. So the exposed path is safe. However: it overwrites `created`
with `datetime.now()` on every update (same bug as `soggycactus`), and its merge guard is
`if value is not None and value != ""`, which means **a field can never be cleared** — passing `""`
is silently ignored. The clobbering method remains one wiring mistake away from being live.
Its `regenerate_recipe_image` writes generated images, but through Paprika's `image_url`/recipe
payload, not the `photo_upload` mechanism.

**`mcgilly17/paprika-mcp`** (TypeScript, 10 tools). The broadest *tool* surface found in the wild:
`list_recipes`, `get_recipe`, `search_recipes`, `create_recipe`, `update_recipe`, `list_categories`,
`list_groceries`, `add_grocery_item`, `list_meals`, `add_meal`. It has a small **in-memory
hash-validated recipe cache** (`recipeCacheByUid`, compared against the stub's hash) — better than
its size suggests.

*Write safety — correct idiom, broken hash.* `updateRecipe` does
`const existing = await this.getRecipe(uid); const updated = { ...existing, ...updates, uid, hash: "" }` —
a genuine read-modify-write spread. But it then uploads with **`hash: ""`**, an empty string where
Paprika expects 64 hex characters, and never computes one. `createRecipe` does the same. The right
structure with the wrong payload. No pantry, no delete, no nutrition, no photos.

---

## 2. Write safety — the failure that most likely burned the user

A Paprika recipe update is **`POST /v2/sync/recipe/{uid}/` carrying a gzipped JSON document of the
entire recipe**. There is no PATCH. Any field absent from that document is not "left alone" — it is
overwritten with whatever you sent, or with nothing. Every project therefore has to choose between
two idioms, and the choice is invisible from the outside:

- **Read-modify-write** — GET the recipe, change the fields you mean to change, resend the whole thing.
- **Construct-and-send** — build a recipe object out of the caller's arguments and send it.

Construct-and-send is silent, permanent data loss on every call.

| Project | Idiom | Verdict | Collateral damage per update |
| --- | --- | --- | --- |
| `soggycactus` | construct-and-send | **Destroys data** | `rating`, `categories`, `source`, `source_url`, `image_url`, `nutritional_info`, `total_time`, `scale`, `on_favorites`, `is_pinned`, all four photo fields — **plus `created`, rewritten to now()** |
| `sandordaroczi` | read-modify-write (exposed path) | Safe, 2 bugs | `created` rewritten to now(); empty string can never clear a field; a clobbering `update_recipe()` sits unused in the same client |
| `mcgilly17` | read-modify-write | Safe idiom, **invalid hash** | Nothing lost, but every write ships `hash: ""` instead of 64 hex chars |
| `briantkatch` | read-modify-write | **Correct** | None |
| `paprika-recipes` | read-modify-write, enforced by the type | **Correct** | None; also re-fetches and returns the server's copy |
| `aarons22` | user supplies the whole gzipped file | N/A (offloaded) | Whatever the user omits |
| `paprika-rs` | never writes | N/A | — |

This is a strong candidate for *the* reason stitching several of these together went badly. A user
running `soggycactus` for its natural-language editing alongside anything else would watch ratings,
categories, sources and photos quietly evaporate from every recipe they touched — with no error, no
warning, and a `hash` that changed exactly as if the edit were legitimate, so the damage propagates
to every synced device. Nothing in the ecosystem previews a write, and nothing can undo one.

**Implication for the plugin:** read-modify-write is not a style preference, it is a correctness
requirement, and it must be structurally enforced (a fully-populated typed model that cannot be
partially constructed) rather than left to each call site. `created` must be preserved on update, and
`photo_url` must never be echoed back.

---

## 3. Coverage matrix

`✔` = implemented and exposed · `spec` = defined in spec/client but not usable · `–` = absent
Columns: **aar** = aarons22 · **sog** = soggycactus · **bri** = briantkatch · **rs** = Syfaro/paprika-rs ·
**san** = sandordaroczi · **mcg** = mcgilly17 · **rec** = coddingtonbear/paprika-recipes · **NEED** = the plugin

| Operation | aar | sog | bri | rs | san | mcg | rec | NEED |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| **Recipes** |
| List (uid+hash stubs) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Read full recipe | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Create | spec | ✔ | – | – | ✔ | ✔ | ✔ | ✔ |
| Update | spec | ✔ | ✔ | – | ✔ | ✔ | ✔ | ✔ |
| **Update without data loss** | n/a | **✗** | ✔ | n/a | ✔* | ✔* | **✔** | **✔** |
| Soft-delete (`in_trash`) | spec | client | – | – | ✔ | – | ✔ | ✔ |
| Text search | – | – | ✔ | – | ✔ | ✔ | – | ✔ |
| Filter by time/ingredient | – | – | – | – | ✔ | – | – | ✔ |
| Markdown round-trip | – | one-way | – | – | – | – | ✔ | ✔ |
| Export archive (`.paprikarecipes`) | – | – | – | – | – | – | ✔ | ✔ |
| **Photos** |
| Read photo metadata | – | – | – | ✔ | – | – | ✔ | ✔ |
| Download image bytes | – | – | – | – | – | – | ✔ | ✔ |
| **Upload recipe thumbnail** | – | – | – | – | – | – | **✔** | **✔** |
| **Gallery photo CRUD** | – | – | – | – | – | – | **✔** | **✔** |
| **App-identical image derivation** | – | – | – | – | – | – | **✔** | **✔** |
| Handles signed-URL expiry | – | – | – | – | – | – | ✔ | ✔ |
| Preserves photos on update | n/a | **✗** | ✔ | n/a | ✔ | ✔ | ✔ | ✔ |
| **Categories** |
| List | ✔ | – | ✔ | ✔ | – | ✔ | – | ✔ |
| Name↔UID translation | ✗ wrong | – | ✔ | ✔ | – | – | – | ✔ |
| Create / rename | – | – | – | – | – | – | – | ✔ |
| Assign to recipe | – | ✗ wipes | ✔ | – | – | ✔ | ✔ | ✔ |
| **Batch re-categorize** | – | – | – | – | – | – | – | **✔** |
| **Duplicate detection** | – | – | – | – | – | – | – | **✔** |
| **Uncategorized report** | – | – | – | – | – | – | – | **✔** |
| **Groceries** |
| List grocery lists | ✔ | – | – | ✔ | – | – | – | ✔ |
| List items | ✔ | – | – | ✔ | – | ✔ | – | ✔ |
| Add item | ✔ | – | – | – | – | ✔ | – | ✔ |
| Mark purchased / remove | – | – | – | – | – | – | – | ✔ |
| Aisles / grocery ingredients | – | – | – | ✔ | – | – | – | ✔ |
| **Build list from a meal plan** | – | – | – | – | – | – | – | **✔** |
| **Subtract pantry stock** | – | – | – | – | – | – | – | **✔** |
| **Pantry** |
| List items | ✔ guessed | – | – | ✔ | – | – | – | ✔ |
| Add / update / consume | – | – | – | – | – | – | – | **✔** |
| **Meals / menus** |
| List meal plan | ✔ | – | – | ✔ | – | ✔ | – | ✔ |
| Create meal entries | spec | – | – | – | – | ✔ | – | ✔ |
| Delete meal entry (`deleted`) | spec | – | – | – | – | – | – | ✔ |
| Meal types | – | – | – | ✔ | – | – | – | ✔ |
| Menus / menu items | – | – | – | ✔ read | – | – | – | **✔** |
| **Plan a week from library** | – | – | – | – | – | – | – | **✔** |
| **Web-search fallback** | – | – | – | – | – | – | – | **✔** |
| **Nutrition** |
| Expose `nutritional_info` string | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Parse it into numbers | – | – | – | – | – | – | – | **✔** |
| Compute at plan time | – | – | – | – | – | – | – | **✔** |
| Daily roll-up vs targets | – | – | – | – | – | – | – | **✔** |
| **Plumbing** |
| `/sync/status` counters used | reported | – | – | ✔ | – | – | – | ✔ |
| Hash-validated recipe cache | – | – | ✔ disk | ✔ pg | – | ✔ mem | ✔ disk | ✔ |
| Three-way merge / conflicts | – | – | – | – | – | – | **✔** | ✔ |
| Correct write hash | – | ✔ | ✔ | dead | ✔ | **✗ ""** | ✔ | ✔ |
| gzip request encoding | ✔ | ✔ | ✔ | dead | ✔ | ✔ | ✔ | ✔ |
| gzip response decoding | ✔ py | – | ✔ | – | – | – | ✔ | ✔ |
| Token persisted to disk | ✔ | – | ✔ | – | – | – | ✔ | ✔ |
| 401 → re-auth → retry | ✔ | – | – | – | ✔ | – | – | ✔ |
| Retry/backoff on 429/5xx | – | – | – | – | – | – | **✔** | ✔ |
| Error-in-200-body detection | – | – | – | ✔ | – | – | ✔ | ✔ |
| `User-Agent` set | – | ✔ | ✔ | – | – | – | ✔ | ✔ |
| `POST /sync/notify` after write | – | ✔ | – | – | – | – | ✔ | ✔ |
| Keyring credential storage | – | – | ✗ opt-out | – | – | – | **✔** | ✔ |
| Non-developer setup wizard | partial | – | `setup.sh` | – | ✔ | – | – | ✔ |
| Delivered as CLI (not MCP) | ✔ Go | – | – | – | ✔ aux | – | **✔** | ✔ |

`✔*` = safe on the exposed path but carries documented bugs (see §2).
Bold cells are capabilities the plugin requires that only one project — or no project — provides.

---

## 4. Gap analysis

### 4.1 The gap, stated plainly

**Every MCP server here is a transport. None is a planner. The one project that is more than a
transport is a recipe vault, not a kitchen manager.**

The five MCP servers are a thin, faithful mapping of Paprika's HTTP endpoints onto tool calls. Each
tool is one endpoint. The unit of work is "one entity, one call." Whatever intelligence exists lives
in the LLM's head at call time and is discarded when the conversation ends. `paprika-recipes` breaks
that mould — it has a real domain model, a merge engine, and a photo pipeline — but it deliberately
scopes itself to recipes and photos and touches none of the meal-planning entities.

Consequently, **every capability that requires reading two different entity types and reasoning across
them is missing from all six**:

1. **Grocery list minus pantry.** Requires `meals` → `recipe.ingredients` (a newline-delimited
   *string*) → parsed quantities → matched against `pantry_item.ingredient`/`in_stock`/`quantity` →
   written to `grocery_item`. Four entities, one unit-aware ingredient parser, one fuzzy matcher.
   **Zero projects touch it.** `paprika-rs` can *read* all four and does nothing with them; the rest
   cannot read the pantry at all.
2. **Nutrition.** `nutritional_info` is a **free-text string**, and all six pass it through verbatim.
   Nobody parses it, normalizes per-serving vs per-recipe, scales by `servings`/`scale`, or sums a
   day. "Nutrition computed at plan time, rolled up daily against targets" is 100% greenfield.
3. **Weekly planning.** Two projects can *write* a meal entry. None *chooses* what goes in the slot —
   no constraint satisfaction over the library (variety, recency, category balance, nutrition
   targets), and no fallback to web search plus recipe import when the library can't fill a slot.
4. **Bulk library operations.** Closest prior art is `briantkatch`'s one find/replace on one field of
   one recipe. Batch re-categorization across hundreds of recipes, duplicate detection (which needs
   normalized-title + ingredient-set similarity — the API `hash` changes on any edit and is useless
   for near-duplicates), and an uncategorized report do not exist.
5. **Menus and pantry writes.** Paprika has a first-class saved-menu concept (`menu`, `menu_item`
   with `day` and `type_uid`). Only `paprika-rs` reads them; **nothing writes them, and nothing
   writes the pantry either.** Both are in the plugin's CRUD baseline, so both are unimplemented
   prior art across the entire ecosystem.
6. **Safety on writes.** Every write in the survey is fire-and-forget. Nothing previews a batch,
   nothing is re-runnable, nothing can undo — and as §2 shows, one popular server actively destroys
   data on every update. For an operation that rewrites 200 recipes' categories, that is
   disqualifying.

### 4.2 Photos: a confirmed ecosystem-wide gap outside one project

Cross-checked with issue #9 and verified in source. Of the five MCP servers, **not one can attach a
photo to a recipe**:

- `aarons22` — no `/photos` path in the OpenAPI spec, no `photo_upload` concept anywhere.
- `soggycactus` — no photo support, *and* wipes all four photo fields on every update, *and*
  echoes the response-only `photo_url` back on write.
- `briantkatch` — photo fields excluded from the editable enum; preserved but never settable.
- `paprika-rs` — reads gallery metadata into Postgres; never downloads or uploads bytes.
- `sandordaroczi` — generates AI images but routes them through the recipe payload, not
  `photo_upload`.
- `mcgilly17` — sets `photo_hash: null` on create and never touches photos again.

Only `coddingtonbear/paprika-recipes` implements it, and it implements it *thoroughly*: the
`photo_upload` multipart sibling field, the separate `/sync/photo/{uid}/` gallery endpoint, the
`null`-not-`""` spelling, the response-only `photo_url` exclusion, signed-URL expiry handling, and
byte-exact reproduction of the app's own 280 px / 2048 px / JPEG-q85 / EXIF-transposed derivation.

This matters directly: the plugin imports recipes from the web via search fallback, and an imported
recipe that loses its photo looks broken in the app. Reimplementing this from scratch means
reverse-engineering multipart field names and image dimensions from app traffic — days of work that
is already done, tested (`tests/test_images.py`), and documented in source comments.

### 4.3 The delivery-shape gap

Five of six are **MCP servers**. The plugin is a **Python CLI driven through Claude Code Skills**.
That difference is not cosmetic:

- MCP tool schemas are consumed by the model every turn; a multi-step plan burns context on
  round-trips. A Skill hands the model one procedure and one CLI, and the CLI does the cross-entity
  work deterministically in-process.
- MCP servers must be registered in a client config JSON with credentials pasted inline. Two of the
  six store the user's Paprika **password in a JSON blob a chat client reads**. For a non-developer
  that is both hostile to set up and bad security. Only `paprika-recipes` uses keyring.
- Nothing in the survey composes. `soggycactus` re-fetches every recipe every 60 seconds; running it
  alongside `briantkatch` means two independent caches, two logins, two views of truth — and, per §2,
  one of them silently deleting fields the other just wrote. This is precisely the "stitch several
  together and still lack what you need" failure, and it is worse than lacking: it is destructive.

The one MCP-free CLI, `aarons22`'s Go binary, is machine-generated: it cannot gzip your payload,
does not decompress responses, does not refresh tokens, and carries auto-pagination code for an API
with no pagination.

### 4.4 The correctness gap

Nobody has written down the API's actual behaviour *correctly and completely* in one place. Merged
across sources (§5) the picture is consistent — but each individual project is wrong about at least
one thing, and several of the wrong things live in the OpenAPI spec everyone would naturally trust.

---

## 5. API landmines (merged and corrected across all six — do not re-learn these the hard way)

**Writes and data integrity**

1. **A recipe write is a full-object replace.** Omitted fields are destroyed. Always read-modify-write.
   See §2 for who gets this wrong.
2. **Preserve `created` on update.** Two projects overwrite it with `now()` on every save.
3. **Recipe writes require a valid 64-char hex `hash`, recomputed on every change.** The algorithm —
   independently derived in Go by `soggycactus` and in Python by `paprika-recipes` — is:
   serialize to a map, drop `hash`, `json.dumps(..., sort_keys=True)`, SHA-256, hex. `mcgilly17`
   ships `hash: ""` and is wrong.
4. **Bulk `POST /v2/sync/recipes/` returns 500.** Write recipes one at a time to
   `POST /v2/sync/recipe/{uid}/`. Groceries and meals *do* accept arrays.
5. **All writes are gzipped JSON in a `multipart/form-data` field named `data`.** Confirmed
   identically across Python `requests`, `aiohttp`, Go `mime/multipart`, Rust `reqwest`, and Node.
6. **Nothing truly deletes.** Recipes: `in_trash: true`. Groceries: `purchased: true`. Meals:
   `deleted: true`. Photos: `deleted: true`. `DELETE /v2/sync/groceries/{uid}` returns 404.
7. **UIDs are client-generated uppercase UUID4**, e.g. `E22C871B-35AA-46E3-97AC-40ABCADFACDE`.

**Photos**

8. **A new photo's bytes ride in a second multipart field, `photo_upload`, in the same POST as
   `data`.** Set `photo` to the filename and `photo_hash` to a digest of exactly those bytes.
9. **An absent photo field must serialize as `null`, never `""`.**
10. **`photo_url` is response-only — never send it.** `soggycactus` does.
11. **`photo_url` points at signed object storage that expires in hours.** Re-fetch the recipe around
    your cache to mint a fresh link; download it with a plain GET (no bearer token, no JSON envelope).
12. **Gallery photos are a separate entity**: `GET /api/v2/sync/photos/`,
    `POST /api/v2/sync/photo/{uid}/`, fields `uid, recipe_uid, filename, name, order_flag, hash,
    deleted`. The recipe's `photo_large` names the gallery copy.
13. **Match the app's derivation**: 280×280 square-fit JPEG for `photo`; original scaled into a
    2048 px bounding box for `photo_large`; JPEG quality 85; EXIF orientation applied; transparency
    flattened onto white; pass conformant JPEGs through untouched.

**Schema traps**

14. **`recipe.categories` is a list of category UIDs, not names.** `aarons22`'s `openapi.yaml` says
    *"List of category names (not UIDs)"* with `example: ["Breakfast", "Baking"]`, and its
    `list_categories` docstring repeats it. Contradicted by `briantkatch` (which translates UID↔name
    in both directions), `soggycactus`'s `Categories []string`, `mcgilly17` ("New category UIDs"), and
    decisively by `paprika-rs`'s `recipe_category(recipe_uid, category_uid REFERENCES category(uid))`.
    **Trust the code, not the spec.**
15. **The individual recipe path is singular: `/v2/sync/recipe/{uid}/`.** `aarons22`'s spec normalizes
    it to plural `/recipes/{uid}/` "for a consistent CLI experience" and asserts "the effective URL is
    identical." It is not — against the spec's own `servers:` base of `.../api/v2/sync` it resolves to
    `/v2/sync/recipes/{uid}/`. Generate a client from that spec verbatim and every single-recipe call
    404s.
16. **`aarons22`'s `PantryItem` schema is guessed** — annotated *"endpoint confirmed from database
    schema analysis."* It lists `{uid, name, ingredient, quantity, purchased, aisle, order_flag}`.
    `paprika-rs`, which actually consumed the endpoint, records `{uid, ingredient, aisle,
    expiration_date, has_expiration, in_stock, purchase_date, quantity, aisle_uid}` — **no `name`, no
    `purchased`; `in_stock` and expiry dates instead.** Pantry subtraction depends on `in_stock` and
    `quantity`. Use paprika-rs's shape.
17. **`on_grocery_list` is typed inconsistently** (`string|null` in the OpenAPI schema, `BOOLEAN NOT
    NULL` in paprika-rs, `bool` in soggycactus, `str | None` in paprika-recipes). Treat as untrusted.
18. **Recipe updates must send every field** — empty strings for unused text, `false` for booleans,
    `0` for rating, `[]` for categories (but `null` for photo fields, per #9).
19. **Meal `type` is an int: 0=Breakfast, 1=Lunch, 2=Dinner, 3=Snack.** Dates are
    `"YYYY-MM-DD HH:MM:SS"`, not ISO-8601. `recipe_uid` may be null for a text-only meal.
20. **Leave `aisle` empty on new grocery items** — the server auto-assigns.

**Transport and auth**

21. **Two login paths exist and both work**: `POST /api/v1/account/login/` (four projects) and
    `POST /api/v2/account/login/` (`paprika-recipes`). A bare form body suffices; the Basic auth
    header `aarons22` also sends is belt-and-braces. The app posts a third field `receipt` (its App
    Store receipt); omitting it is fine, since it is only validated when present and non-empty.
22. **Some responses are gzipped without advertising it.** Sniff `\x1f\x8b` before parsing.
23. **Errors can arrive with HTTP 200 and an `"error"` key in the JSON body.** Only `paprika-rs` and
    `paprika-recipes` check.
24. **The token appears to be a non-expiring JWT** — implement 401 → re-auth → retry anyway.
25. **Retry 429/500/502/503/504 with backoff** on both GET and POST (`paprika-recipes`' policy:
    `total=5, backoff_factor=1`). Nobody else does.
26. **`POST /v2/sync/notify/`** (no body) after writes prompts other devices to sync.
27. **Set a plausible `User-Agent`.** Three projects do so deliberately; `briantkatch` auto-detects it
    from an installed Paprika for Mac.
28. **There is no pagination.** Every list endpoint returns everything.

---

## 6. Copy this / skip this

### 6.1 Copy outright

| # | What | From | Why |
| --- | --- | --- | --- |
| 1 | **The whole photo pipeline**: `photo_upload` multipart sibling field, `/sync/photo/{uid}/` gallery endpoint, `null`-not-`""`, `photo_url` exclusion, signed-URL refresh, and the 280 px / 2048 px / q85 / EXIF derivation. | `coddingtonbear/paprika-recipes` `remote.py` + `images.py` + `tests/test_images.py` | **The only implementation that exists.** Reproducing it means reverse-engineering multipart field names and image dimensions from app traffic. Imported web recipes keep their photos or they look broken. |
| 2 | **Read-modify-write enforced by the type**: a fully-populated recipe dataclass with every wire field declared, obtainable only by reading, with `update_hash()` on the way out and a re-fetch on the way back. | `paprika-recipes` `RemoteRecipe` / `upload_recipe`; `briantkatch` for the MCP-side idiom | §2. This is the difference between a tool and a data-loss incident. Make partial construction impossible rather than discouraged. |
| 3 | **The recipe write hash**: drop `hash`, `sort_keys=True`, SHA-256, hex. | `soggycactus` `updateHash()` **and** `paprika-recipes` `calculate_hash()` — independently derived, identical | Two independent agreeing implementations is the strongest correctness evidence available. ~6 lines in Python. |
| 4 | **Per-collection change-counter sync**: read `/sync/status`, persist each collection's counter, re-fetch only collections whose counter moved; diff into Added/Changed/Deleted/Equal with per-state hooks; commit a pass in one transaction with deferred constraints. | `Syfaro/paprika-rs` `updates.rs` (`check_for_updates`, `update_collection<C>`) | The correct sync architecture, proven across all 14 collections. Port the algorithm; swap Postgres for SQLite. Bulk cleanup and duplicate detection need a full local mirror and this keeps one cheap. |
| 5 | **Hash-validated per-recipe disk cache** + `get_recipe_index()` (whole-account `uid→hash` in one request). | `paprika-recipes` `cache.DirectoryCache` / `remote.py`, as used by `briantkatch` | The right cache granularity. Layer with #4: status counter gates the stub fetch, hash gates the body fetch. |
| 6 | **Three-way merge against a stored base copy.** | `paprika-recipes` `sync.py` + `merge.py` (+ its 54 KB `test_sync.py`) | The only conflict handling in the ecosystem. A local mirror that can be edited offline needs this the first time a phone edit races a CLI edit. |
| 7 | **The auth block**: form-body login → `result.token` → Bearer; token cached 0600; **401 → clear → re-auth → retry once**. | `aarons22` `client.py` (~60 lines) | Only complete 401 handling in the survey. Copy it, then swap credential storage for #8. |
| 8 | **Keyring-backed credential storage.** | `paprika-recipes` `credentials.py` | Five of six store the password in plaintext JSON/TOML. For a non-developer this is the one security decision worth getting right on day one. |
| 9 | **Session-level retry/backoff and error-in-200-body detection.** | `paprika-recipes` `Remote.__init__` / `_request` | `Retry(total=5, backoff_factor=1, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","POST"])`, plus checking for an `"error"` key on a 200. Nobody else survives a flaky Paprika. |
| 10 | **gzip+multipart write envelope and the `\x1f\x8b` response sniff.** | `aarons22` `client.py` | Five independent implementations agree; no reason to rediscover. |
| 11 | **`POST /sync/notify/` after every write batch, and a set `User-Agent`.** | `soggycactus`, `paprika-recipes` | Two one-liners that make writes actually appear on the user's phone and reduce bot-detection risk. |
| 12 | **The Paprika data model as a schema.** | `paprika-rs` `migrations/*.up.sql` | 14 tables + join table = the whole entity graph, including `menu`, `menu_item`, `meal_type`, `aisle`, `grocery_ingredient`, `bookmark`, `photo`. Transcribe into the local SQLite mirror. Use **its** `pantry_item` shape, not the OpenAPI guess. |
| 13 | **Multi-field search with context lines + NFD title matching.** | `briantkatch` `utils.search_in_text`, `read_recipe` | Small, correct, immediately useful. NFD normalization is a bug you would otherwise ship. |
| 14 | **A real setup wizard** that prompts for credentials, verifies login, and writes config — no hand-edited JSON. | `sandordaroczi` `setup_wizard.py`, `briantkatch` `setup.sh` | The brief says non-developer. Two projects show any awareness of that. |
| 15 | **The `.paprikarecipes` archive reader/writer and markdown round-trip.** | `paprika-recipes` `archive.py`, `markdown.py` | Free import/export and a plausible bulk-edit surface for a non-developer ("edit these 40 files, push"). |
| 16 | **Unicode fraction rendering** (`1/4`→`¼`). | `briantkatch` `tools/format_fraction.py` | Free polish for generated grocery lists and scaled recipes. |
| 17 | **The corrected landmine list (§5).** | merged, all six | Field notes worth more than any single project's code. |

### 6.2 Skip / do not reinvent from

| What | Why |
| --- | --- |
| **`aarons22`'s `openapi.yaml` as a client-generation source.** | Two breaking errors — plural `/recipes/{uid}/` (every single-recipe call 404s) and "categories are names" (every category edit breaks) — plus a guessed `PantryItem` missing `in_stock`, the field pantry subtraction depends on, plus no photo endpoints at all. Read it for the field inventory; hand-write the client. Do **not** run a generator over it. |
| **`soggycactus`'s write path — the whole of it.** | Construct-and-send: destroys `rating`, `categories`, `source`, `nutritional_info`, all photo fields, and rewrites `created` on every update, silently, on every synced device. Copy its `updateHash()`. Discard everything else about how it writes. |
| **`soggycactus`'s 60-second full-library re-fetch.** | The exact anti-pattern the status counters exist to prevent. |
| **`mcgilly17`'s upload payload.** | Right idiom (spread over a read), invalid payload (`hash: ""`). Take the idiom, compute the hash. |
| **`sandordaroczi`'s `update_recipe()` client method** (as opposed to `update_recipe_partial`). | A clobbering construct-and-send sitting unused one wiring mistake away from being live. Also: don't copy its `if value != ""` merge guard — it makes clearing a field impossible — or its `created` rewrite. |
| **The generated Go CLI.** | Dead auto-pagination for a non-paginated API, no gzip either leg, no 401 handling, writes require the user to pre-gzip a file. A 12 MB binary committed to the repo. |
| **MCP-resource-per-recipe.** | Wrong shape for a CLI+Skills plugin, and it forces a full library fetch at startup. |
| **GraphQL / a long-running server / Postgres.** | `paprika-rs`'s deployment model is a query surface for other software. The plugin's user is a person with a laptop. Take the sync algorithm, leave the actix/juniper/Postgres stack. |
| **Find/replace as the primary edit primitive.** | `briantkatch`'s `update_recipe` is a clever workaround for not modeling the recipe. With a typed model and a local mirror, edit fields directly and make batch operations first-class and previewable. |
| **AI image generation.** | `sandordaroczi`'s Flux integration is orthogonal to the brief, adds a paid dependency, and is not in the requirements. Real photo *upload* (§6.1 #1) is the requirement. |
| **Password-in-client-config credential flow.** | Adopted by `briantkatch` and `sandordaroczi` because MCP stdio made it convenient. A CLI has no such excuse. |
| **Depending on any of them at runtime.** | `paprika-recipes` is the only one mature enough to depend on, and doing so buys sync + merge + cache + keyring + photos at the cost of inheriting its recipe-only model (no groceries, meals, pantry, menus — the entities the plugin's differentiating features live in). Note `briantkatch` pins a *fork*, so it may not track upstream's photo work. **Recommendation: vendor/port its patterns into a first-party client covering all 14 collections, rather than either depending on it or ignoring it.** |

### 6.3 What must be built from nothing

No prior art exists for any of these. Budget accordingly — this is the actual product.

1. Ingredient-line parser (quantity + unit + name) over `recipe.ingredients` free text.
2. Ingredient normalization/matching for pantry subtraction and duplicate detection.
3. `nutritional_info` free-text → structured nutrients, scaled by `servings`/`scale`.
4. Daily nutrition roll-up against user targets.
5. Weekly-plan selection over the library (variety, recency, category balance, nutrition constraints).
6. Web-search fallback + recipe import for unfilled slots — **including photo capture**, which only
   §6.1 #1 makes possible.
7. Plan → grocery list generation with pantry subtraction and aisle grouping.
8. Duplicate detection by normalized title + ingredient-set similarity (**not** the API `hash`).
9. Batch operations with dry-run, preview, idempotent re-run, and undo.
10. Menu / menu-item writes — nothing in the ecosystem writes these.
11. Pantry writes — nothing in the ecosystem writes these either.
12. The Skills layer: procedures a non-developer invokes in natural language over a deterministic CLI.

---

## 7. Bottom line

The six projects collectively solve **transport**, and solve it well enough that re-solving it is
waste. Between `aarons22`'s auth+gzip client, the `soggycactus`/`paprika-recipes` agreeing hash
algorithm, `paprika-recipes`' photo pipeline, cache, merge engine, keyring and retry policy, and
`paprika-rs`'s change-counter sync and complete schema, a correct, complete, cached, photo-capable
Paprika client for **all 14 collections** can be assembled from existing verified code in days rather
than weeks.

Not one of them solves **domain reasoning across entities**. Meal planning, pantry-aware grocery
generation, nutrition roll-up, and bulk library hygiene are absent from every project — because each
MCP server is built as one-tool-per-endpoint, which structurally cannot express an operation that
reads meals, recipes, and pantry and writes groceries. That is the gap, and it is the whole plugin.

And the reason stitching several of these together didn't merely fall short but actively hurt: a
recipe update is a full-object replace, and the most convenient natural-language editor in the set
sends a freshly-constructed object every time. Ratings, categories, sources, creation dates and
photos disappear silently, with a legitimately-changed hash, propagated to every device. **Write
safety is the first requirement, not a polish item.**
