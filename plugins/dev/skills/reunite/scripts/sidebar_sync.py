"""The ``--sidebar-from`` step: copy one account's sidebar layout and stars to every other account.

Reunite makes every account's conversation index identical; what still differs per
account is the sidebar layout — manual groups and their members, section order,
collapsed state — and which environments are starred, both of which the app keeps in
Local Storage rather than beside the index. This reads those values, plans the copy,
and with ``--apply`` writes it back as one LevelDB batch after backing the whole
database up, then reads every written key back and restores the backup if what landed
is not exactly what was written. Only ``dframe-store`` — inside it only the per-scope
layout maps of the receiving scopes — and the receiving accounts' star keys are written.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import ldb_store
import local_storage
import sidebar
import stars
from ldb_codec import LevelDBError
from manifest import BACKUP_DIR, drop_local_storage, local_storage_records, write_manifest


class NoLayout(sidebar.SidebarError):
    """The store holds no sidebar layout yet."""


@dataclass(frozen=True)
class SidebarPlan:
    """The stored layout, the copy planned from it, and the star keys to write."""

    raw: bytes
    document: dict
    scope: str
    updated: dict
    changes: list[sidebar.ScopeChange]
    source_stars: int | None
    star_writes: list[tuple[bytes, bytes | None]]
    star_changes: list[stars.StarChange]

    @property
    def changed(self) -> bool:
        return any(c.changed for c in self.changes) or bool(self.star_writes)


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


def plan_copy(store: Path, source: str, scopes: dict[str, str], held: dict[str, set[str]]) -> SidebarPlan:
    """Plan giving every account in ``scopes`` the source account's layout and stars.

    Raises LevelDBError or SidebarError when the store cannot be read as expected.
    """
    accounts = sorted(scopes)
    values = ldb_store.read_many(store, [sidebar.STORE_KEY, *(stars.key(a) for a in accounts)])
    raw = values[sidebar.STORE_KEY]
    if raw is None:
        raise NoLayout("no sidebar layout stored yet")
    document = sidebar.decode(raw)
    scope = sidebar.source_scope(document["state"], source, scopes.get(source, ""))
    updated, changes = sidebar.plan_layout(document, scope, source, scopes, held)
    starred = {a: values[stars.key(a)] for a in accounts}
    writes, star_changes = stars.plan_stars(starred, source)
    count = stars.starred(starred.get(source))
    return SidebarPlan(
        raw, document, scope, updated, changes, None if count is None else len(count), writes, star_changes
    )


def _plan(store: Path, source: str, scopes: dict[str, str], held: dict[str, set[str]]) -> SidebarPlan:
    try:
        return plan_copy(store, source, scopes, held)
    except NoLayout:
        sys.exit(f"No sidebar layout stored in {store} yet — open the app's Code tab once first.")
    except (LevelDBError, sidebar.SidebarError) as error:
        sys.exit(f"Cannot read the sidebar layout in {store}: {error}")


def report(store: Path, plan: SidebarPlan, source: str) -> None:
    """Print each scope's manual-group count, each account's stars, and what the copy would change."""
    entry = plan.document["state"][sidebar.SECTIONS_BY_SCOPE][plan.scope]
    sections, manual = len(sidebar.sections_of(entry)), sidebar.manual_count(entry)
    print(f"\nSidebar layout {store}")
    print(f"  from {plan.scope}  {sections} sections, {manual} manual groups")
    for change in plan.changes:
        before = "(no layout yet)" if change.created else f"{change.manual_before} manual groups"
        if not change.changed:
            print(f"  {change.scope}  {before}  already identical")
            continue
        dropped = f", {change.dropped} members not in its index dropped" if change.dropped else ""
        after = f"{change.sections_after} sections, {change.manual_after} manual groups"
        print(f"  {change.scope}  {before}  → {after}{dropped}")
    print(f"  starred environments from {source}: {plan.source_stars or 0}")
    for star in plan.star_changes:
        before = "(none)" if star.before is None else f"{star.before} starred"
        print(f"  {star.account}  {before}  → {star.after or 0} starred")


def run(root: Path, store: Path, source: str, scopes: dict[str, str], held, apply: bool) -> int:
    """Report the copy, and with ``apply`` write it. Returns the exit status."""
    if not apply:
        report(store, _plan(store, source, scopes, held), source)
        if local_storage.app_running():
            print(f"  Claude is running — --apply will refuse until it is quit. {local_storage.QUIT_FIRST}")
        return 0
    with local_storage.exclusive(store):
        plan = _plan(store, source, scopes, held)
        report(store, plan, source)
        if not plan.changed:
            print("  every scope already has this layout; nothing written.")
            return 0
        return write(root, store, plan)


def write(root: Path, store: Path, plan: SidebarPlan) -> int:
    """Back the store up, write the plan as one batch, and roll back unless every key reads back.

    The caller holds the store exclusively. Returns the exit status.
    """
    saved = local_storage.backup(store, root / BACKUP_DIR)
    write_manifest(root, [], [], {"backup": saved.name, "store": str(store.resolve())})
    layout = sum(c.changed for c in plan.changes)
    operations = [(sidebar.STORE_KEY, sidebar.encode(plan.updated))] if layout else []
    operations += plan.star_writes
    try:
        sequence = ldb_store.put_many(store, operations)
        landed = ldb_store.read_many(store, [key for key, _ in operations])
    except (LevelDBError, OSError) as error:
        landed, sequence = {}, None
        print(f"  write failed: {error}", file=sys.stderr)
    if any(landed.get(key, b"") != value for key, value in operations):
        local_storage.restore(saved, store)
        print(f"SIDEBAR NOT WRITTEN: a value read back differs; {store} restored from {saved.name}.")
        return 1
    print(f"\nSidebar layout written to {layout} scope(s) at sequence {sequence}.")
    if plan.star_writes:
        print(f"Starred environments copied to {len(plan.star_writes)} account(s).")
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
