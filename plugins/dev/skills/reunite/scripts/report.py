"""What a run prints before it writes: the index on disk, and what --apply would change."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import lifecycle
import mirror
from index_tree import Entry, landing_org, transcripts_dir

REPORTED_FIELDS = ("title", "isArchived", "isStarred")


def human(size: float) -> str:
    """Byte count as the report should read it."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def report_state(root: Path, tree: dict[str, dict[str, list[Entry]]], current: str | None) -> None:
    """Print what is on disk before anything is written."""
    print(f"Session index {root}")
    for account, orgs in tree.items():
        total = sum(len(e) for e in orgs.values())
        landing = landing_org(orgs)
        mark = "  <- signed in" if account == current else ""
        print(f"  account {account}  {total:>4} conversations  lands in {landing}{mark}")


def report_plan(
    plan: mirror.MirrorPlan, life: lifecycle.LifecyclePlan, targets: list[str], orphans: int | None
) -> None:
    """Print what --apply would write, broken down by the fields a sidebar shows."""
    created = [w for w in plan.writes if w.created]
    updated = [w for w in plan.writes if not w.created]
    added = sum(len(w.content) for w in created)
    print(f"\nPlan: align {len(targets)} account index(es)")
    print(f"  {len(created)} copies to create, +{human(added)}")
    print(f"  {len(updated)} copies to overwrite with the canonical copy")
    fields = Counter(f for w in updated for f in w.fields)
    for name in REPORTED_FIELDS:
        print(f"    {fields.pop(name, 0):>5} change {name}")
    other = sum(1 for w in updated if set(w.fields) - set(REPORTED_FIELDS))
    print(f"    {other:>5} change other fields only the app reads")
    deleted = len(life.newly_deleted)
    print(f"  {len(plan.removals)} copies to remove — {deleted} conversations deleted under one account")
    if orphans is None:
        print(f"  orphan detection skipped: no transcripts found under {transcripts_dir()}")
    elif orphans:
        print(f"  {orphans} conversations have no transcript left; archived unless --from says otherwise")
    titled = [w for w in updated if "title" in w.fields]
    for write in titled[:10]:
        title = json.loads(write.content).get("title") or "(untitled)"
        print(f"    {write.dest.parent.parent.name[:8]}  → {title}")
    if len(titled) > 10:
        print(f"    … and {len(titled) - 10} more")
