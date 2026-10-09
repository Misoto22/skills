"""Every account must end up holding the same conversations as byte-identical files."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.reunite_skill.test_merge import merge

lifecycle = sys.modules["lifecycle"]
manifest = sys.modules["manifest"]

A = "account-a"
B = "account-b"
C = "account-c"
ORG = "org"


class AlignRunTests(unittest.TestCase):
    """Drive merge.main() against a temporary home holding several account indexes."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "sessions"
        for account in (A, B):
            (self.root / account / ORG).mkdir(parents=True)
        (self.home / ".claude" / "projects" / "proj").mkdir(parents=True)
        env = patch.dict(os.environ, {"HOME": str(self.home), merge.SESSIONS_ROOT_ENV: str(self.root)})
        env.start()
        self.addCleanup(env.stop)

    def path(self, account: str, sid: str) -> Path:
        return self.root / account / ORG / f"local_{sid}.json"

    def session(
        self, account: str, sid: str, mtime: float = 1_000.0, transcript: bool = True, **fields
    ) -> Path:
        if transcript:
            (self.home / ".claude" / "projects" / "proj" / f"cli-{sid}.jsonl").write_text("{}")
        path = self.path(account, sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"sessionId": sid, "cliSessionId": f"cli-{sid}", "title": sid, "lastActivityAt": 1, **fields}
        path.write_text(json.dumps(data))
        os.utime(path, (mtime, mtime))
        return path

    def edit(self, account: str, sid: str, mtime: float, **fields) -> None:
        path = self.path(account, sid)
        data = {**json.loads(path.read_text()), **fields}
        path.write_text(json.dumps(data))
        os.utime(path, (mtime, mtime))

    def field(self, account: str, sid: str, name: str):
        path = self.path(account, sid)
        return json.loads(path.read_text()).get(name) if path.exists() else "MISSING"

    def assert_identical(self, sid: str, accounts=(A, B)) -> None:
        contents = {self.path(a, sid).read_bytes() for a in accounts}
        self.assertEqual(len(contents), 1, f"{sid} differs across {accounts}")

    def run_merge(self, *flags: str, code: int = 0) -> str:
        out = io.StringIO()
        with patch.object(sys, "argv", ["merge.py", *flags]), contextlib.redirect_stdout(out):
            self.assertEqual(merge.main(), code, out.getvalue())
        return out.getvalue()

    def test_every_account_ends_with_the_newest_copy_byte_for_byte(self) -> None:
        self.session(A, "s1", mtime=1_000, title="old", model="m1")
        self.session(B, "s1", mtime=2_000, title="new", model="m2", isStarred=True)
        self.session(A, "only-a")

        report = self.run_merge("--apply")

        self.assertIn("Aligned: 2 conversations identical across 2", report)
        self.assert_identical("s1")
        self.assert_identical("only-a")
        self.assertEqual(self.field(A, "s1", "title"), "new")
        self.assertTrue(self.field(A, "s1", "isStarred"))
        self.assertEqual(self.path(A, "s1").stat().st_mtime, 2_000)

    def test_a_second_run_has_nothing_to_do(self) -> None:
        self.session(A, "s1", mtime=1_000)
        self.session(B, "s2", mtime=2_000)
        self.run_merge("--apply")

        report = self.run_merge()

        self.assertIn("byte for byte", report)

    def test_archiving_under_one_account_archives_every_copy(self) -> None:
        self.session(A, "s1")
        self.run_merge("--apply")

        self.edit(A, "s1", mtime=5_000, isArchived=True)
        self.run_merge("--apply")

        self.assertTrue(self.field(B, "s1", "isArchived"))
        self.assert_identical("s1")

    def test_unarchiving_under_one_account_unarchives_every_copy(self) -> None:
        self.session(A, "s1", isArchived=True)
        self.session(B, "s1", isArchived=True)
        self.run_merge("--apply")

        self.edit(B, "s1", mtime=5_000, isArchived=False)
        self.run_merge("--apply")

        self.assertFalse(self.field(A, "s1", "isArchived"))

    def test_an_archive_wins_over_a_newer_unrelated_touch_elsewhere(self) -> None:
        """The flag follows the copy whose flag moved, not whichever copy is newest."""
        self.session(A, "s1")
        self.run_merge("--apply")

        self.edit(A, "s1", mtime=5_000, isArchived=True)
        self.edit(B, "s1", mtime=6_000, lastFocusedAt=9)
        self.run_merge("--apply")

        self.assertTrue(self.field(A, "s1", "isArchived"))
        self.assertTrue(self.field(B, "s1", "isArchived"))
        self.assert_identical("s1")

    def test_a_deletion_removes_every_copy_and_is_never_copied_back(self) -> None:
        self.session(A, "s1")
        self.session(B, "s1")
        self.run_merge("--apply")

        self.path(A, "s1").unlink()
        report = self.run_merge("--apply")
        again = self.run_merge("--apply")

        self.assertIn("1 conversations deleted under one account", report)
        self.assertEqual(self.field(B, "s1", "title"), "MISSING")
        self.assertIn("0 copies to create", again)

    def test_a_merged_copy_deleted_before_any_baseline_still_counts_as_deleted(self) -> None:
        """Manifests written before the baseline existed are the only record of those copies."""
        self.session(A, "s1")
        self.run_merge("--apply")
        (self.root / lifecycle.BASELINE_NAME).unlink()

        self.path(B, "s1").unlink()
        self.run_merge("--apply")

        self.assertEqual(self.field(A, "s1", "title"), "MISSING")

    def test_a_resumed_conversation_comes_back_after_its_deletion(self) -> None:
        self.session(A, "s1")
        self.session(B, "s1")
        self.run_merge("--apply")
        self.path(A, "s1").unlink()
        self.run_merge("--apply")

        self.session(B, "s1", mtime=9_000)
        self.run_merge("--apply")

        self.assert_identical("s1")

    def test_without_a_baseline_disagreeing_copies_settle_on_archived(self) -> None:
        self.session(A, "s1", mtime=1_000, isArchived=True)
        self.session(B, "s1", mtime=9_000)

        self.run_merge("--apply")

        self.assertTrue(self.field(A, "s1", "isArchived"))
        self.assert_identical("s1")

    def test_a_conversation_without_a_transcript_is_aligned_but_archived(self) -> None:
        self.session(A, "ghost", transcript=False)
        self.session(B, "live")

        report = self.run_merge("--apply")

        self.assertIn("1 conversations have no transcript left", report)
        self.assertTrue(self.field(B, "ghost", "isArchived"))
        self.assert_identical("ghost")

    def test_an_account_missing_from_the_tree_deletes_nothing(self) -> None:
        """A signed-out or wiped account is not a statement about any one conversation."""
        for account in (A, B, C):
            self.session(account, "s1")
        self.run_merge("--apply")

        self.path(C, "s1").unlink()
        (self.root / C / ORG).rmdir()
        (self.root / C).rmdir()
        self.run_merge("--apply")

        self.assertEqual(self.field(A, "s1", "title"), "s1")

    def test_an_account_whose_last_conversation_was_deleted_still_counts(self) -> None:
        self.session(A, "s1")
        self.session(B, "s1")
        self.run_merge("--apply")

        self.path(A, "s1").unlink()
        self.run_merge("--apply")

        self.assertEqual(self.field(B, "s1", "title"), "MISSING")

    def test_into_current_aligns_only_the_signed_in_account(self) -> None:
        config = self.home / "Library" / "Application Support" / "Claude" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"lastKnownAccountUuid": A}))
        self.session(B, "s1")

        self.run_merge("--apply", "--into=current")

        self.assert_identical("s1")

    def test_from_current_makes_every_account_a_copy_of_the_signed_in_one(self) -> None:
        config = self.home / "Library" / "Application Support" / "Claude" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"lastKnownAccountUuid": A}))
        kept = self.session(A, "kept", mtime=1_000, title="mine", isArchived=True)
        self.session(B, "kept", mtime=9_000, title="newer elsewhere")
        self.session(B, "clutter", mtime=9_000)
        before = kept.read_bytes()

        report = self.run_merge("--apply", "--from=current")

        self.assertIn("Authority: account-a", report)
        self.assertEqual(kept.read_bytes(), before)
        self.assert_identical("kept")
        self.assertTrue(self.field(B, "kept", "isArchived"))
        self.assertEqual(self.field(B, "clutter", "title"), "MISSING")

    def test_from_all_is_refused(self) -> None:
        self.session(A, "s1")

        with self.assertRaises(SystemExit):
            self.run_merge("--from=all")

    def test_report_only_writes_nothing(self) -> None:
        self.session(A, "s1", isArchived=True)
        self.session(B, "s1")

        report = self.run_merge()

        self.assertIn("report only", report)
        self.assertIsNone(self.field(B, "s1", "isArchived"))
        self.assertFalse((self.root / lifecycle.BASELINE_NAME).exists())
        self.assertFalse((self.root / manifest.BACKUP_DIR).exists())

    def test_undo_puts_back_overwritten_removed_and_created_files(self) -> None:
        self.session(A, "s1", mtime=1_000, title="a-title")
        self.session(B, "s1", mtime=2_000, title="b-title")
        self.session(A, "gone")
        self.session(B, "gone")
        self.run_merge("--apply")
        a_original = self.path(A, "s1").read_bytes()
        self.path(A, "gone").unlink()
        self.run_merge("--apply")
        self.session(A, "only-a")
        self.run_merge("--apply")

        self.run_merge("--undo")

        self.assertEqual(self.field(A, "s1", "title"), "a-title")
        self.assertEqual(self.path(B, "gone").exists(), True)
        self.assertFalse(self.path(B, "only-a").exists())
        self.assertNotEqual(self.path(A, "s1").read_bytes(), a_original)
        self.assertFalse((self.root / manifest.BACKUP_DIR).exists())
        self.assertFalse((self.root / lifecycle.BASELINE_NAME).exists())

    def test_the_backup_directory_is_never_read_as_an_account(self) -> None:
        self.session(A, "s1", mtime=1_000)
        self.session(B, "s1", mtime=2_000, title="new")
        self.run_merge("--apply")

        report = self.run_merge()

        self.assertNotIn(manifest.BACKUP_DIR, report.split("Plan:")[0])

    def test_a_corrupt_baseline_stops_the_run_instead_of_guessing(self) -> None:
        self.session(A, "s1")
        (self.root / lifecycle.BASELINE_NAME).write_text("[]")

        with self.assertRaises(SystemExit):
            self.run_merge("--apply")


if __name__ == "__main__":
    unittest.main()
