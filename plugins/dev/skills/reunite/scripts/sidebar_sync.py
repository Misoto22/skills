"""The ``--sidebar-from`` step: copy one account's sidebar layout to every other account.

Reunite makes every account's conversation index identical; what still differs per
account is the sidebar layout — manual groups and their members, section order,
collapsed state — which the app keeps in Local Storage rather than beside the index.
This reads that value, plans the copy, and with ``--apply`` writes it back as one
LevelDB put after backing the whole database up, then reads it back and restores the
backup if what landed is not exactly what was written. Only the ``dframe-store`` key is
written, and inside it only the per-scope layout maps of the receiving scopes.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import ldb_store
import local_storage
import sidebar
from ldb_codec import LevelDBError
from manifest import BACKUP_DIR, drop_local_storage, local_storage_records, write_manifest


def held_sessions(entries: Iterable[object], plan: object | None = None) -> dict[str, set[str]]:
    """Session ids each account's index holds — after ``plan`` when one is still to be applied."""
    held: dict[str, set[str]] = defaultdict(set)
    by_path = {}
    for entry in entries:
        held[entry.path.parts[-3]].add(entry.session_id)
        by_path[entry.path] = entry.session_id
    if plan is not None:
        for path in plan.removals:
            held[path.parts[-3]].discard(by_path.get(path))
        for write in plan.writes:
            if write.created:
                held[write.dest.parts[-3]].add(json.loads(write.content).get("sessionId"))
    return dict(held)


def _load(store: Path) -> tuple[bytes, dict]:
    raw = ldb_store.read(store, sidebar.STORE_KEY)
    if raw is None:
        sys.exit(f"No sidebar layout stored in {store} yet — open the app's Code tab once first.")
    return raw, sidebar.decode(raw)


def _plan(store: Path, source: str, scopes: dict[str, str], held: dict[str, set[str]]):
    try:
        raw, document = _load(store)
        scope = sidebar.source_scope(document["state"], source, scopes.get(source, ""))
        updated, changes = sidebar.plan_layout(document, scope, source, scopes, held)
    except (LevelDBError, sidebar.SidebarError) as error:
        sys.exit(f"Cannot read the sidebar layout in {store}: {error}")
    return raw, document, scope, updated, changes


def report(store: Path, document: dict, scope: str, changes: list[sidebar.ScopeChange]) -> None:
    """Print each scope's manual-group count and what the copy would change."""
    entry = document["state"][sidebar.SECTIONS_BY_SCOPE][scope]
    sections, manual = len(sidebar.sections_of(entry)), sidebar.manual_count(entry)
    print(f"\nSidebar layout {store}")
    print(f"  from {scope}  {sections} sections, {manual} manual groups")
    for change in changes:
        before = "(no layout yet)" if change.created else f"{change.manual_before} manual groups"
        if not change.changed:
            print(f"  {change.scope}  {before}  already identical")
            continue
        dropped = f", {change.dropped} members not in its index dropped" if change.dropped else ""
        after = f"{change.sections_after} sections, {change.manual_after} manual groups"
        print(f"  {change.scope}  {before}  → {after}{dropped}")


def run(root: Path, store: Path, source: str, scopes: dict[str, str], held, apply: bool) -> int:
    """Report the copy, and with ``apply`` write it. Returns the exit status."""
    if not apply:
        _, document, scope, _, changes = _plan(store, source, scopes, held)
        report(store, document, scope, changes)
        if local_storage.app_running():
            print(f"  Claude is running — --apply will refuse until it is quit. {local_storage.QUIT_FIRST}")
        return 0
    with local_storage.exclusive(store):
        raw, document, scope, updated, changes = _plan(store, source, scopes, held)
        report(store, document, scope, changes)
        if not any(change.changed for change in changes):
            print("  every scope already has this layout; nothing written.")
            return 0
        return _write(root, store, raw, updated, sum(c.changed for c in changes))


def _write(root: Path, store: Path, raw: bytes, updated: dict, count: int) -> int:
    saved = local_storage.backup(store, root / BACKUP_DIR)
    write_manifest(root, [], [], {"backup": saved.name, "store": str(store.resolve())})
    value = sidebar.encode(updated)
    try:
        sequence = ldb_store.put(store, sidebar.STORE_KEY, value)
        landed = ldb_store.read(store, sidebar.STORE_KEY)
    except (LevelDBError, OSError) as error:
        landed, sequence = None, None
        print(f"  write failed: {error}", file=sys.stderr)
    if landed != value:
        local_storage.restore(saved, store)
        print(f"SIDEBAR NOT WRITTEN: the value read back differs; {store} restored from {saved.name}.")
        return 1
    print(f"\nSidebar layout written to {count} scope(s) at sequence {sequence}.")
    print(f"Local Storage kept in {BACKUP_DIR}/{saved.name} and recorded for --undo.")
    print("Open Claude again — it loads the layout at startup.")
    return 0


def check(store: Path, source: str, scopes: dict[str, str]) -> None:
    """Exit now, before any index is written, if the layout could not be copied later."""
    _plan(store, source, scopes, {})
    with local_storage.exclusive(store):
        pass


def add_arguments(parser) -> None:
    """The command-line flags this step owns."""
    parser.add_argument(
        "--sidebar-from",
        dest="sidebar_from",
        help="copy this account's sidebar layout to every other account: 'current' or an accountUuid",
    )
    parser.add_argument(
        "--undo-sidebar",
        action="store_true",
        help="restore only the sidebar layout, from the most recent backup; the index stays as it is",
    )


def undo(root: Path, records: list[dict[str, str]]) -> bool:
    """Put back the Local Storage copied before the first recorded sidebar write.

    Returns whether it was restored; exits while the app holds the database.
    """
    return _restore(root, records[0])


def undo_latest(root: Path) -> int:
    """Revert only the latest sidebar write: restore its backup and forget its record."""
    records = local_storage_records(root)
    if not records:
        print(f"Nothing to undo — no sidebar layout backup recorded under {root}")
        return 0
    if not _restore(root, records[-1]):
        return 1
    drop_local_storage(root, records[-1])
    print("Conversation indexes are unchanged. Open Claude again to see the restored layout.")
    return 0


def _restore(root: Path, record: dict[str, str]) -> bool:
    store = local_storage.store_dir()
    if Path(record["store"]).resolve() != store.resolve():
        sys.exit(
            f"The sidebar backup was taken from {record['store']}, but {local_storage.STORE_ENV} "
            f"now names {store}. Point it back and rerun."
        )
    saved = root / BACKUP_DIR / record["backup"]
    if not (saved / "CURRENT").is_file():
        print(f"  Local Storage backup {saved.name} is missing; the sidebar layout was not restored.")
        return False
    with local_storage.exclusive(store):
        kept = local_storage.restore(saved, store, root / local_storage.REPLACED_DIR)
    print(f"Restored Local Storage from {saved.name}; the replaced copy is in {kept}.")
    return True
