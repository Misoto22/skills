"""Decide each conversation's archive state, and which conversations were deleted.

The app archives or deletes only the signed-in account's copy of a conversation. What
the user changed is only knowable against what was there before, so every ``--apply``
records a baseline: which accounts held each conversation and whether each copy was
archived. The next run compares against it:

- a copy whose archive flag moved since the baseline was changed by the user, and the
  newest such change wins — archiving and unarchiving alike;
- an account that held a conversation and no longer does deleted it, and the
  conversation is removed from every account.

With no baseline yet, copies that disagree settle on archived: no recorded change says
which one is newer, and hiding a conversation is the recoverable way to be wrong. A
conversation whose transcript is gone opens to nothing, so it is always archived.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

BASELINE_NAME = ".session-merge-baseline.json"
ARCHIVE_FIELD = "isArchived"


@dataclass(frozen=True)
class Copy:
    """One account's index file for a conversation, reduced to what the plan reads."""

    account: str
    path: Path
    archived: bool
    mtime: float


@dataclass
class Baseline:
    """The state the previous --apply left behind."""

    held: dict[str, dict[str, bool]] = field(default_factory=dict)
    deleted: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class LifecyclePlan:
    """The archive flag each conversation settles on, and the ones that were deleted."""

    desired: dict[str, bool]
    deleted: set[str]
    newly_deleted: set[str]


def copies_by_session(entries: Iterable[object]) -> dict[str, list[Copy]]:
    """Group index entries by conversation; the account is the path's third-from-last part."""
    grouped: dict[str, list[Copy]] = defaultdict(list)
    for entry in entries:
        path = entry.path
        grouped[entry.session_id].append(Copy(path.parts[-3], path, entry.archived, entry.mtime))
    return dict(grouped)


def load_baseline(root: Path) -> Baseline | None:
    """Read the previous run's baseline, or None when there has been no --apply yet."""
    try:
        data = json.loads((root / BASELINE_NAME).read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise SystemExit(f"Unreadable {BASELINE_NAME} under {root}: {error}") from error
    held = data.get("held") if isinstance(data, dict) else None
    deleted = data.get("deleted") if isinstance(data, dict) else None
    if not isinstance(held, dict) or not isinstance(deleted, list):
        raise SystemExit(f"{BASELINE_NAME} under {root} is not a baseline this script wrote.")
    return Baseline(
        held={sid: {a: bool(v) for a, v in accounts.items()} for sid, accounts in held.items()},
        deleted={sid for sid in deleted if isinstance(sid, str)},
    )


def save_baseline(root: Path, sessions: dict[str, list[Copy]], deleted: set[str]) -> None:
    """Record what is on disk now, so the next run can tell what the user changed."""
    held = {sid: {c.account: c.archived for c in copies} for sid, copies in sorted(sessions.items())}
    payload = {"held": held, "deleted": sorted(deleted)}
    (root / BASELINE_NAME).write_text(json.dumps(payload, separators=(",", ":")))


def vanished_copies(root: Path, copied: list[str]) -> dict[str, set[str]]:
    """Conversations whose merged copy is gone from disk: the user deleted it there.

    This is the only deletion signal available before a baseline exists, and it covers
    exactly the files an earlier merge wrote.
    """
    gone: dict[str, set[str]] = defaultdict(set)
    for relative in copied:
        path = root / relative
        if not path.exists():
            gone[path.stem.removeprefix("local_")].add(path.parts[-3])
    return dict(gone)


def desired_archive(copies: list[Copy], before: dict[str, bool] | None) -> bool | None:
    """The archive flag every copy should carry, or None when the copies already agree."""
    if before:
        changed = [c for c in copies if c.account in before and before[c.account] != c.archived]
        if changed:
            return max(changed, key=lambda c: c.mtime).archived
    if len({c.archived for c in copies}) > 1:
        return True
    return None


def plan_lifecycle(
    sessions: dict[str, list[Copy]],
    accounts: set[str],
    baseline: Baseline | None,
    vanished: dict[str, set[str]],
    orphans: set[str],
) -> LifecyclePlan:
    """Settle each conversation's archive flag and find the ones deleted under some account.

    ``accounts`` is every account directory on disk, including one whose last conversation
    was just deleted. An account missing from it altogether is not counted as having
    deleted anything: a signed-out or wiped account says nothing about one conversation.

    A deletion stays recorded so no later run copies the conversation back, unless it
    reappears where the baseline had none of it — the user resumed it, and it is live.
    """
    held = baseline.held if baseline else {}
    prior = baseline.deleted if baseline else set()
    prior_deleted = {sid for sid in prior if sid not in sessions or sid in held}
    desired: dict[str, bool] = {}
    newly: set[str] = set()
    for sid, copies in sessions.items():
        present = {c.account for c in copies}
        before = held.get(sid)
        gone = (set(before or ()) | vanished.get(sid, set())) & (accounts - present)
        if gone and sid not in prior_deleted:
            newly.add(sid)
            continue
        want = True if sid in orphans else desired_archive(copies, before)
        if want is not None:
            desired[sid] = want
    return LifecyclePlan(desired, prior_deleted | newly, newly)


def authoritative_plan(sessions: dict[str, list[Copy]], authority: str) -> LifecyclePlan:
    """Take one account's index as the whole truth: its flags win, and what it lacks is deleted.

    This is the reset for an index tree that has drifted past reconciling — the user
    names the account whose sidebar is right, and every other account becomes a copy
    of it. No baseline or mtime is consulted.
    """
    desired: dict[str, bool] = {}
    removed: set[str] = set()
    for sid, copies in sessions.items():
        own = [c for c in copies if c.account == authority]
        if own:
            desired[sid] = own[0].archived
        else:
            removed.add(sid)
    return LifecyclePlan(desired, removed, removed)
