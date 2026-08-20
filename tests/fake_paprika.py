"""A fake Paprika that is wrong in all the same ways the real one is.

This is the executable record of ``docs/research/paprika-v2-api-surface.md`` and
of issue #19's live probing. It reproduces the API's **pathologies**, not an
idealised version of it, because the riskiest code in this plugin is wire-format
code and a tidy fake would skip exactly the parts that had to be learned the hard
way:

* an ``{"error": ...}`` body arriving at HTTP 200
* an unrecognised ``User-Agent`` refused the same way, also at 200
* a genuine HTTP 500, naming no field, when a write is malformed
* no bulk recipe endpoint — the index returns ``{uid, hash}`` stubs only
* a stale ``hash`` accepted and stored, never bumped, never rejected
* no ``DELETE`` verb anywhere
* ``/sync/status/`` holding monotonic change counters rather than counts
* soft deletion leaving no tombstone

It sits at HTTP rather than behind a client interface on purpose. A swappable
``PaprikaClient`` protocol would fake away the gzip construction, the User-Agent
gate, the body sniffing and the error-inside-a-200 — the four things most likely
to damage her library.
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass, field
from typing import Any

import httpx

BASE = "https://www.paprikaapp.com"

#: The prefix the v2 API gates on. Anything not starting with this is refused —
#: at a 200, with an error body, which is the whole point.
REQUIRED_UA_PREFIX = "Paprika 3/"

GOOD_EMAIL = "cook@example.com"
GOOD_PASSWORD = "correct-horse"
TOKEN = "fake.jwt.token"

#: Every field a full recipe object carries. Thirty-five of them, seven
#: undocumented anywhere (`cook_minutes`, `prep_minutes`, `total_minutes`,
#: `servings_min`, `servings_max`, `cookbook_uid`, `metadata_version`).
RECIPE_FIELDS: tuple[str, ...] = (
    "uid",
    "name",
    "ingredients",
    "directions",
    "description",
    "notes",
    "nutritional_info",
    "servings",
    "difficulty",
    "prep_time",
    "cook_time",
    "total_time",
    "rating",
    "categories",
    "source",
    "source_url",
    "image_url",
    "photo",
    "photo_hash",
    "photo_large",
    "photo_url",
    "hash",
    "created",
    "on_favorites",
    "on_grocery_list",
    "in_trash",
    "is_pinned",
    "scale",
    "cook_minutes",
    "prep_minutes",
    "total_minutes",
    "servings_min",
    "servings_max",
    "cookbook_uid",
    "metadata_version",
)

#: The fields Paprika will not accept as blanks. A write missing any of them, or
#: sending `""` where `null` is required, earns a genuine 500 naming no field.
_PHOTO_FIELDS = ("photo", "photo_hash", "photo_large")

#: Removal. Not part of the v2 recipe object as fetched, but accepted on write.
REMOVAL = "deleted"


def _error(message: str, code: int = 1, status: int = 200) -> httpx.Response:
    """Build an error response — at a success status by default, as Paprika does.

    Args:
        message: What Paprika says. Verbatim, so nothing about it looks polished.
        code: Paprika's own error code.
        status: The HTTP status to send it at. 200 is the realistic case.

    Returns:
        httpx.Response: The response.
    """
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


def _refused() -> httpx.Response:
    """Build the genuine 500 a malformed write earns.

    It names no field and carries no JSON, which is exactly why a client has to
    validate before it posts rather than read the refusal.

    Returns:
        httpx.Response: The response.
    """
    return httpx.Response(500, text="Internal Server Error")


def _result(payload: Any) -> httpx.Response:
    """Build a success response.

    Args:
        payload: Whatever goes under ``result``.

    Returns:
        httpx.Response: The response.
    """
    return httpx.Response(200, json={"result": payload})


@dataclass
class FakePaprika:
    """One fake account, holding whatever a test seeded into it.

    Attributes:
        recipes: uid to full recipe object.
        categories: The category tree, flat, with ``parent_uid`` links.
        counters: ``/sync/status/`` change counters. Monotonic, not counts.
        writes: Every recipe body that was accepted, in order. What a test asserts
            against, since the API's own response says only ``true``.
        requests: Every request that arrived, as ``(method, path)``.
    """

    recipes: dict[str, dict[str, Any]] = field(default_factory=dict)
    categories: list[dict[str, Any]] = field(default_factory=list)
    meals: list[dict[str, Any]] = field(default_factory=list)
    pantry: list[dict[str, Any]] = field(default_factory=list)
    grocery_ingredients: list[dict[str, Any]] = field(default_factory=list)
    grocery_aisles: list[dict[str, Any]] = field(default_factory=list)
    grocery_lists: list[dict[str, Any]] = field(default_factory=list)
    groceries: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    writes: list[dict[str, Any]] = field(default_factory=list)
    requests: list[tuple[str, str]] = field(default_factory=list)
    #: When set, every recipe write is refused. For exercising a Run that starts
    #: failing partway, which must stop rather than continue.
    fail_writes: bool = False
    #: Refuse writes only once this many have landed.
    fail_writes_after: int | None = None
    #: Accept the write, answer `true`, and quietly keep the old object. The
    #: failure mode a status code would never reveal, and the reason a bulk Run
    #: verifies itself rather than trusting what it was told.
    silently_discard: set[str] = field(default_factory=set)
    #: Refuse the stub index once a write has happened, so a Run cannot verify.
    fail_index_after_write: bool = False
    #: How many times her other devices were told to pull.
    notified: int = 0
    #: Refuse the announcement, which must not fail the write it follows.
    refuse_notify: bool = False
    #: Every meal array that was accepted, in order.
    meal_writes: list[list[dict[str, Any]]] = field(default_factory=list)
    #: Every pantry array that was accepted, in order.
    pantry_writes: list[list[dict[str, Any]]] = field(default_factory=list)
    #: Every grocery array that was accepted, in order.
    grocery_writes: list[list[dict[str, Any]]] = field(default_factory=list)

    def transport(self) -> httpx.MockTransport:
        """Return a transport that answers as Paprika would.

        Returns:
            httpx.MockTransport: The transport to hand to an ``httpx.Client``.
        """
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Answer one request.

        Args:
            request: The request that arrived.

        Returns:
            httpx.Response: What Paprika would send back.
        """
        path = request.url.path
        method = request.method
        self.requests.append((method, path))

        # There is no DELETE verb anywhere in this API.
        if method == "DELETE":
            return httpx.Response(404, text="Not found.")

        if path == "/api/v1/account/login/":
            return self._login(request)

        # The gate: an unrecognised client is refused at a 200, not a 4xx.
        agent = request.headers.get("User-Agent", "")
        if not agent.startswith(REQUIRED_UA_PREFIX):
            return _error("Unrecognized client.")

        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return _error("Invalid session.")

        if method == "GET":
            return self._get(path)
        if method == "POST":
            return self._post(path, request)
        return httpx.Response(404, text="Not found.")

    def _login(self, request: httpx.Request) -> httpx.Response:
        """Answer the form-encoded v1 login.

        Args:
            request: The login request.

        Returns:
            httpx.Response: A token, or an error at a 200.
        """
        form = dict(httpx.QueryParams(request.content.decode("utf-8")))
        if form.get("email") == GOOD_EMAIL and form.get("password") == GOOD_PASSWORD:
            return _result({"token": TOKEN})
        return _error("Invalid email or password.")

    def _collections(self) -> dict[str, list[dict[str, Any]]]:
        """Return every whole-account collection, by path.

        Returns:
            dict[str, list[dict[str, Any]]]: Path to what it serves.
        """
        return {
            "/api/v2/sync/categories/": self.categories,
            # Soft-deleted meals stay in the collection, as everything here does.
            "/api/v2/sync/meals/": self.meals,
            "/api/v2/sync/pantry/": self.pantry,
            "/api/v2/sync/groceryingredients/": self.grocery_ingredients,
            "/api/v2/sync/groceryaisles/": self.grocery_aisles,
            "/api/v2/sync/grocerylists/": self.grocery_lists,
            "/api/v2/sync/groceries/": self.groceries,
        }

    def _get(self, path: str) -> httpx.Response:
        """Answer a read.

        Args:
            path: The request path.

        Returns:
            httpx.Response: The collection or object, or a 404.
        """
        if path == "/api/v2/sync/status/":
            return _result(dict(self.counters))
        collection = self._collections().get(path)
        if collection is not None:
            return _result([dict(row) for row in collection])
        if path == "/api/v2/sync/recipes/":
            if self.fail_index_after_write and self.writes:
                return _error("Try again later.")
            # Stubs only. There is no bulk recipe download, and this is the
            # single fact that makes a cold sync cost 1 + N requests.
            #
            # Every recipe is listed, trashed ones included: `in_trash` is not
            # removal, and a trashed recipe stays here and stays readable.
            # Removal leaves no tombstone — the object is simply gone from this
            # collection, and only a moved counter says so.
            return _result(
                [
                    {"uid": uid, "hash": recipe["hash"]}
                    for uid, recipe in self.recipes.items()
                ]
            )
        if path.startswith("/api/v2/sync/recipe/") and path.endswith("/"):
            uid = path.rsplit("/", 2)[-2]
            recipe = self.recipes.get(uid)
            if recipe is None:
                return _error("Recipe not found.")
            return _result(dict(recipe))
        return httpx.Response(404, text="Not found.")

    def _post(self, path: str, request: httpx.Request) -> httpx.Response:
        """Answer a write.

        Args:
            path: The request path.
            request: The request, whose ``data`` part is gzipped JSON.

        Returns:
            httpx.Response: ``true``, or a genuine 500 for a malformed body.
        """
        if path == "/api/v2/sync/notify/":
            if self.refuse_notify:
                return _error("Not now.")
            self.notified += 1
            return _result(True)
        if path == "/api/v2/sync/meals/":
            return self._post_meals(request)
        if path == "/api/v2/sync/pantry/":
            return self._post_pantry(request)
        if path == "/api/v2/sync/groceries/":
            return self._post_groceries(request)
        # The plural route is the web clipper's scraper, not a bulk write. Using
        # it to create recipes is a 500.
        if path == "/api/v2/sync/recipes/":
            if self.fail_index_after_write and self.writes:
                return _error("Try again later.")
            return _refused()
        if path.startswith("/api/v2/sync/recipe/") and path.endswith("/"):
            return self._post_recipe(path.rsplit("/", 2)[-2], request)
        return httpx.Response(404, text="Not found.")

    def _post_meals(self, request: httpx.Request) -> httpx.Response:
        """Upsert the posted meal array.

        Args:
            request: The multipart request.

        Returns:
            httpx.Response: What Paprika would send back.
        """
        return _post_meals_impl(self, request)

    def _post_pantry(self, request: httpx.Request) -> httpx.Response:
        """Upsert the posted pantry array.

        The endpoint wants `ingredient` and an `aisle` key; an empty aisle
        passes. There is no `name` field here at all.

        Args:
            request: The multipart request.

        Returns:
            httpx.Response: What Paprika would send back.
        """
        body = _extract_gzipped_part(request.content)
        if not isinstance(body, list):
            return _refused()
        for entry in body:
            if not isinstance(entry, dict) or not entry.get("uid"):
                return _refused()
            if not str(entry.get("ingredient") or "").strip():
                return _refused()
            if "aisle" not in entry:
                return _refused()
            # Groceries and pantry are not symmetric; there is no name here.
            if "name" in entry:
                return _refused()
        self.pantry_writes.append([dict(e) for e in body])
        by_uid = {i["uid"]: i for i in self.pantry}
        for entry in body:
            if entry.get("deleted"):
                by_uid.pop(entry["uid"], None)
            else:
                by_uid[entry["uid"]] = dict(entry)
        self.pantry = list(by_uid.values())
        self.counters["pantry"] = self.counters.get("pantry", 0) + 1
        return _result(True)

    def _post_groceries(self, request: httpx.Request) -> httpx.Response:
        """Upsert the posted grocery array.

        `list_uid` is required here, unlike almost everything else.

        Args:
            request: The multipart request.

        Returns:
            httpx.Response: What Paprika would send back.
        """
        body = _extract_gzipped_part(request.content)
        if not isinstance(body, list):
            return _refused()
        for entry in body:
            if not isinstance(entry, dict) or not entry.get("uid"):
                return _refused()
            if not str(entry.get("list_uid") or "").strip():
                return _refused()
        self.grocery_writes.append([dict(e) for e in body])
        by_uid = {i["uid"]: i for i in self.groceries}
        for entry in body:
            by_uid[entry["uid"]] = dict(entry)
        self.groceries = list(by_uid.values())
        self.counters["groceries"] = self.counters.get("groceries", 0) + 1
        return _result(True)

    def _post_recipe(self, uid: str, request: httpx.Request) -> httpx.Response:
        """Store one recipe, or refuse it the way the real server refuses it.

        The refusal is a genuine HTTP 500 with no body worth reading and no field
        named — which is exactly why a client has to validate before it posts.

        Args:
            uid: The uid from the path, which is authoritative.
            request: The multipart request.

        Returns:
            httpx.Response: ``true`` on success, a 500 on anything malformed.
        """
        if self.fail_writes or (
            self.fail_writes_after is not None
            and len(self.writes) >= self.fail_writes_after
        ):
            return _refused()

        body = _extract_gzipped_part(request.content)
        if body is None or not isinstance(body, dict):
            return _refused()

        missing = [f for f in RECIPE_FIELDS if f != "photo_url" and f not in body]
        if missing:
            return _refused()
        # `photo_url` is read-only; sending it back is a malformed write.
        if "photo_url" in body:
            return _refused()
        # The three photo fields must be null when absent, never "".
        if any(body.get(f) == "" for f in _PHOTO_FIELDS):
            return _refused()
        stored_hash = body.get("hash")
        if not isinstance(stored_hash, str) or len(stored_hash) != 64:
            return _refused()

        # A stale hash is accepted and stored as sent. There is no
        # compare-and-swap here and the server never bumps it.
        stored = dict(body)
        stored["uid"] = uid
        stored["photo_url"] = None
        if uid in self.silently_discard:
            # Accepted, acknowledged, and not actually stored.
            self.writes.append(dict(body))
            return _result(True)
        if stored.pop(REMOVAL, False):
            # Removal, and it leaves no tombstone: the object is simply gone
            # from the collection. Re-posting the whole thing brings it back.
            self.recipes.pop(uid, None)
        else:
            self.recipes[uid] = stored
        self.writes.append(dict(body))
        self.counters["recipes"] = self.counters.get("recipes", 0) + 1
        return _result(True)


