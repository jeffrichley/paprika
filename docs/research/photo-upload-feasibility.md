# Research: is photo upload feasible?

Resolves [#9](https://github.com/jeffrichley/paprika/issues/9).

## Verdict

**Photo upload through the unofficial Paprika v2 API is FEASIBLE.** It is not
closed. There is a real, working, publicly readable implementation of the full
write path, and the mechanism is simple: an extra `photo_upload` file part
riding alongside the gzipped JSON on the ordinary recipe sync POST.

Split by the two features that depend on this:

| Use case | Needs photo upload? | Verdict |
|---|---|---|
| **(a) Recipe quality** — a recipe imported from the web keeps its photo | Yes | **FEASIBLE.** We fetch the image ourselves, cut two derived JPEGs, and post them with the recipe. |
| **(b) Fog-stage pantry intake** — user photographs a shelf, agent reads the items | **No** | **Not gated by this ticket at all.** Reading a local image is Claude's own multimodal capability. Nothing is uploaded to Paprika; only the extracted *text* items are written, through the pantry/grocery endpoints. |

These two must not be conflated. (b) would still be buildable if photo upload
were completely impossible.

One caveat that does bind (a): this is reverse-engineered, unofficial, and
carries no vendor contract. See [Risks and unknowns](#risks-and-unknowns).

## The photo data model

Paprika has **two distinct photo concepts**, and confusing them is the main
trap in this area.

### 1. The recipe thumbnail — carried on the recipe object

Fields on the recipe itself:

| Field | Type | Meaning |
|---|---|---|
| `photo` | string / null | Filename of the recipe's thumbnail, e.g. `"BC6BFB89-1301-445C-AB7F-61FF0410E122.jpg"`. Not a path, not a URL. |
| `photo_hash` | string / null | Uppercase hex SHA256 of the **exact thumbnail bytes**. Integrity and dedupe. |
| `photo_large` | string / null | Filename of the *gallery* twin of the main picture (see below). |
| `photo_url` | string / null | **Read-only, response-only.** A signed object-storage download link on `uploads.paprikaapp.com`. Never sent on writes. |
| `image_url` | string | Free-text external image URL. No evidence the server ever fetches it. |

Note `photo_hash` is a content hash, while the recipe's `hash` field is a
change-detection token — kappari documents them as two unrelated SHA256
systems, the latter being SHA256 of a random discarded GUID.

### 2. Gallery photos — separate first-class entities

A recipe's photos page holds a list of photo objects, each its own record,
retrieved from `GET /api/v2/sync/photos/`:

```
uid         string   uppercase UUID (= filename minus ".jpg")
recipe_uid  string   owning recipe
filename    string   e.g. "25E502DA-91D2-45EA-8852-10740D004EE6.jpg"
name        string   display name; the app numbers them "1", "2", ...
order_flag  int      display order
hash        string   opaque sync token, uppercase hex SHA256 of the bytes
deleted     bool     soft-delete flag (this is how deletion works)
photo_url   string   read-only signed download link; responses only
```

When the app adds a photo to a recipe it writes **both**: a square thumbnail
onto the recipe (`photo`/`photo_hash`), and the full picture into the gallery,
with the recipe's `photo_large` naming that gallery copy.

`GET /api/v2/sync/status/` returns a `photos` counter alongside `recipes`,
`pantry`, etc., so photo changes participate in normal sync-status polling.

### On disk (local Paprika 3 SQLite, per kappari)

Photos are filesystem blobs, never DB blobs: `Photos/{recipe_uid}/{uuid}.jpg`.
The `recipes` table carries `photo`, `photo_hash`, `photo_large`,
`photo_is_downloaded`, `photo_is_uploaded`; extra photos live in a
`recipe_photos` table. This is only relevant if we ever read a local install —
not needed for API work.

## Read path (confirmed)

1. `GET /api/v2/sync/recipes/` → lightweight `{uid, hash}` pairs.
2. `GET /api/v2/sync/recipe/{uid}/` → full recipe, including a freshly signed
   `photo_url`.
3. `GET <photo_url>` → **plain GET against object storage.** No bearer token,
   no JSON envelope; the response body is the raw image.
4. `GET /api/v2/sync/photos/` → every gallery photo on the account, each with
   its own `photo_url`.

Two practical notes:

- **Signed URLs expire in hours.** A `photo_url` cached from an earlier
  response may no longer open. Re-fetching the recipe (deliberately bypassing
  any response cache) mints a new signature.
- **The recipe's `photo_url` yields the 280px thumbnail, not the original.**
  The full-size picture is the gallery copy named by `photo_large`. If we want
  the good image, pull it from the gallery.

## Write path (confirmed by a working implementation)

Both writes are `multipart/form-data` POSTs carrying **two parts**: the usual
gzipped-JSON `data` part, plus a raw binary `photo_upload` part. Binary never
goes inside the gzip JSON.

### Recipe thumbnail

```
POST /api/v2/sync/recipe/{recipe_uid}/
Authorization: Bearer <token>
Content-Type: multipart/form-data

  part "data"          = gzip(JSON of the FULL recipe object)
  part "photo_upload"  = (recipe.photo, <thumbnail bytes>, "image/jpeg")   # only when the photo changes
```

Before posting, the caller sets:

- `photo` = a fresh `UUID4().upper() + ".jpg"`
- `photo_hash` = `sha256(thumbnail_bytes).hexdigest().upper()`
- `photo_large` = a second fresh `UUID4().upper() + ".jpg"`
- `photo_url` — **removed from the payload entirely**
- `hash` — recomputed (any 64-char hex is accepted by the server)

Two spellings matter, observed from the app's own traffic rather than
documented anywhere: **an absent photo field must serialize as JSON `null`,
never `""`**, and `photo_url` must not be sent at all.

### Gallery photo

```
POST /api/v2/sync/photo/{photo_uid}/
Authorization: Bearer <token>
Content-Type: multipart/form-data

  part "data"          = gzip(JSON of the photo object, photo_url stripped)
  part "photo_upload"  = (photo.filename, <full-size bytes>, "image/jpeg")
```

**Deletion** is a re-post of the same photo object with `deleted: true` and no
image part — the closest thing the endpoint has to a DELETE. This matters when
replacing a photo: the old `photo_large` becomes an orphan unless explicitly
taken down.

### Afterwards

`POST /api/v2/sync/notify/` asks the API to tell other devices something
changed.

## Encoding and size limits

| Aspect | Finding | Confidence |
|---|---|---|
| Transport | Separate `multipart/form-data` binary part. Not base64, not inside the gzip. | High — implemented and documented; kappari's encoding notes state plainly that "binary data (images) [is] handled separately". |
| Format | `image/jpeg`. PNG/other inputs get converted to JPEG on the way up. | High |
| Thumbnail | 280×280 square (center-fit crop), JPEG quality ~85 | High — matches the app's own uploads |
| Full/gallery image | Scaled to fit a 2048px bounding box (never upscaled), JPEG quality ~85 | High |
| Orientation | EXIF orientation must be applied and the tag dropped, or phone photos land sideways | High |
| Transparency | Flattened onto white before JPEG encoding | High |
| **Server-side byte cap** | **Not documented anywhere. Behavior on an oversized upload is unknown.** The 2048px bound is a *client* convention copied from the app, not a known server rule. | **Unknown** |
| Rate limits | Unknown across all sources; the most careful source recommends 60s+ intervals between writes | Unknown |

There is exactly one place base64 photo data appears in the Paprika ecosystem:
the `.paprikarecipes` **archive/export** format, where each `.paprikarecipe`
entry may carry a `photo_data` field holding base64 image bytes. That is a
file-import format, **not an API mechanism**, and it is a poor fit for anything
text-shaped — a single recipe buries its ingredients under a megabyte of
base64. Mentioned here only so it isn't mistaken for the upload path.

## Which existing implementations do it

| Project | Photo read | Photo write | Notes |
|---|---|---|---|
| [coddingtonbear/paprika-recipes](https://github.com/coddingtonbear/paprika-recipes) (Python, MIT, ~83★, active) | ✅ | ✅ **full** | **The only known implementation of photo upload.** Implements both endpoints, both derived image sizes, gallery deletion, signed-URL renewal. Its `remote.py`, `images.py`, and `sync.py` are the primary evidence for this whole document. |
| [Syfaro/paprika-rs](https://github.com/Syfaro/paprika-rs) (Rust) | metadata only | ❌ | `GET sync/photos` is modeled (`PaprikaPhoto` = uid/filename/recipe_uid/order_flag/name/hash — note it does **not** model `photo_url`, so it can't even fetch bytes). Its `json_post` helper is marked `#[allow(dead_code)]` and unused: the client writes nothing at all. |
| [aarons22/paprika-tools](https://github.com/aarons22/paprika-tools) (OpenAPI + Go CLI + MCP) | fields only | ❌ | The OpenAPI spec has **no `/photos` path whatsoever** — photos are simply outside its scope. It documents `photo_url` as "Server-hosted photo URL (read-only)" and its Python MCP client has no photo methods. |
| [soggycactus/paprika-3-mcp](https://github.com/soggycactus/paprika-3-mcp) (Go MCP) | fields only | ❌ | Its `Recipe` struct carries `photo`/`photo_hash`/`photo_large`/`photo_url` and `SaveRecipe` gzips them straight back. ⚠️ It sends `photo_url` back on write and uses `""` rather than `null` for empty photo fields — both contrary to the observed app behavior above. Worth avoiding as a model. |
| [briantkatch/paprika-mcp](https://github.com/briantkatch/paprika-mcp) (Python MCP) | ❌ | ❌ | `update_recipe` whitelists writable fields by enum; photo fields are deliberately excluded. Text find/replace only. |
| [radicalrob/paprika-mcp](https://github.com/radicalrob/paprika-mcp) | — | — | **404 — repository not reachable.** Cannot be assessed. |
| [johnwbyrd/kappari](https://github.com/johnwbyrd/kappari) (docs only) | n/a | n/a | Documentation project, no client. Its endpoint list marks `/api/v2/photos/` as an **unconfirmed guess** — that guess is wrong; the real endpoints are `/api/v2/sync/photos/` and `/api/v2/sync/photo/{uid}/`. Its schema and encoding notes are otherwise excellent. |

**Bottom line: no MCP server implements photo upload. Exactly one CLI does.**
If we ship it, we are ahead of every MCP server in this space — and we have a
reference implementation to follow rather than protocol to rediscover.

## Risks and unknowns

- **Unofficial throughout.** Every endpoint here is reverse-engineered. Paprika
  publishes no API contract and owes us no stability.
- **No known size cap.** We don't know what the server does with a 40MB
  upload. Staying inside the app's own 2048px / q85 convention is the safe
  play, and is what we'd do anyway.
- **Rate limits unknown.** Be conservative with bulk photo pushes.
- **Signed URLs expire.** Never persist a `photo_url`; re-fetch the recipe.
- **Orphaned gallery copies.** Replacing a photo without soft-deleting the old
  `photo_large` leaves junk in the account.
- **`image_url` is not an upload shortcut.** No source shows the server
  fetching it. Do not assume setting `image_url` populates the photo —
  **UNKNOWN**, and cheap to test later, but not something to design against.
- **Auth is a separate concern.** Sources disagree: v1 Basic auth, v2 bearer
  with a `receipt` field (reportedly optional), and kappari's desktop capture
  showing license data plus an RSA signature. Out of scope for this ticket.
- **Everything above is read from source, not executed.** No live API calls
  were made and no credentials were used in this research. The write path
  should get one manual end-to-end confirmation before we depend on it.

## Recommendation

For **(a) recipe quality**, treat photo upload as a supported capability and
implement it in this order:

1. Download the source image ourselves from the imported recipe's image URL.
2. Derive two JPEGs: a 280×280 center-fit thumbnail and a ≤2048px full copy,
   both q85, EXIF-corrected, transparency flattened.
3. `POST /api/v2/sync/recipe/{uid}/` with `data` + `photo_upload` (thumbnail),
   setting `photo`, `photo_hash`, `photo_large` as described, `photo_url`
   omitted, empty photo fields as `null`.
4. `POST /api/v2/sync/photo/{gallery_uid}/` with `data` + `photo_upload`
   (full copy).
5. Soft-delete any previous `photo_large`.
6. `POST /api/v2/sync/notify/`.

For **(b) pantry intake**, build it independently. It needs local image
reading and text writes only, and should not wait on any of the above.

## Sources

All read via the GitHub API; no repositories were cloned, no live Paprika API
calls were made, no credentials were used.

- `coddingtonbear/paprika-recipes` — `paprika_recipes/remote.py`,
  `paprika_recipes/images.py`, `paprika_recipes/sync.py`,
  `paprika_recipes/recipe.py`, `paprika_recipes/archive.py`, `readme.md`
- `johnwbyrd/kappari` — `schema.md`, `api.md`, `endpoints.md`, `encoding.md`
- `aarons22/paprika-tools` — `openapi.yaml`, `API_REFERENCE.md`,
  `paprika_mcp/client.py`
- `Syfaro/paprika-rs` — `paprika-client/src/lib.rs`
- `soggycactus/paprika-3-mcp` — `internal/paprika/client.go`
- `briantkatch/paprika-mcp` — `src/paprika_mcp/tools/update_recipe.py`
- `radicalrob/paprika-mcp` — unreachable (404)
