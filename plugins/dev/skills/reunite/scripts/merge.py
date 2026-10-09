#!/usr/bin/env python3
"""Align the desktop app's per-account conversation indexes onto one identical set.

Claude's desktop app keeps one conversation index per signed-in account under

    ~/Library/Application Support/Claude/claude-code-sessions/<account>/<org>/local_*.json

so signing in as a second account hides the first account's conversations from the
sidebar, and a rename, archive or deletion made under one account never reaches the
others. The transcripts themselves live in ~/.claude/projects/ keyed by working
directory and carry no account field at all, which is why `claude --resume` still
lists every one of them. Only the index is partitioned.

This makes every account hold the same conversations with byte-identical index files:
the copy the user touched last wins, an archive or deletion under one account reaches
all of them, and an entry whose transcript is gone is kept but archived. Every file it
creates and every original it overwrites or removes is recorded, so `--undo` puts the
tree back. Transcripts are never touched.

The desktop app reads the index at startup and does not rescan it while running, so a
run lands in the sidebar only after the app restarts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lifecycle
import mirror
from manifest import BACKUP_DIR, MANIFEST_NAME, index_path, read_manifest, restore_backups, write_manifest

SESSIONS_ROOT_ENV = "CLAUDE_DESKTOP_SESSIONS_DIR"
DEFAULT_ROOT = "~/Library/Application Support/Claude/claude-code-sessions"
DESKTOP_CONFIG = "~/Library/Application Support/Claude/config.json"
TITLE_FIELDS = ("title", "titleSource", "previousTitles")
REPORTED_FIELDS = ("title", "isArchived", "isStarred")


@dataclass(frozen=True)
class Entry:
    """One `local_*.json` index file — the sidebar's record of a conversation."""

    path: Path
    session_id: str
    cli_session_id: str | None
    last_activity: int
    mtime: float
    archived: bool = False


def sessions_root() -> Path:
    """Locate the desktop app's index directory, or exit saying it is not there."""
    root = Path(os.environ.get(SESSIONS_ROOT_ENV, DEFAULT_ROOT)).expanduser()
    if not root.is_dir():
        sys.exit(
            f"No desktop session index at {root}\n"
            f"  Set {SESSIONS_ROOT_ENV} if the app stores it elsewhere on this platform."
        )
    return root


def read_entry(path: Path) -> Entry | None:
    """Parse one index file. Returns None for the non-session JSON the app keeps here."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    session_id = data.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        return None
    return Entry(
        path=path,
        session_id=session_id,
        cli_session_id=data.get("cliSessionId"),
        last_activity=data.get("lastActivityAt") or 0,
        mtime=path.stat().st_mtime,
        archived=bool(data.get(lifecycle.ARCHIVE_FIELD)),
    )


def scan(root: Path) -> dict[str, dict[str, list[Entry]]]:
    """Map account -> org -> entries, skipping this script's own dot-directories."""
    tree: dict[str, dict[str, list[Entry]]] = {}
    for account in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        orgs: dict[str, list[Entry]] = {}
        for org in sorted(p for p in account.iterdir() if p.is_dir()):
            entries = [e for e in (read_entry(f) for f in org.glob("local_*.json")) if e]
            orgs[org.name] = entries
        if orgs:
            tree[account.name] = orgs
    return tree


def flatten(tree: dict[str, dict[str, list[Entry]]]) -> list[Entry]:
    """Every entry under every account and org."""
    return [e for orgs in tree.values() for entries in orgs.values() for e in entries]


def transcript_ids() -> set[str]:
    """Every CLI session id that still has a transcript under ~/.claude/projects/."""
    projects = Path("~/.claude/projects").expanduser()
    if not projects.is_dir():
        return set()
    found: set[str] = set()
    for project in projects.iterdir():
        if not project.is_dir():
            continue
        try:
            found.update(f.stem for f in project.glob("*.jsonl"))
        except OSError:
            continue
    return found


def landing_org(orgs: dict[str, list[Entry]]) -> str | None:
    """The org subdirectory this account last worked in — where the app will look."""
    active = {name: entries for name, entries in orgs.items() if entries}
    if not active:
        return next(iter(orgs), None)
    return max(active, key=lambda name: max(e.last_activity for e in active[name]))


def signed_in_account() -> str | None:
    """The account whose index the desktop app is writing, or None if it cannot be read.

    The desktop app and the `claude` CLI hold their own logins and are routinely on
    different accounts, so `~/.claude.json` answers a different question: it names the
    account the CLI authenticates as, not the one whose sidebar is on screen. The app
    records its own in `config.json` as `lastKnownAccountUuid`, and that is the index a
    rename lands in. Fall back to the CLI's only when the app has recorded nothing.
    """
    for path, read in (
        (DESKTOP_CONFIG, lambda d: d.get("lastKnownAccountUuid")),
        ("~/.claude.json", lambda d: (d.get("oauthAccount") or {}).get("accountUuid")),
    ):
        try:
            account = read(json.loads(Path(path).expanduser().read_text()))
        except (OSError, ValueError):
            continue
        if isinstance(account, str) and account:
            return account
    return None


def human(size: int) -> str:
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
    plan: mirror.MirrorPlan, life: lifecycle.LifecyclePlan, targets: list[str], orphans: int
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
    if orphans:
        print(f"  {orphans} conversations have no transcript left; archived unless --from says otherwise")
    titled = [w for w in updated if "title" in w.fields]
    for write in titled[:10]:
        title = json.loads(write.content).get("title") or "(untitled)"
        print(f"    {write.dest.parent.parent.name[:8]}  → {title}")
    if len(titled) > 10:
        print(f"    … and {len(titled) - 10} more")


