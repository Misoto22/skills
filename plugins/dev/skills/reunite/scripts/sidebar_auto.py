"""The service's sidebar step: copy whichever account's layout changed since the last run.

A manual ``--sidebar-from`` names its source. The service has nobody to ask, so it keeps
a hash of each account's layout and stars from its previous run and treats the one
account whose hash moved as the source. When several moved, the account the app last
signed in to (``lastKnownAccountUuid``) is the one the user was looking at; when it is
not among them, nothing is copied. A first run, and an account first seen now, only
record a hash — a fresh account's empty layout must never overwrite the others.

Like the manual step it writes only while the app is fully quit; while it runs, the
recorded hashes are kept as they were, so the change is still pending next time.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from collections.abc import Callable
from pathlib import Path

import ldb_store
import local_storage
import sidebar
import sidebar_sync
import stars
from ldb_codec import LevelDBError


def store_path() -> Path:
    """The Local Storage directory, without exiting when it is missing."""
    return Path(os.environ.get(local_storage.STORE_ENV, local_storage.DEFAULT_STORE)).expanduser()


def fingerprints(store: Path, scopes: dict[str, str]) -> dict[str, str]:
    """A hash per account of its scope's layout, its group names and its starred environments."""
    accounts = sorted(scopes)
    values = ldb_store.read_many(store, [sidebar.STORE_KEY, *(stars.key(a) for a in accounts)])
    raw = values[sidebar.STORE_KEY]
    state = sidebar.decode(raw)["state"] if raw is not None else {}
    layouts = state.get(sidebar.SECTIONS_BY_SCOPE) or {}
    groups = state.get(sidebar.GROUPS_BY_SCOPE) or {}
    result = {}
    for account in accounts:
        starred = values[stars.key(account)]
        payload = [layouts.get(scopes[account]), groups.get(scopes[account]), starred and starred.hex()]
        result[account] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return result


def _moved(previous: dict[str, str], current: dict[str, str]) -> list[str]:
    return sorted(a for a in current if a in previous and current[a] != previous[a])


def choose_source(
    previous: dict[str, str] | None, current: dict[str, str], signed_in: str | None
) -> str | None:
    """The account whose layout changed since the last run, or None when that is not one account."""
    if previous is None:
        return None
    moved = _moved(previous, current)
    if len(moved) == 1:
        return moved[0]
    return signed_in if signed_in in moved else None


def step(
    root: Path,
    scopes: dict[str, str],
    previous: dict[str, str] | None,
    signed_in: str | None,
    held: Callable[[], dict[str, set[str]]],
) -> tuple[str, dict[str, str] | None]:
    """One pass: the log fragment, and the hashes to record — None keeps the previous ones."""
    store = store_path()
    if not (store / "CURRENT").is_file():
        return "no Local Storage", None
    if local_storage.app_running():
        return "waiting for Claude to quit", None
    try:
        with local_storage.exclusive(store):
            return _copy(root, store, scopes, previous, signed_in, held)
    except SystemExit:
        return "waiting for Claude to quit", None
    except (LevelDBError, sidebar.SidebarError) as error:
        return f"not read ({error})", None


def _copy(root, store, scopes, previous, signed_in, held) -> tuple[str, dict[str, str] | None]:
    current = fingerprints(store, scopes)
    if previous is None:
        return "recorded", current
    source = choose_source(previous, current, signed_in)
    if source is None:
        moved = _moved(previous, current)
        return ("unchanged" if not moved else f"changed in {len(moved)} accounts; none copied"), current
    plan = sidebar_sync.plan_copy(store, source, scopes, held())
    if not plan.changed:
        return f"from {source[:8]}: already identical", current
    with contextlib.redirect_stdout(io.StringIO()):
        failed = sidebar_sync.write(root, store, plan)
    if failed:
        return "write did not read back and was rolled back", None
    receivers = len({c.account for c in plan.changes if c.changed} | {s.account for s in plan.star_changes})
    return f"from {source[:8]} to {receivers} account(s)", fingerprints(store, scopes)
