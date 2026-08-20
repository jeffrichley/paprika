"""Getting signed in, without ever asking her to.

Preconditions live here rather than in a skill: one place that knows what "not
set up" means, one sentence that says so.

A token that has gone stale is not a failure. The client renews it and retries
the **one request** that hit it — never the caller's whole run, because a cold
sync restarted from the top would discard every recipe it had already committed.
"""

from __future__ import annotations

from paprika_core import store
from paprika_core.http import PaprikaClient


def sign_in() -> PaprikaClient:
    """Return a client that is signed in and can renew itself.

    A stored token is trusted rather than probed: the cheap liveness check is a
    request we would be making anyway, and the renewal hook handles the case
    where the trust was misplaced.

    Returns:
        PaprikaClient: A client carrying a bearer token.

    Raises:
        PaprikaError: ``not_set_up`` when there are no credentials to use;
            ``credentials_rejected`` when Paprika refuses them.
    """
    email, password = store.credentials()

    def renew() -> str:
        """Sign in again and persist the result.

        Uses its own client so a renewal can never recurse through the one
        that asked for it.

        Returns:
            str: A fresh bearer token.
        """
        store.clear_token()
        fresh = PaprikaClient()
        try:
            token = fresh.login(email, password)
        finally:
            fresh.close()
        store.save_token(token)
        return token

    held = store.read_token()
    return PaprikaClient(token=held or renew(), renew=renew)
