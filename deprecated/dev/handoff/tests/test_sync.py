from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.dev.skills.handoff.scripts import sync


class FakeNative:
    def __init__(self, continued: bool = False, fail: bool = False):
        self.continued = continued
        self.fail = fail
        self.calls = 0

    def existing_imports(self):
        return []

    def import_session(self, source):
        self.calls += 1
        if self.fail:
            raise RuntimeError("offline")
        return {
            "thread_id": f"thread-{self.calls}",
            "rollout_path": source.path,
            "changed": not self.continued,
        }

    def read_thread(self, thread_id):
        return {"id": thread_id, "path": "ok"}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = sync.Paths(self.root, codex_database=self.root / "db.sqlite")
        self.paths.claude_projects.mkdir(parents=True)
        (self.paths.claude_projects / "project").mkdir()
        self.claude_path = self.paths.claude_projects / "project" / "s.jsonl"
        self.claude_path.write_text(
            json.dumps({"sessionId": "s", "cwd": "/w", "type": "user", "message": {"content": "hello"}})
            + "\n"
        )
        self.desktop = self.paths.claude_desktop / "account" / "org"
        self.desktop.mkdir(parents=True)
        self.addCleanup(self.tmp.cleanup)

    def _db(self, rollout: Path):
        conn = sqlite3.connect(self.paths.codex_database)
        conn.execute(
            "CREATE TABLE threads (id TEXT, title TEXT, cwd TEXT, "
            "rollout_path TEXT, archived INTEGER, source TEXT, agent_path TEXT)"
        )
        conn.execute(
            "INSERT INTO threads VALUES (?,?,?,?,?,?,?)", ("c", "Codex", "/w", str(rollout), 0, "codex", None)
        )
        conn.commit()
        conn.close()

    def test_claude_copy_is_stable_and_publishes_all_accounts(self):
        native = FakeNative()
        with patch.object(sync, "discover_codex", return_value=[]):
            first = sync.synchronize(self.paths, native, apply=True)
            second = sync.synchronize(self.paths, native, apply=True)
        self.assertEqual(first["results"][0]["status"], "imported")
        self.assertEqual(second["results"][0]["status"], "unchanged")
        self.assertEqual(native.calls, 1)
        self.assertTrue((self.desktop / "local_s.json").exists())

    def test_codex_history_gets_owned_claude_transcript(self):
        rollout = self.root / "rollout.jsonl"
        rollout.write_text(
            json.dumps({"type": "session_meta", "payload": {"cwd": "/w"}})
            + "\n"
            + json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "hi"}],
                    },
                }
            )
            + "\n"
        )
        self._db(rollout)
        with patch.object(sync, "discover_claude", return_value=[]):
            report = sync.synchronize(self.paths, FakeNative(), apply=True)
        self.assertEqual(report["results"][0]["status"], "copied")
        self.assertEqual(len(list(self.paths.claude_projects.rglob("*.jsonl"))), 2)

    def test_native_failure_is_reported_and_retried(self):
        with patch.object(sync, "discover_codex", return_value=[]):
            failed = sync.synchronize(self.paths, FakeNative(fail=True), apply=True)
            retried = sync.synchronize(self.paths, FakeNative(), apply=True)
        self.assertEqual(failed["errors"][0]["status"], "error")
        self.assertEqual(retried["results"][0]["status"], "imported")


if __name__ == "__main__":
    unittest.main()
