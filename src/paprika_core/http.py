"""The wire. Everything Paprika's API does wrong is handled exactly here.

Four facts drive this module, all of them established in
``docs/research/paprika-v2-api-surface.md``:

1. **The v2 API gates on User-Agent.** An unrecognised one gets
   ``{"error": {"message": "Unrecognized client."}}`` at a 200. The match is a
   prefix, so appending our own name still gets in.
2. **Never trust the status code in either direction.** Parse every body. An
   ``error`` key at a success status is a failure; a genuine 500 is one too.
3. **Responses may or may not be gzipped**, and ``Content-Encoding`` does not
   reliably say which. Sniff the magic bytes.
4. **Login is form-encoded, against v1**, which has no User-Agent check and no
   receipt check — the intersection of every client's success path.

Nothing in here ever raises anything but :class:`PaprikaError`, and the sentences
it raises are already fit to say to her.
"""

from __future__ import annotations

import gzip
import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from paprika_core.errors import Code, PaprikaError
from paprika_core.log import log_event

BASE_URL = "https://www.paprikaapp.com"

#: Paprika's own iOS app string, with ours appended. The gate is a prefix match,
#: so this identifies us honestly and still gets through.
USER_AGENT = (
    "Paprika 3/3.8.5 (com.hindsightlabs.paprika.ios.v3; build:80; iOS 26.5.2) "
    "Alamofire/5.2.2 paprika-plugin/0.1.0"
)

LOGIN_PATH = "/api/v1/account/login/"
STATUS_PATH = "/api/v2/sync/status/"
CATEGORIES_PATH = "/api/v2/sync/categories/"
RECIPE_INDEX_PATH = "/api/v2/sync/recipes/"

#: Test seam. A fixture points this at a fake so no test can reach the network by
#: forgetting to. Production never sets it.
TRANSPORT: httpx.BaseTransport | None = None

_GZIP_MAGIC = b"\x1f\x8b"

_UNREACHABLE = "We couldn't reach Paprika just now."
_UNREADABLE = "Paprika sent back something we couldn't read."
_REFUSED = "Paprika wouldn't do that."


def _decode(content: bytes) -> bytes:
    """Decompress a response body when it is gzipped.

    Sniffs the magic bytes rather than trusting ``Content-Encoding``, because the
    header is not reliable on this API.

    Args:
        content: The raw response bytes.

    Returns:
        bytes: The body, decompressed if it needed to be.
    """
    if content[:2] == _GZIP_MAGIC:
        try:
            return gzip.decompress(content)
        except OSError:
            return content
    return content


def parse_body(response: httpx.Response, attempted: str) -> Any:
    """Turn a response into a result, or into a failure.

    The status code is evidence, never a verdict. The body is parsed whatever the
    status said, an ``error`` key fails the call at any status, and a status that
    failed with no parseable error still fails.

    Args:
        response: The response to read.
        attempted: What was being done, for the log.

    Returns:
        Any: The value under ``result``, or the whole body when there is no
            ``result`` key.

    Raises:
        PaprikaError: When the body carries an error, or cannot be read, or the
            status failed and said nothing useful.
    """
    payload = _decode(response.content)
    body: Any
    try:
        body = json.loads(payload) if payload else None
    except ValueError:
        log_event(
            "response_unreadable",
            attempted=attempted,
            status=response.status_code,
            bytes=len(payload),
        )
        # A genuine 5xx with an unreadable body — which is what a malformed write
        # earns, naming no field — is a refusal, not a garbled success.
        raise PaprikaError(
            Code.PAPRIKA_REFUSED,
            _REFUSED if response.status_code >= 400 else _UNREADABLE,
            detail=f"unparseable body at HTTP {response.status_code}",
            status=response.status_code,
        ) from None

    if isinstance(body, dict) and "error" in body:
        raise _from_error_body(body["error"], response.status_code, attempted)

    if response.status_code >= 400:
        log_event(
            "response_failed",
            attempted=attempted,
            status=response.status_code,
        )
        raise PaprikaError(
            Code.PAPRIKA_REFUSED,
            _REFUSED,
            detail=f"HTTP {response.status_code} with no error body",
            status=response.status_code,
        )

    if isinstance(body, dict) and "result" in body:
        return body["result"]
    return body


def _from_error_body(error: Any, status: int, attempted: str) -> PaprikaError:
    """Build a failure from Paprika's own error object.

    Paprika's wording is kept for the log and thrown away for the envelope: the
    session never sees ``Unrecognized client.``

    Args:
        error: The value of the body's ``error`` key.
        status: The HTTP status it arrived at, for the log.
        attempted: What was being done, for the log.

    Returns:
        PaprikaError: The failure to raise.
    """
    said = ""
    code = None
    if isinstance(error, dict):
        said = str(error.get("message", ""))
        code = error.get("code")
    elif error is not None:
        said = str(error)

    log_event(
        "paprika_error",
        attempted=attempted,
        status=status,
        paprika_code=code,
        paprika_message=said,
    )
    return PaprikaError(
        Code.PAPRIKA_REFUSED,
        _REFUSED,
        detail=f"HTTP {status}: {said}",
        status=status,
        said=said,
    )


#: What Paprika says when the session, rather than the request, is the problem.
#: Matched on rather than on the status, because this API refuses at a 200 as
#: readily as at a 401.
_SESSION_WORDS = ("session", "unauthorized", "not authorized", "token", "log in")


