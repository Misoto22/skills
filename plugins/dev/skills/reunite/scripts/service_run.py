"""``--service-run``: one background pass, as the launchd agent runs it.

A pass aligns the index the way ``--apply`` does — never ``--from``, and with only the
baseline able to prove a deletion — then the environments, then, only while the app is
quit, the sidebar layout and stars. It does nothing at all until a manual ``--apply``
has recorded a baseline: the service keeps an alignment the user has seen, it does not
make the first one. Every write is recorded in the manifest like a manual run's.

It must be idempotent, because its own writes fire launchd's WatchPaths again: a run
right after a run writes nothing. Reading every index file costs far more than
noticing none changed, so a hash of each file's name, size and mtime is kept from the
last pass, and an unchanged tree is not read at all. One exclusive lock keeps two
passes — or a pass and a manual ``--apply`` — from running at once; a pass that finds
it taken exits at once, since the holder is doing the same work.

The state file is rewritten in place rather than renamed into place: a rename changes
the watched directory's entries, which would start the next pass at once.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import align
import environments_sync
import lifecycle
import sidebar_auto
import sidebar_sync
from environments import EnvironmentsError
from index_tree import flatten, scan, scopes_of, signed_in_account
from service import LOCK_NAME, STATE_NAME, log_path

LOG_LIMIT = 1_048_576


@contextmanager
def exclusive_run(root: Path) -> Iterator[bool]:
    """Hold the pass lock for the duration; yields False at once when someone else holds it."""
    with (root / LOCK_NAME).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def index_fingerprint(root: Path) -> str:
    """A hash of every index file's path, size and mtime — cheap, and moved by any change."""
    digest = hashlib.sha256()
    for account in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for org in sorted(p for p in account.iterdir() if p.is_dir()):
            for path in sorted(org.glob("local_*.json")):
                stat = path.stat()
                digest.update(
                    f"{account.name}/{org.name}/{path.name}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode()
                )
    return digest.hexdigest()


def _index(root: Path, state: dict, updates: dict) -> tuple[str, dict[str, str]]:
    fingerprint = index_fingerprint(root)
    if fingerprint == state.get("index") and isinstance(state.get("scopes"), dict):
        return "index: unchanged", state["scopes"]
    tree = scan(root)
    scopes = scopes_of(tree)
    if len(tree) < 2:
        updates.update(index=fingerprint, scopes=scopes)
        return "index: one account", scopes
    targets = list(tree)
    plan, life, _, created_before = align.plan_run(root, tree, targets, vanished=False)
    applied = align.apply_plan(root, plan, life, targets, created_before)
    if applied.misaligned:
        return f"index: NOT ALIGNED, {len(applied.misaligned)} conversations differ", scopes
    updates.update(index=index_fingerprint(root), scopes=scopes)
    if not (applied.created or applied.overwrote or applied.removed):
        return "index: unchanged", scopes
    return f"index: +{applied.created} ~{applied.overwrote} -{applied.removed}", scopes


def _environments(root: Path, accounts: list[str]) -> str:
    try:
        step = environments_sync.plan_step(root, accounts, True, int(time.time() * 1000))
        if step is None:
            return "environments: no file"
        environments_sync.apply_step(root, step)
    except EnvironmentsError as error:
        return f"environments: not aligned ({error})"
    changes = step.plan.changes
    frozen = f", {len(step.plan.frozen)} frozen" if step.plan.frozen else ""
    if not changes:
        return f"environments: unchanged{frozen}"
    added, updated = sum(c.added for c in changes), sum(c.updated for c in changes)
    return f"environments: +{added} ~{updated} -{sum(c.removed for c in changes)}{frozen}"


def _pass(root: Path, state: dict) -> tuple[str, dict]:
    if not (root / lifecycle.BASELINE_NAME).exists():
        return "index: waiting for a first manual --apply; nothing done", {}
    updates: dict = {}
    index, scopes = _index(root, state, updates)
    environments = _environments(root, sorted(scopes))
    previous = state.get("sidebar") if isinstance(state.get("sidebar"), dict) else None

    def held() -> dict[str, set[str]]:
        return sidebar_sync.held_sessions(flatten(scan(root)))

    side, hashes = sidebar_auto.step(root, scopes, previous, signed_in_account(), held)
    if hashes is not None:
        updates["sidebar"] = hashes
    return f"{index} | {environments} | sidebar: {side}", updates


def _load_state(root: Path) -> dict:
    try:
        state = json.loads((root / STATE_NAME).read_text())
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _rotate_log() -> None:
    log = log_path()
    try:
        if log.stat().st_size > LOG_LIMIT:
            os.replace(log, log.with_name(log.name + ".1"))
    except FileNotFoundError:
        return


def run(root: Path) -> int:
    """One pass under the lock; prints one line naming what changed. Returns the exit status."""
    with exclusive_run(root) as acquired:
        if not acquired:
            return 0
        state = _load_state(root)
        code = 0
        try:
            result, updates = _pass(root, state)
        except SystemExit as error:
            result, updates, code = f"error: {error.code}", {}, 1
        except Exception as error:
            result, updates, code = f"error: {type(error).__name__}: {error}", {}, 1
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        state.update(updates, lastRun=now, result=result)
        (root / STATE_NAME).write_text(json.dumps(state, separators=(",", ":")))
        _rotate_log()
        print(f"{now} {result}", flush=True)
        return code
