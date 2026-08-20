"""Handles — how a recipe is named in the session, since its uid never is."""

from __future__ import annotations

from paprika_core.handles import derive_handles


def test_handles_are_derived_and_short() -> None:
    uids = ["8F2A1C4E-0001-4A1B-9C3D-1A2B3C4D5E6F"]

    assert derive_handles(uids)[uids[0]] == "8f2a1c"


def test_colliding_handles_lengthen_rather_than_clash() -> None:
    """Uniqueness is a property of the whole Library, not of any one uid."""
    uids = ["8F2A1C4E-0001-AAAA", "8F2A1C4E-0002-BBBB", "9999AAAA-0003-CCCC"]

    handles = derive_handles(uids)

    assert len(set(handles.values())) == 3
    assert handles["9999AAAA-0003-CCCC"] == "9999aa"


def test_a_uid_with_no_hex_still_gets_a_handle() -> None:
    """Nothing is ever silently dropped for want of a derivable name."""
    handles = derive_handles(["ZZZZ", "8F2A1C4E-0001-AAAA"])

    assert handles["ZZZZ"] == "zzzz"


def test_handles_are_stable_across_calls() -> None:
    uids = ["8F2A1C4E-0001-AAAA", "9999AAAA-0003-CCCC"]

    assert derive_handles(uids) == derive_handles(reversed(uids))
