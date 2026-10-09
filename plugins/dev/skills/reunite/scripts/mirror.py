"""Make every account's copy of a conversation byte-for-byte the same file.

A rename, a star, an archive or a model switch writes only the signed-in account's copy,
so after any stretch of work the copies of one conversation disagree. For each
conversation the most recently written copy is the one the user last touched: it
becomes the canonical content, carrying the archive flag the lifecycle pass settled on,
and every target account receives exactly those bytes — overwriting a stale copy, or
creating one where the account has none. A conversation deleted under one account is
removed from all of them.

Every overwritten or removed original is backed up first, and every written file takes
the canonical copy's mtime, so the copies stay identical down to the timestamp and a
later change by the user is the only thing that can make one of them newest.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from lifecycle import ARCHIVE_FIELD, Copy, LifecyclePlan
from manifest import manifest_path, save_backup


@dataclass(frozen=True)
class Write:
    """One file to bring onto a conversation's canonical content."""

    dest: Path
    content: bytes
    mtime: float
    created: bool
    fields: tuple[str, ...]


@dataclass(frozen=True)
class MirrorPlan:
    """Every write and removal a run would make."""

    writes: list[Write]
    removals: list[Path]


def canonical(winner: Path, want: bool | None) -> bytes:
    """The newest copy's bytes, with the settled archive flag written in when it differs."""
    raw = winner.read_bytes()
    if want is None:
        return raw
    data = json.loads(raw)
    if bool(data.get(ARCHIVE_FIELD)) == want:
        return raw
    data[ARCHIVE_FIELD] = want
    return json.dumps(data, separators=(",", ":")).encode()


def changed_fields(old: bytes, new: bytes) -> tuple[str, ...]:
    """The top-level keys whose values differ, for the report."""
    try:
        before, after = json.loads(old), json.loads(new)
    except ValueError:
        return ("(unreadable)",)
    return tuple(sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k)))


def plan_mirror(
    sessions: dict[str, list[Copy]],
    landing: dict[str, Path],
    targets: list[str],
    life: LifecyclePlan,
    authority: str | None = None,
) -> MirrorPlan:
    """Pair every target copy that differs from its conversation's canonical content.

    ``landing`` maps each target account to the org directory a new copy goes into. A
    conversation recorded as deleted is never created anywhere. With ``authority``, that
    account's copy is canonical instead of the newest one.
    """
    writes: list[Write] = []
    removals: list[Path] = []
    for sid, copies in sorted(sessions.items()):
        if sid in life.newly_deleted:
            removals.extend(c.path for c in copies if c.account in targets)
            continue
        ruling = [c for c in copies if c.account == authority]
        winner = ruling[0] if ruling else max(copies, key=lambda c: (c.mtime, c.account))
        content = canonical(winner.path, life.desired.get(sid))
        for target in targets:
            own = [c for c in copies if c.account == target]
            for copy in own:
                old = copy.path.read_bytes()
                if old != content:
                    writes.append(
                        Write(copy.path, content, winner.mtime, False, changed_fields(old, content))
                    )
            if not own and sid not in life.deleted and target in landing:
                writes.append(Write(landing[target] / winner.path.name, content, winner.mtime, True, ()))
    return MirrorPlan(writes, removals)


def apply_mirror(root: Path, plan: MirrorPlan, created_before: set[str]) -> tuple[list[str], list[dict]]:
    """Carry out the plan, returning the files created and the originals backed up.

    A file an earlier run created is not backed up: --undo removes it outright.
    """
    created: list[str] = []
    backups: list[dict] = []

    def back_up(path: Path) -> None:
        if manifest_path(root, str(path)) not in created_before and (record := save_backup(root, path)):
            backups.append(record)

    for path in plan.removals:
        back_up(path)
        path.unlink(missing_ok=True)
    for write in plan.writes:
        if write.created:
            write.dest.parent.mkdir(parents=True, exist_ok=True)
            created.append(str(write.dest))
        else:
            back_up(write.dest)
        write.dest.write_bytes(write.content)
        os.utime(write.dest, (write.mtime, write.mtime))
    return created, backups


def misaligned(sessions: dict[str, list[Copy]], targets: list[str], deleted: set[str]) -> list[str]:
    """Conversations whose target copies are missing or not byte-identical — expected empty."""
    wrong: list[str] = []
    for sid, copies in sorted(sessions.items()):
        own = [c for c in copies if c.account in targets]
        accounts = {c.account for c in own}
        missing = sid not in deleted and accounts != set(targets)
        if missing or len({c.path.read_bytes() for c in own}) > 1:
            wrong.append(sid)
    return wrong
