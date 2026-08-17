# Research: The Paprika v2 Sync API Surface

> Resolves wayfinder ticket #4.
> Researched 2026-08-16. All findings are from published reverse-engineering artifacts
> and open-source client code. **No live API calls were made and no credentials were used.**

## 1. Scope and source ranking

Paprika Recipe Manager has **no official API and no official documentation**. Everything below
is reconstructed from reverse engineering. Sources are ranked by how directly they evidence
real server behaviour:

| Rank | Source | Nature of evidence | Trust |
|---|---|---|---|
| A | [`coddingtonbear/paprika-recipes`](https://github.com/coddingtonbear/paprika-recipes) (`remote.py`, `recipe.py`, `sync.py`, `constants.py`, `images.py`) | Mature, actively-maintained Python client with a full bidirectional sync engine, photo upload, and prose comments recording observed app traffic | Highest |
| A | [`Syfaro/paprika-rs`](https://github.com/Syfaro/paprika-rs) (`paprika-client/src/lib.rs`) | Typed Rust client with an integration test per endpoint, run against a real account | Highest (for GET surface + field types) |
| B | [`aarons22/paprika-tools`](https://github.com/aarons22/paprika-tools) (`openapi.yaml`, `API_REFERENCE.md`) | OpenAPI 3.0.3 spec + request/response log; several notes marked "verified live 2026-06-29" | High, but partly derived from other docs rather than traffic (see §8) |
| B | [`soggycactus/paprika-3-mcp`](https://github.com/soggycactus/paprika-3-mcp) (`internal/paprika/client.go`) | Working Go client incl. write path and `notify` | High |
| C | [`johnwbyrd/kappari`](https://github.com/johnwbyrd/kappari) (`api.md`, `endpoints.md`, `authentication.md`, `encoding.md`, `patterns.md`, `sqlite.md`, `schema.md`) | Windows-app binary + HTTPS-capture analysis; authoritative on wire encoding, licensing/auth and the local SQLite cache; explicitly incomplete on endpoints (many entries are TODO) | High for encoding/auth, low for endpoint completeness |
| C | [mattdsteele gist](https://gist.github.com/mattdsteele/7386ec363badfdeaad05a418b9a1f30a) + its comment thread | Original 2018 v1 reverse engineering, plus a long comment thread that documents most of the v2 write surface | Medium (age; comments unverified individually) |
| D | [`briantkatch/paprika-mcp`](https://github.com/briantkatch/paprika-mcp) | Thin wrapper over `paprika-recipes`; useful only as corroboration on category representation | Low (derivative) |

**Everything in this document is "confirmed" only in the sense that at least one independent
client depends on it in production. Nothing is vendor-guaranteed and all of it can break with
any Paprika release.**

---

## 2. Base URLs, versions, and the User-Agent gate

```
https://www.paprikaapp.com/api/v1/...   # legacy; login + a Basic-auth sync mirror
https://www.paprikaapp.com/api/v2/...   # current; used by Paprika 3
```

Three cross-cutting facts that affect every request:

1. **`www.` matters inconsistently.** `paprika-recipes` and `paprika-tools` use
   `www.paprikaapp.com`; `paprika-3-mcp` uses bare `paprikaapp.com` and works. Prefer `www.`.
2. **Trailing slashes are load-bearing.** Every path in every client ends in `/`. Treat a
   missing trailing slash as a likely 404.
3. **The v2 API gates on `User-Agent`.** This is the single most important undocumented
   behaviour and it is easy to miss:

   > `paprika_recipes/constants.py`: *"The v2 API answers `{"error": {"message": "Unrecognized client."}}` — with a 200, not a 4xx — to any request whose User-Agent it does not recognise, and what it recognises is the string Paprika's own iOS app sends. The match is on a prefix, so appending our own name and version still gets in."*

   The known-good prefix, as of `paprika-recipes` at time of writing:

   ```
   Paprika 3/3.8.5 (com.hindsightlabs.paprika.ios.v3; build:80; iOS 26.5.2) Alamofire/5.2.2
   ```

   kappari observed the Windows app's equivalent:
   `Paprika Recipe Manager 3/3.3.1 (Microsoft Windows NT 10.0.26100.0)`.
   The **v1 login endpoint has no User-Agent check**, which is why several clients log in via
   v1 and then use the token against v2. `paprika-3-mcp` sends `paprika-3-mcp/<ver> (golang; ...)`
   and reportedly works against v2 sync GETs — so the gate may apply only to some routes, or may
   have been added after that client was written. **Treat as: send an app-prefixed UA always.**

### Response envelope

Success: `{"result": <payload>}` where payload is an object, an array, or the bare boolean `true`.
Error: `{"error": {"code": <int>, "message": "<string>"}}`.

**Errors are frequently returned with HTTP 200.** `paprika-3-mcp` comments: *"The Paprika API is
very inconsistent with how it returns errors; sometimes a successful status code can be returned
but an error is still returned in the body."* A client MUST inspect the body for an `error` key
regardless of status code.

### Compression

- **Responses** may or may not be gzipped. Clients sniff for the `1f 8b` magic bytes and
  decompress conditionally rather than trusting `Content-Encoding`.
- **Request bodies for all sync writes are mandatorily gzipped JSON**, delivered as
  `multipart/form-data` with the field name `data` (as a *file* part, `filename=file`).
  kappari's capture of the exact part headers:

  ```
  --{uuid-boundary}
  Content-Disposition: form-data; name=data; filename=file; filename*=utf-8''file

  {gzip bytes}
  --{uuid-boundary}--
  ```

  kappari notes the app writes `Content-Type` *before* `Content-Disposition` and uses unquoted
  field names (`name=data`, not `name="data"`). No client reports this being required; standard
  multipart encoders (Python `requests`, Go `mime/multipart`, Rust `reqwest`) all work.
- **No pagination exists anywhere.** Collection GETs return the entire account's set of that
  entity in one response. (`paprika-tools` ships a generic `pagination.go`, but no Paprika
  endpoint is configured to use it.)
- **No CORS headers**, so the API cannot be called from a browser.

---

## 3. Endpoint table

Legend for **Status**:
- **Confirmed** — at least one independent client exercises it against the live API.
- **Community** — documented in the gist comment thread or kappari captures; not exercised by
  a client I read.
- **Inferred** — symmetry argument only; not observed anywhere. Do not build on these without testing.
- **Known-broken** — observed to fail.

All sync paths are relative to `https://www.paprikaapp.com`. All require
`Authorization: Bearer <token>` except the two login endpoints and the web clipper.

### Authentication

| Method | Path | Purpose | Status |
|---|---|---|---|
| POST | `/api/v1/account/login/` | Email + password → JWT. No UA check, no license/receipt needed. The portable path. | Confirmed (kappari, paprika-tools, paprika-3-mcp) |
| POST | `/api/v2/account/login/` | Same, but gated on User-Agent and (historically) a purchase receipt. | Confirmed (paprika-recipes, paprika-rs) |

### Sync — reads (collection GETs, whole-account)

| Method | Path | Returns | Status |
|---|---|---|---|
| GET | `/api/v2/sync/status/` | Change-counter object for all 13 entity types | Confirmed |
| GET | `/api/v2/sync/recipes/` | Array of `{uid, hash}` **stubs only** — not full recipes | Confirmed |
| GET | `/api/v2/sync/recipe/{uid}/` | One full recipe object (note: **singular** `recipe`) | Confirmed |
| GET | `/api/v2/sync/categories/` | Array of categories | Confirmed |
| GET | `/api/v2/sync/meals/` | Array of meal-plan entries (whole history, undated-filtered) | Confirmed |
| GET | `/api/v2/sync/mealtypes/` | Array of meal-type definitions | Confirmed (paprika-rs) |
| GET | `/api/v2/sync/groceries/` | Array of grocery items across **all** lists | Confirmed |
| GET | `/api/v2/sync/grocerylists/` | Array of grocery lists | Confirmed |
| GET | `/api/v2/sync/groceryaisles/` | Array of aisles | Confirmed (paprika-rs) |
| GET | `/api/v2/sync/groceryingredients/` | Array of canonical ingredient→aisle mappings | Confirmed (paprika-rs) |
| GET | `/api/v2/sync/pantry/` | Array of pantry items | Confirmed (paprika-rs) |
| GET | `/api/v2/sync/menus/` | Array of menus | Confirmed (paprika-rs) |
| GET | `/api/v2/sync/menuitems/` | Array of menu items | Confirmed (paprika-rs) |
| GET | `/api/v2/sync/photos/` | Array of gallery photo objects (all recipes) | Confirmed (paprika-recipes) |
| GET | `/api/v2/sync/bookmarks/` | Array of web bookmarks | Confirmed (paprika-rs) |

### Sync — writes

All writes are `POST` + `multipart/form-data` + gzipped-JSON `data` field, and return
`{"result": true}`.

| Method | Path | Body shape | Purpose | Status |
|---|---|---|---|---|
| POST | `/api/v2/sync/recipe/{uid}/` | gzipped **single object** | Create or update one recipe. Optional second multipart part `photo_upload` carrying JPEG bytes. | Confirmed |
| POST | `/api/v2/sync/photo/{uid}/` | gzipped **single object** (+ optional `photo_upload` part) | Create/replace/delete one gallery photo | Confirmed (paprika-recipes) |
| POST | `/api/v2/sync/groceries/` | gzipped **array** | Create/update grocery items in bulk | Confirmed |
| POST | `/api/v2/sync/meals/` | gzipped **array** | Create/update meal-plan entries in bulk | Confirmed (paprika-tools, "verified live 2026-06-29") |
| POST | `/api/v2/sync/menuitems/` | gzipped **array** | Create/update/soft-delete menu items | Confirmed (kappari traffic capture) |
| POST | `/api/v2/sync/categories/` | gzipped **array** (`uid`, `name`, `order_flag`, `parent_uid`, `deleted`) | Create/rename/delete categories | Community (gist thread) |
| POST | `/api/v2/sync/notify/` | empty body | Tells all of the user's running Paprika clients to pull. Fire-and-forget. | Confirmed (paprika-recipes, paprika-3-mcp) |
| POST | `/api/v2/sync/grocerylists/` | array (presumed) | Manage grocery lists | Inferred |
| POST | `/api/v2/sync/groceryaisles/` | array (presumed) | Manage aisles | Inferred |
| POST | `/api/v2/sync/pantry/` | array (presumed) | Manage pantry | Inferred |
| POST | `/api/v2/sync/menus/` | array (presumed) | Manage menus | Inferred |
| POST | `/api/v2/sync/mealtypes/` | array (presumed) | Manage meal types | Inferred |
| POST | `/api/v2/sync/bookmarks/` | array (presumed) | Manage bookmarks | Inferred |

### Known-broken / absent

| Method | Path | Observed behaviour |
|---|---|---|
| DELETE | `/api/v2/sync/groceries/{uid}` | `404`. **There is no DELETE verb anywhere in this API.** |
| POST | `/api/v2/sync/meals/{uid}/` | `404 Not found.` Meals have no per-uid write route; always POST the array. |
| POST | `/api/v2/sync/recipes/` (plural) | `500` when used to create recipes. Use the singular per-uid route. |

### Legacy v1 mirror (HTTP Basic auth, no bearer token)

Documented in the 2018 gist and still reported working by kappari. Useful mainly as a fallback.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/sync/{recipes,categories,groceries,meals,bookmarks}/` | Basic auth with the cloud-sync email/password |
| GET | `/api/v1/sync/recipe/{uid}/` | Basic auth |
| POST | `/api/v1/sync/recipe/{uid}/` | Basic auth, gzipped `data` field |

### Web clipper (distinct from the sync API)

| Method | Path | Purpose | Status |
|---|---|---|---|
| POST | `/api/v1/sync/recipes/` | **Recipe scraper**, not a bulk write. Multipart with `url` (text/plain), `html` (gzipped page HTML, filename `recipe.html`), `styles` (gzipped JSON of page styles, filename `styles.json`). Returns `{"result": {name, ingredients, directions, notes, nutritional_info, prep_time, cook_time, total_time, servings, difficulty, image_url}}` — a parsed recipe with **no uid and no hash**, which the client then assigns and POSTs to the sync API. Reported as requiring **no auth**. | Community (gist, 2018) |

This endpoint is very likely what the "`POST /v2/sync/recipes/` returns 500" note is actually
colliding with: `recipes/` (plural) is the scraper's route, not a bulk-recipe route.

**Endpoint count: 25 distinct routes documented** — 15 authenticated collection/item reads,
7 sync writes (including `notify`), 2 login routes, 1 web clipper, plus a 6-route v1 Basic-auth
mirror and 6 further writes that are inferred-only.

---

## 4. Recipe object schema

The recipe is the only entity with a two-tier representation.

**`GET /v2/sync/recipes/` returns stubs only:**

| Field | Type | Notes |
|---|---|---|
| `uid` | string | Uppercase UUID4 |
| `hash` | string | 64-char hex sync token |

**Full recipe object** (`GET /v2/sync/recipe/{uid}/` → `result`):

"Writable" = the server persists what you send in the gzipped upload body.

| Field | Type | Writable | Notes |
|---|---|---|---|
| `uid` | string | Yes (identity) | Uppercase UUID4, **client-generated**. Immutable once created; it is also the photo directory name. |
| `name` | string | Yes | Recipe title. Effectively required. |
| `ingredients` | string | Yes | One ingredient per line, `\n`-separated. Not a list. |
| `directions` | string | Yes | Steps, `\n`-separated (app uses `\n\n` between paragraphs). Not a list. |
| `description` | string \| null | Yes | Summary. kappari notes the local DB column doubles as notes storage; null in most rows. |
| `notes` | string | Yes | Free text. `paprika-rs` types this non-optional `String` while everything else allows empty/null. |
| `nutritional_info` | string | Yes | Free text, newline-separated `Key: value` pairs in practice. **Absent from `paprika-rs`'s model** — see §8. |
| `servings` | string | Yes | Free text ("12 muffins", "One serving"). Never numeric. |
| `difficulty` | string | Yes | Free text. The app offers Easy/Medium/Hard but does not enforce it. |
| `prep_time` | string | Yes | Free text ("15 min", "20 mins."). |
| `cook_time` | string | Yes | Free text. |
| `total_time` | string | Yes | Free text; observed as bare `"35"` in real data. |
| `rating` | int | Yes | 0 = unrated, 1–5 stars. |
| `categories` | array of string | Yes | **Category UIDs, not names.** See §8 — this is the single biggest source disagreement. |
| `source` | string | Yes | Attribution ("New York Times"). |
| `source_url` | string | Yes | Original URL. |
| `image_url` | string | Yes | External image URL (from web import). Distinct from `photo_url`. |
| `photo` | string \| null | Yes | Filename of the recipe's square thumbnail. **Must be `null`, never `""`, on upload.** |
| `photo_hash` | string \| null | Yes | Uppercase SHA256 hex of the thumbnail's *bytes*. Must be `null` when there is no photo. |
| `photo_large` | string \| null | Yes | Filename of the gallery-sized copy. Must be `null` when absent. |
| `photo_url` | string \| null | **No — read-only** | Pre-signed object-storage URL. `paprika-recipes` strips it from uploads entirely. **Expires within hours**; re-fetch the recipe to mint a fresh one. |
| `hash` | string | Yes (and required) | 64-char hex sync token. See §6 — you must supply one, but the server's stored value is not reproducible client-side. |
| `created` | string | Yes | `"YYYY-MM-DD HH:MM:SS"`, UTC, space-separated — **not ISO 8601**. |
| `on_favorites` | bool | Yes | Favorited. Older v1 payloads used `0`/`1`. |
| `on_grocery_list` | **disputed** | Yes | `bool` in `paprika-rs` and `paprika-3-mcp`; `str \| None` in `paprika-recipes` and the OpenAPI spec. See §8. |
| `in_trash` | bool | Yes | **The only delete mechanism.** Setting `true` moves to app trash; emptying trash requires the app UI. |
| `is_pinned` | bool | Yes | Quick-access marker. |
| `scale` | string \| null | Yes | Serving-scale factor. Null in essentially all observed data. |
| `deleted` | bool | Legacy | Present in the 2018 v1 payload and in every *other* entity type. Not part of the v2 recipe object — recipes use `in_trash`. |

**Fields that exist only in the local SQLite cache and are never on the wire** (kappari):
`id` (autoincrement), `status` (`"unmodified"`/`"modified"`), `is_synced`, `sync_hash` (surfaces
as the API's `hash`), `photo_is_downloaded`, `photo_is_uploaded`, `selected_ingredients`,
`selected_direction`. Local `created` is a Julian float, converted to the string form for the API.

### Upload rules for recipes

1. **Full object only.** There are no partial updates; you must send every field. Missing text
   fields → `""` (except the three photo fields → `null`), booleans → `false`, `rating` → `0`,
   `categories` → `[]`.
2. `photo_url` must be omitted entirely.
3. `hash` must be a valid 64-char hex string and should change whenever content changes.
4. Upload creates *or* updates; the `{uid}` in the path is authoritative.
5. Uploading rewrites the server's hash and **Paprika may normalise other fields**, so a
   correct client re-fetches the recipe after pushing (`paprika-recipes` does exactly this).

---

## 5. Other entity schemas

Field lists below are from `paprika-rs`'s typed models (test-verified against a live account),
cross-checked against `paprika-tools`' OpenAPI spec.

**Category** — `uid`, `name`, `order_flag: int`, `parent_uid: string|null` (categories nest),
`deleted: bool` (on write).

**MealPlan** (`/sync/meals/`) — `uid`, `recipe_uid: string|null` (null = text-only meal),
`date: "YYYY-MM-DD HH:MM:SS"`, `type: int` (**0=Breakfast, 1=Lunch, 2=Dinner, 3=Snack**),
`name`, `order_flag: int`, `type_uid: string` (FK to mealtypes; an empty string is accepted on
write), `scale: string|null`, `is_ingredient: bool`, `deleted: bool` (write-only soft delete).

**MealType** — `uid`, `name`, `order_flag: int`, `color: string`, `export_all_day: bool`,
`export_time: int`, `original_type: int`. Meal types are **user-customisable**, so the
0/1/2/3 `type` enum is a display default, not a closed set — `type_uid` is the real link.

**GroceryList** — `uid`, `name`, `order_flag: int`, `is_default: bool`, `reminders_list: string`
(iOS Reminders list name).

**GroceryItem** — `uid`, `list_uid` (**required**), `name`, `ingredient` (lowercase canonical
form), `quantity`, `instruction`, `purchased: bool` (**the only delete: set `true`**),
`aisle: string`, `aisle_uid: string`, `recipe_uid: string|null`, `recipe: string|null`,
`order_flag: int`, `separate: bool`. **Send `aisle: ""` on create** so Paprika auto-assigns it
from `ingredient`; do not overwrite a server-assigned aisle on update.

**GroceryAisle** — `uid`, `name`, `order_flag: int`.

**GroceryIngredient** — `uid`, `name`, `aisle_uid: string|null`. This is the account's
ingredient→aisle lookup table.

**PantryItem** — `paprika-rs` (live-tested): `uid`, `ingredient`, `aisle`, `aisle_uid`,
`quantity`, `in_stock: bool`, `has_expiration: bool`, `expiration_date: datetime|null`,
`purchase_date: datetime`. The OpenAPI spec instead lists `name`/`purchased`/`order_flag` and
labels the endpoint "confirmed from database schema analysis" — **trust `paprika-rs` here**;
the OpenAPI pantry schema looks copied from the grocery-item shape.

**Menu** — `uid`, `name`, `notes`, `order_flag: int`, `days: int`.
**MenuItem** — `uid`, `name`, `order_flag: int`, `recipe_uid`, `menu_uid`, `type_uid`,
`day: int`, `deleted: bool`. Menus are reusable meal-plan templates, distinct from `/meals/`.

**Photo** (gallery) — `uid`, `recipe_uid`, `filename`, `name` (the app numbers them `"1"`,
`"2"`, …), `order_flag: int`, `hash` (opaque sync token, uppercase SHA256 of the image bytes in
`paprika-recipes`), `deleted: bool`, `photo_url` (**response-only**, stripped on upload).

**Bookmark** — `uid`, `title`, `url`, `order_flag: int`.

### Photo model (important, and poorly documented elsewhere)

A recipe carries **two** images and they live in different places:

- The recipe's own `photo` field is a **square thumbnail** (`paprika-recipes` uses 280×280,
  JPEG q85) whose bytes are digested into `photo_hash`. It is uploaded as the `photo_upload`
  multipart part *in the same request* as the recipe JSON.
- The picture itself is a **gallery photo**: a separate object POSTed to
  `/v2/sync/photo/{photo_uid}/`, and the recipe's `photo_large` names that file
  (`paprika-recipes` caps the long edge at 2048px). Deleting one is a POST with `deleted: true`
  and no image bytes.
- Local layout for the desktop app is `Photos/{recipe_uid}/{filename}.jpg`.

---

## 6. Authentication flow and token lifetime

### The flow that actually works for a third-party client

```
POST https://www.paprikaapp.com/api/v1/account/login/
Content-Type: application/x-www-form-urlencoded
User-Agent: <Paprika-app-prefixed string>

email=<email>&password=<password>

→ 200 {"result": {"token": "<JWT>"}}
```

Then on every subsequent request: `Authorization: Bearer <JWT>`.

Two client variants exist and both work: `paprika-tools` additionally sends
`Authorization: Basic base64(email:password)` alongside the form body; `paprika-3-mcp` and
kappari send the form body alone. The Basic header appears to be redundant belt-and-braces.

### Why v1 rather than v2

`POST /api/v2/account/login/` is the endpoint the real app uses, and it accepts four multipart
fields: `email`, `password`, `data` (a JSON license blob), `signature` (base64 RSA-SHA256
signature of that blob, verifiable only with Paprika's private key). kappari's finding:

- v2 rejects password-only login with `{"error": {"message": "Invalid purchase receipt."}}`
  **unless the User-Agent identifies a mobile client**, and sending empty `data`/`signature`
  triggers the same error — they must be **omitted entirely**, not blanked.
- v1 has no such check on any platform.

`paprika-recipes` reaches the opposite practical conclusion and uses v2 successfully with only
`email`+`password`, noting: *"Paprika's own app posts a third field here, `receipt`, holding the
App Store receipt... Omitting it is fine — the field is only validated when it is present and
non-empty, and the token comes back with the same scope and account mode either way."* The
reconciliation is almost certainly the User-Agent: `paprika-recipes` sends the iOS app's UA
prefix, which is exactly the condition kappari says unlocks v2 password-only login.

**Recommendation for the plugin: log in via v1 with an app-prefixed User-Agent.** It is the
intersection of every source's success path.

### The license layer (context, not a requirement)

The desktop app does local RSA license validation before logging in: it decrypts a license blob
(AES-256-CBC/PBKDF2) from the local SQLite `purchases` table, verifies an SHA256withRSA
signature against a public key embedded in the binary, checks the product id and a
machine-bound `install_uid` (Windows: `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`), and
only then calls v2 login. **None of this is needed by a third-party client** — it is client-side
DRM plus an optional server-side receipt check. On iOS the license lives in the keychain, so
even the official client can't always produce it, which is presumably why the password-only
path survives.

### Token lifetime — genuinely unresolved

This is the least-settled fact in the whole surface. What each source says:

| Source | Claim |
|---|---|
| gist comment thread | The JWT payload contains only **issue time (`iat`) and email — no `exp` claim**; commenter reports a token "working for several weeks now" without renewal |
| `paprika-3-mcp` | *"As far as I can tell, this is a JWT with no expiration."* |
| kappari | *"JWT tokens have long expiration times (hours or days)."* Also notes the app revalidates its **license** daily (a separate concern) |
| `paprika-tools` `API_REFERENCE.md` | *"Token Expiration: Unknown duration — handle 401 gracefully."* |

**Working conclusion:** the token most likely has no `exp` claim and is valid until
server-side revocation (password change, account action). It is **not** safe to assume
permanence. Every client that handles this at all uses the same pattern, which the plugin
should copy: cache the token on disk (mode 0600), attach it, and on a `401` **clear the cache,
re-login once, and retry the request exactly once**. `paprika-tools` implements precisely this;
`paprika-rs` validates a supplied token by calling `/sync/status/` at construction time, which
is a cheap liveness probe worth stealing.

Observed token cache locations in the wild: `~/.config/paprika/config.yaml`,
`~/Library/Application Support/paprika-mcp/.paprika_token.json` (chmod 600),
`~/.paprika-mcp/config.json`.

### Rate limits

**Undocumented and unobserved.** No source reports ever being throttled, and none reports a
429 in the wild. `paprika-tools` recommends a very conservative "60+ seconds between requests",
which is almost certainly excessive superstition — `paprika-rs`'s test suite walks every recipe
in an account back-to-back without issue, and the app's own sync does the same.
`paprika-recipes` mounts a retry adapter for `429, 500, 502, 503, 504` with `backoff_factor=1`
and 5 attempts, which is the sane posture: **don't pre-throttle, do back off on 429/5xx.**

---

## 7. Sync semantics and cost

### How change is detected

Paprika's sync model is **hash-token-based, not timestamp-based**. Every syncable entity carries
a 64-hex-char `hash` (`sync_hash` in the local DB). Critically, per kappari's binary analysis:

> *"The `sync_hash` field... is **not a content hash** but a change tracking mechanism. When an
> entity is modified, the system generates a new GUID, immediately hashes it with SHA256, and
> stores the result as the sync_hash. The original GUID is discarded."*

So the hash is an **opaque random change token**, not a digest of the recipe. Two consequences:

1. **You cannot verify or recompute the server's hash.** `paprika-recipes` says it plainly:
   *"This is the only thing Paprika's hash is good for — it folds in the photo, so we cannot
   compute it ourselves."* The hash is useful **only** for equality comparison against the value
   you saw last time.
2. **Any 64-char hex string is accepted on write.** The server validates format (64 hex chars;
   an empty or malformed hash causes sync failure and client retry loops) but not derivation.
   Clients nonetheless pick a deterministic scheme — both `paprika-recipes` and `paprika-3-mcp`
   use `sha256(json.dumps(recipe_minus_hash, sort_keys=True))` — because a *content-derived*
   local hash makes "did my local copy change?" cheap. That is a client-side convenience and has
   nothing to do with what the server stores.

### The `/sync/status/` counter layer

`GET /v2/sync/status/` returns one integer per entity type:

```json
{"result": {"recipes": 42, "categories": 5, "meals": 12, "groceries": 8,
            "groceryaisles": 15, "groceryingredients": 30, "grocerylists": 3,
            "mealtypes": 4, "menuitems": 0, "menus": 0, "pantry": 10,
            "photos": 25, "bookmarks": 2}}
```

These are **change counters that increment on modification, not item counts** (per
`paprika-tools`' API reference). Store them; on the next sync, only fetch the collections whose
counter moved. This is the cheapest possible "has anything changed at all?" probe — one request
for the whole account.

> ⚠️ **Unverified.** The counters-not-counts claim comes from a single source and the example
> values are suspiciously plausible as counts (42 recipes, 3 grocery lists, 4 meal types).
> No client I read actually *uses* `/status/` for change detection — `paprika-rs` calls it only
> as a token liveness check, and `paprika-recipes` ignores it entirely in favour of the recipe
> index. **The plugin should verify empirically before relying on it**, and should not treat a
> counter as a count.

### The recipe two-step

1. `GET /v2/sync/recipes/` → `[{uid, hash}, ...]` for the entire account, one request.
2. Diff against your cached `uid → hash` map.
3. `GET /v2/sync/recipe/{uid}/` for each uid that is new or whose hash moved.
4. Cache the full body keyed by `(uid, hash)`.

Both `paprika-recipes` (`DirectoryCache`) and `briantkatch/paprika-mcp` implement exactly this,
keying the cache by uid and validating by hash.

### Cost model

Let **N** = recipes in the account, **C** = recipes changed since last sync.

| Operation | Requests | Notes |
|---|---|---|
| "Has anything changed?" (cheapest) | **1** | `GET /sync/status/`, ~200 bytes — *if* the counter semantics hold |
| Recipe change detection | **1** | `GET /sync/recipes/`; ~100 bytes per recipe, so ~100 KB at N=1000. This is the real workhorse and is cheap enough to do unconditionally. |
| Incremental recipe sync | **1 + C** | One index call plus one full fetch per changed recipe |
| Full recipe sync (cold cache) | **1 + N** | **There is no bulk recipe download.** N=500 recipes = 501 sequential HTTP round-trips. At ~200 ms each that is ~100 seconds. This is the dominant cost in the entire API. |
| Full non-recipe sync | **14** | One GET per remaining collection; each returns everything at once |
| Push one recipe | **1** (+1 to re-fetch, +1 `notify`) | Plus 1 more per gallery photo |
| Push K grocery items / meals | **1** | Bulk arrays — genuinely cheap |

**Design implication for the plugin: the local cache is not an optimisation, it is a
requirement.** Cold-start a 1000-recipe library and you are making 1001 requests. Persist
`uid → (hash, full recipe JSON)` durably, and never invalidate on anything but a hash change.
Note that a cached `photo_url` goes stale within hours even when the hash has not moved — treat
photo URLs as never-cacheable and re-fetch the recipe to mint a fresh signed link.

### Writes, conflicts and deletion

- **Last-write-wins, no optimistic concurrency.** There is no If-Match, no version check, and
  the server does not reject a write based on a stale `hash`. Whoever POSTs last wins the whole
  object. Since writes are full-object, a concurrent edit to a *different field* is still lost.
  Any safe client must re-read immediately before writing, or do a three-way merge against a
  stored base copy (which is what `paprika-recipes`' sync engine does: server hash vs. base hash
  vs. local diff, merging when both moved).
- **After any write, re-fetch.** The upload rewrites the hash and the server may normalise other
  fields; the response is only `{"result": true}` and tells you nothing about what was stored.
- **`POST /v2/sync/notify/`** after writes to push other devices to pull. Fire-and-forget;
  `paprika-3-mcp` defers it and ignores failures.
- **Deletion is soft, always, everywhere:**

  | Entity | Delete mechanism |
  |---|---|
  | Recipe | `in_trash: true` (recoverable; **permanent deletion requires emptying trash in the app UI — there is no API for it**) |
  | Grocery item | `purchased: true` |
  | Meal plan entry | `deleted: true` |
  | Menu item, category, photo | `deleted: true` |

  kappari's rationale: soft deletes stop deleted content from resurrecting when an offline
  device reconnects.

---

## 8. Where sources disagree

These are the points a downstream design must not assume away.

### 8.1 `categories` — UIDs or names? **(highest-impact disagreement)**

| Source | Says |
|---|---|
| `aarons22/paprika-tools` OpenAPI + API_REFERENCE | *"List of category **names** (not UIDs)"*, example `["Breakfast", "Baking"]` |
| 2018 gist payload | UIDs: `"categories": ["cbaca738-cdfb-4150-960d-e1b1ac4cdcc3"]` |
| gist comment thread | *"categories identified by UIDs rather than plain names"* |
| `briantkatch/paprika-mcp` | Explicitly: *"categories field (stored internally as a UUID list)"*, and ships UID↔name translation against `/sync/categories/` |
| `coddingtonbear/paprika-recipes` | `list[str]`, untyped either way |
| `Syfaro/paprika-rs` | `Vec<String>`, untyped either way |

**Assessment: `categories` almost certainly holds category UIDs.** Three independent sources say
UIDs (including one that had to build a translation layer *because* they were UIDs), one says
names, and that one's example values look synthetic — its own example recipe uses placeholder
category uids `"CAT-UID-1"` elsewhere in the same document. **Verify before writing any recipe**,
because getting this wrong silently detaches every recipe from its categories.

### 8.2 `on_grocery_list` — bool or string?

`paprika-rs` types it `bool`; `paprika-3-mcp` types it `bool`; `paprika-recipes` and the OpenAPI
spec type it `str | None` (described as "grocery list reference if ingredients have been added").
Both compile against real data, which suggests the field may be polymorphic or that one side is
coercing. Treat as **opaque, echo back whatever you received**, and never synthesise a value.

### 8.3 `nutritional_info` missing from `paprika-rs`

`paprika-rs`'s `PaprikaRecipe` has no `nutritional_info` field at all, despite every other source
including it and the web clipper returning it. Serde ignores unknown fields by default, so this
is a gap in that client, not evidence the field is absent. **The field exists.** It does mean any
recipe round-tripped through `paprika-rs` would silently drop its nutrition data.

### 8.4 v2 password-only login

kappari says it fails with "Invalid purchase receipt"; `paprika-recipes` and `paprika-rs` do it
successfully. Reconciled by the User-Agent gate (§6), but not proven.

### 8.5 Pantry item shape

`paprika-rs` (live-tested) and the OpenAPI spec describe two structurally different objects.
See §5. Trust `paprika-rs`.

### 8.6 Endpoint path normalisation in the OpenAPI spec

`paprika-tools`' `openapi.yaml` **renames `/v2/sync/recipe/{uid}/` to `/recipes/{uid}/`** for CLI
ergonomics and says so in its own description. Anyone generating a client from that spec will
produce wrong URLs unless they account for it. The real path is singular: `recipe`.

### 8.7 Whether `/sync/status/` counters are counters

See §7. Single-sourced and unused by any client I read.

---

## 9. Open questions for follow-up tickets

1. **`categories`: UIDs or names?** Blocking for any recipe write. Resolve with one read of a
   recipe that has known categories. (§8.1)
2. **Are `/sync/status/` values counters or counts?** Determines whether the cheap change probe
   exists at all. Resolve by reading status, modifying one recipe in the app, re-reading. (§7)
3. **Token lifetime.** Decode a real JWT's payload (offline, no API call) to confirm the absence
   of an `exp` claim. (§6)
4. **Is the v2 User-Agent gate still active, and on which routes?** `paprika-3-mcp` appears to
   bypass it on sync GETs. Determines how careful the plugin must be about UA spoofing.
5. **Do the inferred writes exist** (`grocerylists`, `groceryaisles`, `pantry`, `menus`,
   `mealtypes`, `bookmarks`)? Relevant if the plugin ever needs to create a grocery list or
   manage pantry stock rather than just read them.
6. **Is there any server-side filtering at all** — date ranges on `/meals/`, `list_uid` on
   `/groceries/`? Every source says filter client-side, but nobody reports having tried query
   params. A `?date_min=` on `/meals/` would materially change meal-planning cost.
7. **Rate limits.** Nobody has found one. Worth establishing an empirical ceiling before the
   plugin fires 500 sequential recipe fetches at a cold start.
8. **Permanent deletion.** Confirmed absent from the API; recipes accumulate in trash forever
   unless a human opens the app. The plugin should surface this to users rather than implying
   `in_trash` is a delete.
9. **`type_uid` on meal plans.** `paprika-tools` writes `""` successfully; unclear whether the
   server backfills it, or whether the entry renders correctly in the app afterwards.
10. **Error taxonomy.** Only two error messages are documented anywhere ("Unrecognized client.",
    "Invalid purchase receipt.", plus a generic "Invalid data." with `code: 0`). No source has
    catalogued the `code` values.

---

## 10. Practical checklist for the plugin

- Log in via `POST /api/v1/account/login/`, form-encoded, with an app-prefixed User-Agent.
- Cache the token at 0600; on 401, clear, re-login once, retry once. Probe liveness with
  `GET /v2/sync/status/`.
- Send the app-prefixed UA on **every** request, not just login.
- Check every response body for an `error` key regardless of HTTP status.
- Sniff `1f 8b` on responses and decompress conditionally.
- Persist a `uid → (hash, recipe)` cache. Never cold-fetch a library twice.
- Treat `photo_url` as uncacheable (expires in hours) and never send it on upload.
- Writes: full object, gzipped, multipart `data`, `photo`/`photo_hash`/`photo_large` as `null`
  when empty; re-fetch afterwards; then `POST /v2/sync/notify/`.
- Never attempt DELETE. Use `in_trash` / `purchased` / `deleted` per entity.
- Read before write, or three-way merge — the API has no concurrency control whatsoever.