def undo(root: Path) -> int:
    """Remove the files previous runs created and restore every original they replaced."""
    manifest = root / MANIFEST_NAME
    copied, titles, backups = read_manifest(root, manifest)
    if not copied and not titles and not backups:
        print(f"Nothing to undo — no {MANIFEST_NAME} under {root}")
        return 0
    removed = 0
    for path in copied:
        target = index_path(root, path)
        if target is None:
            continue
        try:
            target.unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as error:
            print(f"  could not remove {path}: {error}", file=sys.stderr)
    restored = restore_backups(root, backups, set(copied))
    retitled = restore_titles(root, titles)
    (root / lifecycle.BASELINE_NAME).unlink(missing_ok=True)
    manifest.unlink(missing_ok=True)
    print(f"Removed {removed} of {len(copied)} created entries.")
    print(f"Restored {restored} of {len(backups)} originals.")
    if titles:
        print(f"Restored {retitled} of {len(titles)} replaced titles.")
    print("Restart the desktop app.")
    return 0


def restore_titles(root: Path, titles: list[dict[str, object]]) -> int:
    """Put back titles recorded by a run from before whole files were mirrored."""
    restored = 0
    for record in titles:
        path = index_path(root, record.get("path"))
        if path is None or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for field in TITLE_FIELDS:
            if record.get(field) is None:
                data.pop(field, None)
            else:
                data[field] = record[field]
        stat = path.stat()
        path.write_text(json.dumps(data, separators=(",", ":")))
        os.utime(path, (stat.st_atime, stat.st_mtime))
        restored += 1
    return restored


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the plan (default: report only)")
    parser.add_argument("--undo", action="store_true", help="put back everything previous runs changed")
    parser.add_argument(
        "--into",
        default="all",
        help="which account indexes are aligned: 'all' (default), 'current', or an accountUuid",
    )
    parser.add_argument(
        "--from",
        dest="authority",
        help="make one account the whole truth: 'current' or an accountUuid; what it lacks is deleted",
    )
    return parser.parse_args()


def resolve_targets(tree: dict[str, dict[str, list[Entry]]], into: str, current: str | None) -> list[str]:
    """Turn --into into the account directories that will be written."""
    if into == "all":
        return list(tree)
    if into == "current":
        if current is None:
            sys.exit("Cannot read the signed-in account — pass --into=<accountUuid>.")
        if current not in tree:
            sys.exit(f"Signed-in account {current} has no index directory yet — open one conversation first.")
        return [current]
    if into not in tree:
        sys.exit(f"No index directory for account {into}. Known: {', '.join(tree)}")
    return [into]


def plan_run(root: Path, tree, targets: list[str], authority: str | None = None):
    """Settle archive state and deletions, then plan the writes that align the targets."""
    entries = flatten(tree)
    live = transcript_ids()
    orphans = {e.session_id for e in entries if e.cli_session_id not in live}
    sessions = lifecycle.copies_by_session(entries)
    copied_before = read_manifest(root, root / MANIFEST_NAME)[0]
    if authority:
        life = lifecycle.authoritative_plan(sessions, authority)
    else:
        life = lifecycle.plan_lifecycle(
            sessions,
            set(tree),
            lifecycle.load_baseline(root),
            lifecycle.vanished_copies(root, copied_before),
            orphans,
        )
    landing = {a: root / a / org for a in targets if (org := landing_org(tree[a])) is not None}
    plan = mirror.plan_mirror(sessions, landing, targets, life, authority)
    return plan, life, len(orphans), set(copied_before)


def main() -> int:
    args = parse_args()
    root = sessions_root()
    if args.undo:
        return undo(root)

    tree = scan(root)
    if len(tree) < 2:
        print(f"Only one account index under {root} — nothing to align.")
        return 0

    current = signed_in_account()
    report_state(root, tree, current)
    targets = resolve_targets(tree, args.into, current)
    if args.authority == "all":
        sys.exit("--from names one account: 'current' or an accountUuid.")
    authority = resolve_targets(tree, args.authority, current)[0] if args.authority else None
    if authority:
        print(f"\nAuthority: {authority} — every other account becomes a copy of it.")
    plan, life, orphans, created_before = plan_run(root, tree, targets, authority)
    report_plan(plan, life, targets, orphans)
    if not plan.writes and not plan.removals:
        print("  every account already holds the same conversations, byte for byte.")
    if not args.apply:
        print("  report only — rerun with --apply to write.")
        return 0

    created, backups = mirror.apply_mirror(root, plan, created_before)
    manifest = write_manifest(root, created, backups)
    after = lifecycle.copies_by_session(flatten(scan(root)))
    # Recorded even when nothing was written: without it, the next deletion is invisible.
    lifecycle.save_baseline(root, after, life.deleted)
    wrong = mirror.misaligned(after, targets, life.deleted)
    overwrote = len(plan.writes) - len(created)
    print(f"\nCreated {len(created)}, overwrote {overwrote}, removed {len(plan.removals)}.")
    print(f"Originals kept in {BACKUP_DIR}/ and recorded in {manifest.name}; --undo puts them back.")
    if wrong:
        print(f"NOT ALIGNED: {len(wrong)} conversations still differ, e.g. {', '.join(wrong[:3])}")
        return 1
    print(f"Aligned: {len(after)} conversations identical across {len(targets)} account index(es).")
    print("Restart the desktop app — it reads this index at startup and does not rescan while running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