def _post_meals_impl(fake: FakePaprika, request: httpx.Request) -> httpx.Response:
    """Upsert a meal array by uid, as the real endpoint does.

    There is no per-uid route for meals — the whole array is posted, and each
    entry is matched on its uid. ``deleted`` removes.

    Args:
        fake: The account.
        request: The multipart request.

    Returns:
        httpx.Response: ``true``, or a genuine 500 for a malformed body.
    """
    body = _extract_gzipped_part(request.content)
    if not isinstance(body, list):
        return _refused()
    for entry in body:
        if not isinstance(entry, dict) or not entry.get("uid"):
            return _refused()
        # `date` is space-separated rather than ISO, and the server is strict.
        if not isinstance(entry.get("date"), str) or "T" in entry["date"]:
            return _refused()
    fake.meal_writes.append([dict(e) for e in body])
    by_uid = {m["uid"]: m for m in fake.meals}
    for entry in body:
        if entry.get("deleted"):
            by_uid.pop(entry["uid"], None)
        else:
            by_uid[entry["uid"]] = dict(entry)
    fake.meals = list(by_uid.values())
    fake.counters["meals"] = fake.counters.get("meals", 0) + 1
    return _result(True)


def _extract_gzipped_part(content: bytes) -> Any:
    """Pull the gzipped JSON out of a multipart body.

    ``gzip.decompress`` refuses a stream with anything after it, and a multipart
    body always has a closing boundary after it. ``zlib`` with a gzip window
    stops at the stream's own end marker and ignores the trailer, which is what
    a real server's multipart parser does too.

    Args:
        content: The whole multipart body.

    Returns:
        Any: The decoded object, or ``None`` when there isn't one.
    """
    marker = content.find(b"\x1f\x8b")
    if marker == -1:
        return None
    try:
        blob = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(content[marker:])
    except zlib.error:
        return None
    try:
        return json.loads(blob)
    except ValueError:
        return None
