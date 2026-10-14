"""An index write either lands whole or not at all — never half a file."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import atomic
import lifecycle
import mirror


class AtomicWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "local_s1.json"
        self.path.write_bytes(b'{"title":"old"}')
        os.chmod(self.path, 0o640)

    def test_replaces_content_keeps_mode_and_takes_the_given_mtime(self) -> None:
        atomic.write_bytes(self.path, b'{"title":"new"}', mtime=1_234.0)

        self.assertEqual(self.path.read_bytes(), b'{"title":"new"}')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.path.stat().st_mtime, 1_234.0)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ["local_s1.json"])

    def test_a_new_file_is_private_unless_a_mode_is_given(self) -> None:
        fresh = self.directory / "local_s2.json"
        atomic.write_bytes(fresh, b"{}")
        explicit = self.directory / "local_s3.json"
        atomic.write_bytes(explicit, b"{}", mode=0o644)

        self.assertEqual(fresh.stat().st_mode & 0o777, 0o600)
        self.assertEqual(explicit.stat().st_mode & 0o777, 0o644)

    def test_a_failure_before_the_rename_leaves_the_original_and_no_temporary(self) -> None:
        with patch.object(os, "replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            atomic.write_bytes(self.path, b'{"title":"half"}')

        self.assertEqual(self.path.read_bytes(), b'{"title":"old"}')
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ["local_s1.json"])

    def test_the_file_is_only_ever_renamed_into_place(self) -> None:
        """Nothing writes into the destination itself, so a reader sees old bytes or new bytes."""
        renamed: list[tuple[str, str]] = []
        real_replace = os.replace

        def spy(source, destination):
            renamed.append((Path(source).parent.as_posix(), Path(destination).name))
            self.assertEqual(self.path.read_bytes(), b'{"title":"old"}')
            real_replace(source, destination)

        with patch.object(os, "replace", spy):
            atomic.write_bytes(self.path, b'{"title":"new"}')

        self.assertEqual(renamed, [(self.directory.as_posix(), "local_s1.json")])


class MirrorWritesAreAtomicTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stale = self.root / "a" / "org" / "local_s1.json"
        self.stale.parent.mkdir(parents=True)
        self.stale.write_bytes(json.dumps({"sessionId": "s1", "title": "old"}).encode())
        os.chmod(self.stale, 0o600)
        self.fresh = self.root / "b" / "org" / "local_s1.json"

    def plan(self) -> mirror.MirrorPlan:
        content = json.dumps({"sessionId": "s1", "title": "new"}).encode()
        return mirror.MirrorPlan(
            [
                mirror.Write(self.stale, content, 2_000.0, False, ("title",)),
                mirror.Write(self.fresh, content, 2_000.0, True, ()),
            ],
            [],
        )

    def test_every_write_goes_through_a_rename_and_keeps_the_canonical_mtime(self) -> None:
        with patch.object(os, "replace", wraps=os.replace) as replace:
            mirror.apply_mirror(self.root, self.plan(), set())

        self.assertEqual(replace.call_count, 2)
        for path in (self.stale, self.fresh):
            self.assertEqual(json.loads(path.read_text())["title"], "new")
            self.assertEqual(path.stat().st_mtime, 2_000.0)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual([p.name for p in path.parent.iterdir()], ["local_s1.json"])

    def test_a_crash_mid_write_leaves_the_stale_copy_whole(self) -> None:
        with patch.object(os, "replace", side_effect=OSError("killed")), self.assertRaises(OSError):
            mirror.apply_mirror(self.root, self.plan(), set())

        self.assertEqual(json.loads(self.stale.read_text())["title"], "old")
        self.assertEqual([p.name for p in self.stale.parent.iterdir()], ["local_s1.json"])

    def test_a_leftover_temporary_is_never_read_as_an_index_entry(self) -> None:
        leftover = self.stale.parent / ".local_s1.json.abc123.tmp"
        leftover.write_text("{")

        self.assertEqual(list(self.stale.parent.glob("local_*.json")), [self.stale])
        self.assertTrue(lifecycle.BASELINE_NAME.startswith("."))


if __name__ == "__main__":
    unittest.main()
