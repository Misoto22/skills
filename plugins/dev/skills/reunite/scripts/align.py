"""Plan and apply one alignment of the index: the step a manual --apply and the service share."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lifecycle
import mirror
from index_tree import flatten, landing_org, scan, transcript_ids, transcripts_dir
from manifest import MANIFEST_NAME, read_manifest, write_manifest


@dataclass(frozen=True)
class Applied:
    """What one --apply wrote, and what the rescan after it found."""

    created: int
    overwrote: int
    removed: int
    conversations: int
    misaligned: list[str]
    manifest: Path


def plan_run(root: Path, tree, targets: list[str], authority: str | None = None, vanished: bool = True):
    """Settle archive state and deletions, then plan the writes that align the targets.

    ``vanished`` lets a copy an earlier merge created, now gone, count as a deletion —
    the only signal from before a baseline existed. The service turns it off, so that
    only the baseline can prove a deletion there.
    """
    entries = flatten(tree)
    live = transcript_ids(transcripts_dir())
    # No transcripts at all means the store is elsewhere or unreadable, not that every
    # conversation lost its own; archiving all of them on that evidence would be wrong.
    orphans = {e.session_id for e in entries if e.cli_session_id not in live} if live else set()
    sessions = lifecycle.copies_by_session(entries)
    copied_before = read_manifest(root, root / MANIFEST_NAME)[0]
    if authority:
        life = lifecycle.authoritative_plan(sessions, authority)
    else:
        life = lifecycle.plan_lifecycle(
            sessions,
            set(tree),
            lifecycle.load_baseline(root),
            lifecycle.vanished_copies(root, copied_before) if vanished else {},
            orphans,
        )
    landing = {a: root / a / org for a in targets if (org := landing_org(tree[a])) is not None}
    plan = mirror.plan_mirror(sessions, landing, targets, life, authority)
    return plan, life, len(orphans) if live else None, set(copied_before)


def apply_plan(root: Path, plan, life, targets: list[str], created_before: set[str]) -> Applied:
    """Write the plan, record it for --undo, save the baseline, and rescan to verify."""
    created, backups = mirror.apply_mirror(root, plan, created_before)
    # Only a run that wrote something changes the record, so a run with nothing to do writes nothing.
    manifest = write_manifest(root, created, backups) if created or backups else root / MANIFEST_NAME
    after = lifecycle.copies_by_session(flatten(scan(root)))
    # Recorded even when nothing was written: without it, the next deletion is invisible.
    lifecycle.save_baseline(root, after, life.deleted)
    wrong = mirror.misaligned(after, targets, life.deleted)
    return Applied(
        len(created), len(plan.writes) - len(created), len(plan.removals), len(after), wrong, manifest
    )
