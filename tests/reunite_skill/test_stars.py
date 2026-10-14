"""Starred environments travel with the sidebar layout: one Local Storage key per account."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import ldb_store
import local_storage
import stars

from tests.reunite_skill.test_ldb_files import FIXTURE
from tests.reunite_skill.test_merge import merge
from tests.reunite_skill.test_sidebar_sync import ORGS, A, B, C, snapshot


def envelope(*preset_ids: str, timestamp: int = 1_792_017_242_147) -> bytes:
    value = [f"{stars.PRESET_PREFIX}{pid}" for pid in preset_ids]
    return b"\x01" + json.dumps({"value": value, "tabId": "", "timestamp": timestamp}).encode("latin-1")


class StarPlanTests(unittest.TestCase):
    def test_the_key_is_per_account_under_the_apps_origin(self) -> None:
        self.assertEqual(
            stars.key(A), b"_https://claude.ai\x00\x01LSS-persisted.code-projects-order." + A.encode()
        )

    def test_starred_reads_the_preset_ids_in_order(self) -> None:
        self.assertEqual(stars.starred(envelope("p2", "p1")), ["p2", "p1"])
        self.assertIsNone(stars.starred(None))
        self.assertEqual(stars.starred(b"\x01not json"), [])

    def test_every_other_account_receives_the_source_bytes_or_loses_its_key(self) -> None:
        source = envelope("p1", "p2")
        operations, changes = stars.plan_stars({A: source, B: envelope("p9"), C: None}, A)

        self.assertEqual(operations, [(stars.key(B), source), (stars.key(C), source)])
        self.assertEqual([(c.account, c.before, c.after) for c in changes], [(B, 1, 2), (C, None, 2)])

        operations, _ = stars.plan_stars({A: None, B: envelope("p9"), C: None}, A)
        self.assertEqual(operations, [(stars.key(B), None)])

    def test_accounts_already_holding_the_source_bytes_are_left_alone(self) -> None:
        same = envelope("p1")
        self.assertEqual(stars.plan_stars({A: same, B: same}, A), ([], []))


class StarRunTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "sessions"
        self.store = self.home / "Local Storage" / "leveldb"
        shutil.copytree(FIXTURE, self.store)
        projects = self.home / ".claude" / "projects" / "proj"
        projects.mkdir(parents=True)
        for account in (A, B, C):
            org = self.root / account / ORGS[account]
            org.mkdir(parents=True)
            (projects / "s1.jsonl").write_text("{}")
            entry = {"sessionId": "local_s1", "cliSessionId": "s1", "title": "s1", "lastActivityAt": 1}
            (org / "local_s1.json").write_text(json.dumps(entry))
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

    def run_merge(self, *flags: str, code: int = 0) -> str:
        out = io.StringIO()
        with patch.object(sys, "argv", ["merge.py", *flags]), contextlib.redirect_stdout(out):
            self.assertEqual(merge.main(), code, out.getvalue())
        return out.getvalue()

    def star(self, account: str, value: bytes | None) -> None:
        ldb_store.put_many(self.store, [(stars.key(account), value)])

    def test_report_only_counts_the_stars_and_writes_nothing(self) -> None:
        self.star(A, envelope("p1", "p2"))
        before = snapshot(self.store)

        report = self.run_merge(f"--sidebar-from={A}")

        self.assertIn(f"starred environments from {A}: 2", report)
        self.assertIn(f"  {B}  (none)  → 2 starred", report)
        self.assertEqual(snapshot(self.store), before)

    def test_apply_copies_the_source_stars_to_every_account_in_one_batch(self) -> None:
        source = envelope("p1", "p2")
        self.star(A, source)
        self.star(B, envelope("p9"))

        report = self.run_merge(f"--sidebar-from={A}", "--apply")

        self.assertIn("Starred environments copied to 2 account(s)", report)
        for account in (B, C):
            self.assertEqual(ldb_store.read(self.store, stars.key(account)), source, account)
        self.assertTrue(list((self.root / merge.BACKUP_DIR).glob("local-storage-*")))

    def test_a_source_without_stars_clears_them_elsewhere(self) -> None:
        self.star(B, envelope("p9"))

        self.run_merge(f"--sidebar-from={A}", "--apply")

        self.assertIsNone(ldb_store.read(self.store, stars.key(B)))

    def test_a_second_apply_writes_nothing(self) -> None:
        self.star(A, envelope("p1"))
        self.run_merge(f"--sidebar-from={A}", "--apply")
        written = snapshot(self.store)

        report = self.run_merge(f"--sidebar-from={A}", "--apply")

        self.assertIn("already has this layout", report)
        self.assertEqual(snapshot(self.store), written)

    def test_stars_that_read_back_wrong_are_rolled_back(self) -> None:
        self.star(A, envelope("p1"))
        before = snapshot(self.store)
        real = ldb_store.put_many

        def dropping_stars(store: Path, operations):
            return real(store, [op for op in operations if op[0] == stars.key(A) or b"dframe" in op[0]])

        with patch.object(ldb_store, "put_many", dropping_stars):
            report = self.run_merge(f"--sidebar-from={A}", "--apply", code=1)

        self.assertIn("SIDEBAR NOT WRITTEN", report)
        self.assertEqual(snapshot(self.store), before)


if __name__ == "__main__":
    unittest.main()
