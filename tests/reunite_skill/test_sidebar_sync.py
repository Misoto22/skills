"""--sidebar-from end to end through merge.main(), against a copy of a real LevelDB database."""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import ldb_log
import ldb_store
import ldb_table
import local_storage
import mirror
import sidebar
import sidebar_sync

from tests.reunite_skill.test_ldb_files import FIXTURE, ORIGIN
from tests.reunite_skill.test_merge import merge

A = "aaaaaaaa-0000-4000-8000-00000000000a"
B = "bbbbbbbb-0000-4000-8000-00000000000b"
C = "cccccccc-0000-4000-8000-00000000000c"
ORGS = {A: "0a0a0a0a-0000-4000-8000-0000000000a0", B: "0b0b0b0b-0000-4000-8000-0000000000b0"}
ORGS[C] = "0c0c0c0c-0000-4000-8000-0000000000c0"
SCOPES = {account: f"{account}/{org}" for account, org in ORGS.items()}
HOLD_LOCK = (
    "import fcntl, sys, time\n"
    "handle = open(sys.argv[1], 'a')\n"
    "fcntl.lockf(handle, fcntl.LOCK_EX)\n"
    "print('locked', flush=True)\n"
    "time.sleep(60)\n"
)


def every_key(store: Path) -> set[bytes]:
    """Every user key in the database's live tables and logs."""
    version = ldb_store.read_version(store)
    keys = {
        key for n in version.tables for key, *_ in ldb_table.table_entries(ldb_store.table_path(store, n))
    }
    for log in ldb_store.live_logs(store, version):
        for record in ldb_log.read_records(log.read_bytes()).records:
            keys.update(key for _, _, key, _ in ldb_log.decode_batch(record))
    return keys


def snapshot(directory: Path) -> dict[str, bytes]:
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


class HeldSessionsTests(unittest.TestCase):
    def test_a_pending_plan_adds_created_copies_and_drops_removed_ones(self) -> None:
        root = Path("/index")
        entries = [
            merge.Entry(root / A / "org" / "local_s1.json", "local_s1", "s1", 1, 1.0),
            merge.Entry(root / A / "org" / "local_s2.json", "local_s2", "s2", 1, 1.0),
            merge.Entry(root / B / "org" / "local_s2.json", "local_s2", "s2", 1, 1.0),
        ]
        created = mirror.Write(root / B / "org" / "local_s1.json", b'{"sessionId":"local_s1"}', 1.0, True, ())
        plan = mirror.MirrorPlan([created], [root / A / "org" / "local_s2.json"])

        self.assertEqual(sidebar_sync.held_sessions(entries), {A: {"local_s1", "local_s2"}, B: {"local_s2"}})
        self.assertEqual(
            sidebar_sync.held_sessions(entries, plan), {A: {"local_s1"}, B: {"local_s1", "local_s2"}}
        )


class AppRunningTests(unittest.TestCase):
    def test_pgrep_includes_its_own_ancestors(self) -> None:
        # Run from the app's own terminal, the app is an ancestor that plain macOS pgrep skips.
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(local_storage.app_running())
        self.assertEqual(run.call_args.args[0], ["pgrep", "-a", "-x", "Claude"])
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertFalse(local_storage.app_running())

    def test_a_platform_without_pgrep_relies_on_the_lock(self) -> None:
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(local_storage.app_running())


class SidebarRunTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "sessions"
        self.store = self.home / "Local Storage" / "leveldb"
        shutil.copytree(FIXTURE, self.store)
        projects = self.home / ".claude" / "projects" / "proj"
        projects.mkdir(parents=True)
        for account, sids in ((A, ("s1", "s2", "s3")), (B, ("s4",)), (C, ())):
            org = self.root / account / ORGS[account]
            org.mkdir(parents=True)
            for sid in sids:
                (projects / f"{sid}.jsonl").write_text("{}")
                entry = {"sessionId": f"local_{sid}", "cliSessionId": sid, "title": sid, "lastActivityAt": 1}
                (org / f"local_{sid}.json").write_text(json.dumps(entry))
        env = {
            "HOME": str(self.home),
            merge.SESSIONS_ROOT_ENV: str(self.root),
            local_storage.STORE_ENV: str(self.store),
        }
        for patcher in (
            patch.dict(os.environ, env),
            patch.object(local_storage, "app_running", return_value=False),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop(merge.CONFIG_DIR_ENV, None)
        self.original = snapshot(self.store)

    def run_merge(self, *flags: str, code: int = 0) -> str:
        out = io.StringIO()
        with patch.object(sys, "argv", ["merge.py", *flags]), contextlib.redirect_stdout(out):
            self.assertEqual(merge.main(), code, out.getvalue())
        return out.getvalue()

    def refused(self, *flags: str) -> str:
        with (
            patch.object(sys, "argv", ["merge.py", *flags]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            merge.main()
        return str(raised.exception.code)

    def layout(self) -> dict:
        return sidebar.decode(ldb_store.read(self.store, sidebar.STORE_KEY))["state"]

    def assert_untouched(self) -> None:
        self.assertEqual(snapshot(self.store), self.original)
        self.assertFalse((self.root / B / ORGS[B] / "local_s1.json").exists())
        self.assertFalse((self.root / merge.BACKUP_DIR).exists())

    def test_refuses_while_another_process_holds_the_lock(self) -> None:
        holder = subprocess.Popen(
            [sys.executable, "-c", HOLD_LOCK, str(self.store / "LOCK")], stdout=subprocess.PIPE, text=True
        )
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        holder.stdout.close()

        message = self.refused(f"--sidebar-from={A}", "--apply")

        self.assertIn("Quit Claude completely", message)
        self.assert_untouched()

    def test_refuses_while_the_lock_is_held_with_flock(self) -> None:
        with (self.store / "LOCK").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self.assertIn("Quit Claude completely", self.refused(f"--sidebar-from={A}", "--apply"))
        self.assert_untouched()

    def test_refuses_while_the_app_is_running(self) -> None:
        with patch.object(local_storage, "app_running", return_value=True):
            self.assertIn("Claude is running", self.refused(f"--sidebar-from={A}", "--apply"))
        self.assert_untouched()

    def test_report_only_writes_nothing_and_counts_against_the_aligned_index(self) -> None:
        report = self.run_merge(f"--sidebar-from={A}")

        self.assertIn(f"from {SCOPES[A]}  5 sections, 2 manual groups", report)
        # B holds only s4 now, but alignment gives it s1 to s3, so only the gone member drops.
        self.assertIn(f"{SCOPES[B]}  0 manual groups  → 5 sections, 2 manual groups, 1 members", report)
        self.assertIn(f"{SCOPES[C]}  (no layout yet)  →", report)
        self.assertIn("report only", report)
        self.assert_untouched()

    def test_apply_copies_the_layout_to_every_scope_and_touches_nothing_else(self) -> None:
        keys = every_key(self.store)
        before = {key: ldb_store.read(self.store, key) for key in keys}
        state_before = self.layout()

        report = self.run_merge(f"--sidebar-from={A}", "--apply")

        self.assertIn("Sidebar layout written to 2 scope(s)", report)
        state = self.layout()
        source = state[sidebar.SECTIONS_BY_SCOPE][SCOPES[A]]
        for account in (B, C):
            copied = state[sidebar.SECTIONS_BY_SCOPE][SCOPES[account]]
            self.assertEqual(sidebar.manual_count(copied), 2)
            alpha = next(s for s in copied["sections"] if s.get("name") == "Alpha")
            self.assertEqual(alpha["members"], ["code:local_s1", "code:local_s2"])
            self.assertEqual(copied["sections"][3], source["sections"][3])
            groups = state[sidebar.GROUPS_BY_SCOPE][SCOPES[account]]
            self.assertEqual(groups, state[sidebar.GROUPS_BY_SCOPE][SCOPES[A]])
        self.assertEqual(source, state_before[sidebar.SECTIONS_BY_SCOPE][SCOPES[A]])
        for name in set(state_before) - {sidebar.SECTIONS_BY_SCOPE, sidebar.GROUPS_BY_SCOPE}:
            self.assertEqual(state[name], state_before[name], name)
        self.assertEqual(every_key(self.store), keys)
        for key in keys - {sidebar.STORE_KEY}:
            self.assertEqual(ldb_store.read(self.store, key), before[key], key)
        self.assertEqual((self.store / "000005.ldb").read_bytes(), self.original["000005.ldb"])
        backups = list((self.root / merge.BACKUP_DIR).glob("local-storage-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(snapshot(backups[0]), self.original)
        recorded = json.loads((self.root / merge.MANIFEST_NAME).read_text())["localStorage"]
        self.assertEqual(recorded, [{"backup": backups[0].name, "store": str(self.store.resolve())}])

    def test_a_second_apply_writes_nothing(self) -> None:
        self.run_merge(f"--sidebar-from={A}", "--apply")
        written = snapshot(self.store)

        report = self.run_merge(f"--sidebar-from={A}", "--apply")

        self.assertIn("already has this layout", report)
        self.assertEqual(snapshot(self.store), written)
        self.assertEqual(len(list((self.root / merge.BACKUP_DIR).glob("local-storage-*"))), 1)

    def test_a_value_that_reads_back_wrong_is_rolled_back(self) -> None:
        real_put = ldb_store.put

        def corrupting_put(store: Path, key: bytes, value: bytes) -> int:
            return real_put(store, key, value + b" ")

        with patch.object(ldb_store, "put", corrupting_put):
            report = self.run_merge(f"--sidebar-from={A}", "--apply", code=1)

        self.assertIn("SIDEBAR NOT WRITTEN", report)
        self.assertEqual(snapshot(self.store), self.original)

    def test_a_write_that_fails_part_way_is_rolled_back(self) -> None:
        real_put = ldb_store.put

        def failing_put(store: Path, key: bytes, value: bytes) -> int:
            real_put(store, key, value)
            raise ldb_store.LevelDBError("disk went away")

        errors = io.StringIO()
        with patch.object(ldb_store, "put", failing_put), contextlib.redirect_stderr(errors):
            report = self.run_merge(f"--sidebar-from={A}", "--apply", code=1)

        self.assertIn("disk went away", errors.getvalue())
        self.assertIn("SIDEBAR NOT WRITTEN", report)
        self.assertEqual(snapshot(self.store), self.original)

    def test_undo_restores_the_directory_and_keeps_the_replaced_copy(self) -> None:
        self.run_merge(f"--sidebar-from={A}", "--apply")
        written = snapshot(self.store)

        report = self.run_merge("--undo")

        self.assertIn("Restored Local Storage", report)
        self.assertEqual(snapshot(self.store), self.original)
        kept = list((self.root / local_storage.REPLACED_DIR).glob("local-storage-*"))
        self.assertEqual([snapshot(path) for path in kept], [written])
        self.assertFalse((self.root / B / ORGS[B] / "local_s1.json").exists())
        self.assertFalse((self.root / merge.MANIFEST_NAME).exists())

    def test_undo_refuses_while_the_app_is_running(self) -> None:
        self.run_merge(f"--sidebar-from={A}", "--apply")
        written = snapshot(self.store)

        with patch.object(local_storage, "app_running", return_value=True):
            self.assertIn("Claude is running", self.refused("--undo"))

        self.assertEqual(snapshot(self.store), written)
        self.assertTrue((self.root / merge.MANIFEST_NAME).exists())
        self.assertTrue((self.root / B / ORGS[B] / "local_s1.json").exists())

    def test_undo_refuses_a_backup_taken_from_another_store(self) -> None:
        self.run_merge(f"--sidebar-from={A}", "--apply")
        other = self.home / "elsewhere"
        shutil.copytree(FIXTURE, other)

        with patch.dict(os.environ, {local_storage.STORE_ENV: str(other)}):
            self.assertIn("Point it back", self.refused("--undo"))

    def test_undo_without_its_backup_still_undoes_the_index(self) -> None:
        self.run_merge(f"--sidebar-from={A}", "--apply")
        for backup in (self.root / merge.BACKUP_DIR).glob("local-storage-*"):
            shutil.rmtree(backup)

        report = self.run_merge("--undo")

        self.assertIn("was not restored", report)
        self.assertFalse((self.root / B / ORGS[B] / "local_s1.json").exists())

    def test_bad_sources_and_stores_are_refused(self) -> None:
        self.assertIn("name one account", self.refused("--sidebar-from=all"))
        self.assertIn("No index directory", self.refused("--sidebar-from=nobody"))
        with patch.dict(os.environ, {local_storage.STORE_ENV: str(self.home / "missing")}):
            self.assertIn("No Local Storage database", self.refused(f"--sidebar-from={A}"))
        self.assertIn("cannot tell which sidebar scope", self.refused(f"--sidebar-from={C}"))
        # With --apply these must stop before the index is aligned, not after.
        self.assertIn("No index directory", self.refused("--sidebar-from=nobody", "--apply"))
        self.assertIn("cannot tell which sidebar scope", self.refused(f"--sidebar-from={C}", "--apply"))
        self.assert_untouched()

    def test_a_damaged_store_is_refused_before_any_write(self) -> None:
        table = self.store / "000005.ldb"
        table.write_bytes(table.read_bytes()[:-1] + b"\x00")
        self.assertIn("Cannot read the sidebar layout", self.refused(f"--sidebar-from={A}"))

    def test_a_store_without_the_layout_key_is_refused(self) -> None:
        with patch.object(sidebar, "STORE_KEY", ORIGIN + b"never-written"):
            self.assertIn("No sidebar layout stored", self.refused(f"--sidebar-from={A}"))


if __name__ == "__main__":
    unittest.main()
