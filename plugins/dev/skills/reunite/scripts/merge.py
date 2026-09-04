#!/usr/bin/env python3
"""Union the desktop app's per-account conversation indexes.

Claude's desktop app keeps one conversation index per signed-in account under

    ~/Library/Application Support/Claude/claude-code-sessions/<account>/<org>/local_*.json

so signing in as a second account hides the first account's conversations from the
sidebar. It never deletes them: the transcripts live in ~/.claude/projects/ keyed by
working directory and carry no account field at all, which is why `claude --resume`
still lists every one of them. Only the index is partitioned.

This copies each account's index entries into every other account's index. It adds
files and never removes one, records what it wrote so `--undo` can take it back, and
leaves every transcript untouched.

The desktop app reads the index at startup and does not rescan it while running, so a
merge lands in the sidebar only after the app restarts.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

SESSIONS_ROOT_ENV = "CLAUDE_DESKTOP_SESSIONS_DIR"
DEFAULT_ROOT = "~/Library/Application Support/Claude/claude-code-sessions"
MANIFEST_NAME = ".session-merge-manifest.json"


@dataclass(frozen=True)
class Entry:
    """One `local_*.json` index file — the sidebar's record of a conversation."""

    path: Path
    session_id: str
    cli_session_id: str | None
    title: str
    last_activity: int


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
        title=data.get("title") or "(untitled)",
        last_activity=data.get("lastActivityAt") or 0,
    )


def scan(root: Path) -> dict[str, dict[str, list[Entry]]]:
    """Map account -> org -> entries, skipping anything that is not an index file."""
    tree: dict[str, dict[str, list[Entry]]] = {}
    for account in sorted(p for p in root.iterdir() if p.is_dir()):
        orgs: dict[str, list[Entry]] = {}
        for org in sorted(p for p in account.iterdir() if p.is_dir()):
            entries = [e for e in (read_entry(f) for f in org.glob("local_*.json")) if e]
            orgs[org.name] = entries
        if orgs:
            tree[account.name] = orgs
    return tree


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
    """The accountUuid Claude Code currently holds, or None if it cannot be read."""
    try:
        data = json.loads(Path("~/.claude.json").expanduser().read_text())
    except (OSError, ValueError):
        return None
    return (data.get("oauthAccount") or {}).get("accountUuid")


def plan_copies(
    root: Path,
    tree: dict[str, dict[str, list[Entry]]],
    targets: list[str],
    keep_orphans: bool,
) -> tuple[list[tuple[Path, Path]], int, int]:
    """Pair every entry missing from a target account with where it should land.

    Returns the copies, the bytes they add, and how many were skipped as orphans —
    index entries whose transcript is gone, which would open an empty conversation.
    """
    live = transcript_ids()
    copies: list[tuple[Path, Path]] = []
    added = orphans = 0
    for target in targets:
        orgs = tree[target]
        dest_org = landing_org(orgs)
        if dest_org is None:
            continue
        dest = root / target / dest_org
        held = {e.session_id for entries in orgs.values() for e in entries}
        for source, source_orgs in tree.items():
            if source == target:
                continue
            for entry in (e for entries in source_orgs.values() for e in entries):
                if entry.session_id in held:
                    continue
                if not keep_orphans and entry.cli_session_id not in live:
                    orphans += 1
                    continue
                held.add(entry.session_id)
                copies.append((entry.path, dest / entry.path.name))
                added += entry.path.stat().st_size
    return copies, added, orphans


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


def apply_copies(root: Path, copies: list[tuple[Path, Path]]) -> Path:
    """Copy each planned file and record it, so --undo can remove exactly these."""
    written: list[str] = []
    for source, dest in copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        written.append(str(dest))
    manifest = root / MANIFEST_NAME
    previous = read_manifest(manifest)
    manifest.write_text(json.dumps(sorted(set(previous) | set(written)), indent=2))
    return manifest


def read_manifest(manifest: Path) -> list[str]:
    """Paths a previous --apply wrote, or an empty list when there was none."""
    try:
        data = json.loads(manifest.read_text())
    except (OSError, ValueError):
        return []
    return [p for p in data if isinstance(p, str)] if isinstance(data, list) else []


def undo(root: Path) -> int:
    """Remove only the files a previous --apply wrote, then drop the manifest."""
    manifest = root / MANIFEST_NAME
    paths = read_manifest(manifest)
    if not paths:
        print(f"Nothing to undo — no {MANIFEST_NAME} under {root}")
        return 0
    removed = 0
    for path in paths:
        try:
            Path(path).unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as error:
            print(f"  could not remove {path}: {error}", file=sys.stderr)
    manifest.unlink(missing_ok=True)
    print(f"Removed {removed} of {len(paths)} merged entries. Restart the desktop app.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the copies (default: report only)")
    parser.add_argument("--undo", action="store_true", help="remove what a previous --apply wrote")
    parser.add_argument(
        "--into",
        default="all",
        help="which account indexes receive the union: 'all' (default), 'current', or an accountUuid",
    )
    parser.add_argument(
        "--keep-orphans",
        action="store_true",
        help="also copy entries whose transcript is gone; they open to an empty conversation",
    )
    return parser.parse_args()


def resolve_targets(tree: dict[str, dict[str, list[Entry]]], into: str, current: str | None) -> list[str]:
    """Turn --into into the account directories that will be written."""
    if into == "all":
        return list(tree)
    if into == "current":
        if current is None:
            sys.exit("Cannot read the signed-in account from ~/.claude.json — pass --into=<accountUuid>.")
        if current not in tree:
            sys.exit(f"Signed-in account {current} has no index directory yet — open one conversation first.")
        return [current]
    if into not in tree:
        sys.exit(f"No index directory for account {into}. Known: {', '.join(tree)}")
    return [into]


def main() -> int:
    args = parse_args()
    root = sessions_root()
    if args.undo:
        return undo(root)

    tree = scan(root)
    if len(tree) < 2:
        print(f"Only one account index under {root} — nothing to union.")
        return 0

    current = signed_in_account()
    report_state(root, tree, current)

    targets = resolve_targets(tree, args.into, current)
    copies, added, orphans = plan_copies(root, tree, targets, args.keep_orphans)

    print(f"\nPlan: {len(copies)} entries to copy into {len(targets)} account index(es), +{human(added)}")
    if orphans:
        print(f"  skipped {orphans} whose transcript is gone (--keep-orphans copies them anyway)")
    if not copies:
        print("  every account already sees every conversation.")
        return 0
    if not args.apply:
        print("  report only — rerun with --apply to write.")
        return 0

    manifest = apply_copies(root, copies)
    print(f"\nCopied {len(copies)} entries. Recorded in {manifest.name}; --undo removes exactly these.")
    print("Restart the desktop app — it reads this index at startup and does not rescan while running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
