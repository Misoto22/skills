#!/usr/bin/env python3
"""Align the desktop app's per-account conversation indexes onto one identical set.

Claude's desktop app keeps one conversation index per signed-in account under

    ~/Library/Application Support/Claude/claude-code-sessions/<account>/<org>/local_*.json

so signing in as a second account hides the first account's conversations from the
sidebar, and a rename, archive or deletion made under one account never reaches the
others. The transcripts themselves live in ~/.claude/projects/ (under CLAUDE_CONFIG_DIR
when that is set) keyed by working
directory and carry no account field at all, which is why `claude --resume` still
lists every one of them. Only the index is partitioned.

This makes every account hold the same conversations with byte-identical index files:
the copy the user touched last wins, an archive or deletion under one account reaches
all of them, and an entry whose transcript is gone is kept but archived. Every file it
creates and every original it overwrites or removes is recorded, so `--undo` puts the
tree back. Transcripts are never touched.

The desktop app reads the index at startup and does not rescan it while running, so a
run lands in the sidebar only after the app restarts.

`--sidebar-from` also copies one account's sidebar layout — its manual groups and their
members, section order and collapsed state — to every other account. That lives in the
app's Local Storage, which can only be written while the app is fully quit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import align
import environments_sync
import lifecycle as lifecycle
import local_storage
import sidebar_sync
from index_tree import CONFIG_DIR_ENV as CONFIG_DIR_ENV
from index_tree import SESSIONS_ROOT_ENV as SESSIONS_ROOT_ENV
from index_tree import Entry as Entry
from index_tree import flatten, scan, scopes_of, sessions_root, signed_in_account
from manifest import BACKUP_DIR
from manifest import MANIFEST_NAME as MANIFEST_NAME
from manifest import write_manifest as write_manifest
from report import report_plan, report_state
from undo import undo


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
    parser.add_argument(
        "--no-environments",
        dest="environments",
        action="store_false",
        help="leave the environments file alone; by default every account gets the same environments",
    )
    sidebar_sync.add_arguments(parser)
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


def main() -> int:
    args = parse_args()
    root = sessions_root()
    if args.undo:
        return undo(root)
    if args.undo_sidebar:
        return sidebar_sync.undo_latest(root)

    tree = scan(root)
    if len(tree) < 2:
        print(f"Only one account index under {root} — nothing to align.")
        return 0

    current = signed_in_account()
    report_state(root, tree, current)
    targets = resolve_targets(tree, args.into, current)
    if "all" in (args.authority, args.sidebar_from):
        sys.exit("--from and --sidebar-from name one account: 'current' or an accountUuid.")
    store = local_storage.store_dir() if args.sidebar_from else None
    if store:
        source = resolve_targets(tree, args.sidebar_from, current)[0]
        # Each account's scope is the org reunite lands its conversations in.
        scopes = scopes_of(tree)
        if args.apply:
            sidebar_sync.check(store, source, scopes)
    authority = resolve_targets(tree, args.authority, current)[0] if args.authority else None
    if authority:
        print(f"\nAuthority: {authority} — every other account becomes a copy of it.")
    plan, life, orphans, created_before = align.plan_run(root, tree, targets, authority)
    report_plan(plan, life, targets, orphans)
    if not plan.writes and not plan.removals:
        print("  every account already holds the same conversations, byte for byte.")
    everyone = args.into == "all"
    if not args.apply:
        if args.environments:
            environments_sync.run(root, targets, everyone, apply=False)
        if store:
            held = sidebar_sync.held_sessions(flatten(tree), plan)
            sidebar_sync.run(root, store, source, scopes, held, apply=False)
        print("  report only — rerun with --apply to write.")
        return 0

    applied = align.apply_plan(root, plan, life, targets, created_before)
    print(f"\nCreated {applied.created}, overwrote {applied.overwrote}, removed {applied.removed}.")
    print(f"Originals kept in {BACKUP_DIR}/ and recorded in {applied.manifest.name}; --undo puts them back.")
    wrong = applied.misaligned
    if wrong:
        print(f"NOT ALIGNED: {len(wrong)} conversations still differ, e.g. {', '.join(wrong[:3])}")
    else:
        across = f"across {len(targets)} account index(es)"
        print(f"Aligned: {applied.conversations} conversations identical {across}.")
        print("Restart the desktop app — it reads this index at startup and does not rescan while running.")
    env_status = environments_sync.run(root, targets, everyone, apply=True) if args.environments else 0
    status = 0
    if store:
        held = sidebar_sync.held_sessions(flatten(scan(root)))
        status = sidebar_sync.run(root, store, source, scopes, held, apply=True)
    return 1 if wrong else status or env_status


if __name__ == "__main__":
    sys.exit(main())