def is_a_stale_session(error: PaprikaError) -> bool:
    """Decide whether a refusal was about the session rather than the request.

    Narrow on purpose. Treating any refusal as a stale session would eventually
    mean re-sending a write Paprika had already refused once, which is the one
    retry this plugin must never make.

    Args:
        error: The refusal.

    Returns:
        bool: Whether signing in again is worth trying.
    """
    if error.code != Code.PAPRIKA_REFUSED:
        return False
    if error.status == 401:
        return True
    said = (error.said or "").lower()
    return any(word in said for word in _SESSION_WORDS)


class PaprikaClient:
    """A client for the two-and-a-half endpoints the skeleton needs.

    Args:
        token: A bearer token, when one is already held.
        renew: Called to obtain a fresh token when the session turns out to be
            stale. The retry sits here, around **one request**, rather than
            around a caller's whole run — a cold sync that re-ran from the top
            would discard every recipe it had already committed.
    """

    def __init__(
        self,
        token: str | None = None,
        renew: Callable[[], str] | None = None,
    ) -> None:
        self.token = token
        self._renew = renew
        self._client = httpx.Client(
            base_url=BASE_URL,
            transport=TRANSPORT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            # httpx defaults to five seconds. That is a cap nobody here chose,
            # and a cold sync of five hundred recipes should wait as long as
            # Paprika takes rather than be cut off by a number in a library.
            timeout=None,
        )

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._client.close()

    def _send(
        self,
        method: str,
        path: str,
        attempted: str,
        *,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        authenticate: bool = True,
        _renewed: bool = False,
    ) -> Any:
        """Send one request and parse whatever comes back.

        Every request in the plugin goes through here, so the logging, the
        transport-failure sentence and the body parsing exist once.

        Args:
            method: The HTTP method.
            path: The path, trailing slash included — they are load-bearing.
            attempted: What is being done, for the log.
            data: Form fields, for the login post.
            files: Multipart parts, for a gzipped write.
            authenticate: Whether to attach the bearer token.
            _renewed: Set on the one retry after a renewal, so a session that
                stays stale fails rather than looping.

        Returns:
            Any: The parsed result.

        Raises:
            PaprikaError: On a transport failure or on anything the body says.
        """
        headers: dict[str, str] = {}
        if authenticate and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        started = time.monotonic()
        try:
            response = self._client.request(
                method, path, data=data, files=files, headers=headers
            )
        except httpx.HTTPError as exc:
            log_event("request_failed", attempted=attempted, method=method, path=path)
            raise PaprikaError(
                Code.PAPRIKA_UNREACHABLE, _UNREACHABLE, detail=repr(exc)
            ) from exc

        log_event(
            "request",
            attempted=attempted,
            method=method,
            path=path,
            status=response.status_code,
            ms=round((time.monotonic() - started) * 1000, 1),
        )
        try:
            return parse_body(response, attempted)
        except PaprikaError as refusal:
            if _renewed or self._renew is None or not is_a_stale_session(refusal):
                raise
            # An expired session is not a failure she should ever hear about.
            log_event("reauth", attempted=attempted, reason=refusal.detail)
            self.token = self._renew()
            return self._send(
                method,
                path,
                attempted,
                data=data,
                files=files,
                authenticate=authenticate,
                _renewed=True,
            )

    def login(self, email: str, password: str) -> str:
        """Exchange her email and password for a bearer token.

        Form-encoded against v1, which has neither the User-Agent check nor the
        receipt check. The app-prefixed User-Agent is sent anyway, because
        everything after this depends on it.

        Args:
            email: Her Paprika account email.
            password: Her Paprika account password.

        Returns:
            str: The bearer token.

        Raises:
            PaprikaError: ``credentials_rejected`` when Paprika refuses the pair;
                the transport codes otherwise.
        """
        try:
            result = self._send(
                "POST",
                LOGIN_PATH,
                "signing in to Paprika",
                data={"email": email, "password": password},
                authenticate=False,
            )
        except PaprikaError as exc:
            if exc.code == Code.PAPRIKA_REFUSED:
                raise PaprikaError(
                    Code.CREDENTIALS_REJECTED,
                    "Paprika didn't accept that email and password.",
                    detail=exc.detail,
                ) from exc
            raise

        token = result.get("token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            raise PaprikaError(
                Code.CREDENTIALS_REJECTED,
                "Paprika didn't accept that email and password.",
                detail="login succeeded but returned no token",
            )
        self.token = token
        return token

    def get(self, path: str, attempted: str) -> Any:
        """Read one collection or one object.

        Args:
            path: The path, trailing slash included.
            attempted: What is being done, for the log.

        Returns:
            Any: The parsed result.
        """
        return self._send("GET", path, attempted)

    def _post_object(
        self,
        path: str,
        payload: Any,
        attempted: str,
        image: bytes | None = None,
    ) -> Any:
        """Write one object, gzipped, as the API insists.

        Every sync write is a ``multipart/form-data`` post whose ``data`` part is
        gzipped JSON delivered as a file. This is the **transport half only**.
        What may legally be sent through it is the chokepoint's business, not
        this module's — no caller outside the core ever reaches this, and no
        public API accepts a caller-assembled object.

        Args:
            path: The path, trailing slash included.
            payload: The object or array to send.
            attempted: What is being done, for the log.
            image: JPEG bytes to send alongside, when the object carries a
                picture. Which objects legally may is the chokepoint's
                business, not this module's.

        Returns:
            Any: The parsed result.
        """
        blob = gzip.compress(json.dumps(payload).encode("utf-8"))
        parts: dict[str, tuple[str, bytes, str]] = {
            "data": ("file", blob, "application/octet-stream")
        }
        if image is not None:
            # A picture rides in the same request as the object it belongs to,
            # which is the API's design and a good one: there is no window in
            # which a photo has landed against a recipe that has not.
            parts["photo_upload"] = ("photo.jpg", image, "image/jpeg")
        return self._send("POST", path, attempted, files=parts)
