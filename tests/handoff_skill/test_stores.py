from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.dev.skills.handoff.scripts.stores import (
    SessionSource,
    discover_claude,
    discover_codex,
    publish_claude_index,
    semantic_digest,
)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects = self.root / "projects"
        self.desktop = self.root / "desktop"
        self.projects.mkdir()
        self.desktop.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def write_jsonl(self, path: Path, records: list[dict], tail: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in records) + tail)

    def test_claude_discovery_uses_latest_desktop_title_and_archive(self):
        transcript = self.projects / "proj" / "session.jsonl"
        self.write_jsonl(
            transcript,
            [
                {"sessionId": "s1", "cwd": "/work", "type": "user", "message": {"content": "first"}},
                {"sessionId": "s1", "cwd": "/work", "type": "user", "message": {"content": "latest"}},
            ],
        )
        (self.desktop / "acct-a" / "org").mkdir(parents=True)
        (self.desktop / "acct-a" / "org" / "local_s1.json").write_text(
            json.dumps(
                {"cliSessionId": "s1", "title": "latest title", "lastActivityAt": 20, "isArchived": True}
            )
        )
        (self.desktop / "acct-b" / "org").mkdir(parents=True)
        older = self.desktop / "acct-b" / "org" / "local_s1.json"
        older.write_text(json.dumps({"cliSessionId": "s1", "title": "old title", "lastActivityAt": 10}))
        os.utime(older, (1, 1))
        os.utime(self.desktop / "acct-a" / "org" / "local_s1.json", (2, 2))
        found = discover_claude(self.projects, self.desktop)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].title, "latest title")
        self.assertTrue(found[0].archived)
        self.assertEqual(found[0].session_id, "s1")

    def test_claude_discovery_skips_sidechains_and_malformed_files(self):
        self.write_jsonl(
            self.projects / "p" / "good.jsonl",
            [{"sessionId": "good", "cwd": "/x", "type": "user", "message": {"content": "title"}}],
        )
        self.write_jsonl(self.projects / "p" / "bad.jsonl", [], "{bad\n")
        self.write_jsonl(self.projects / "p" / "nested" / "side.jsonl", [{"sessionId": "side"}])
        self.assertEqual([s.session_id for s in discover_claude(self.projects, self.desktop)], ["good"])

    def test_claude_metadata_cache_reads_unchanged_files_once_and_invalidates_changes(self):
        path = self.projects / "p" / "cached.jsonl"
        self.write_jsonl(
            path, [{"sessionId": "cached", "cwd": "/x", "type": "user", "message": {"content": "one"}}]
        )
        import plugins.dev.skills.handoff.scripts.stores as stores

        stores._CLAUDE_CACHE.clear()
        with patch.object(stores, "_records", wraps=stores._records) as read:
            discover_claude(self.projects, self.desktop)
            discover_claude(self.projects, self.desktop)
            self.assertEqual(read.call_count, 1)
            with path.open("a") as handle:
                handle.write(
                    json.dumps(
                        {"sessionId": "cached", "cwd": "/x", "type": "user", "message": {"content": "two"}}
                    )
                    + "\n"
                )
            discover_claude(self.projects, self.desktop)
            self.assertEqual(read.call_count, 2)

    def test_claude_discovery_rejects_sidechain_only_and_symlinked_inputs(self):
        self.write_jsonl(
            self.projects / "p" / "side.jsonl", [{"sessionId": "side", "cwd": "/x", "isSidechain": True}]
        )
        outside = self.root / "outside.jsonl"
        self.write_jsonl(
            outside, [{"sessionId": "escape", "cwd": "/x", "type": "user", "message": {"content": "x"}}]
        )
        (self.projects / "linked.jsonl").symlink_to(outside)
        self.assertEqual(discover_claude(self.projects, self.desktop), [])

    def test_fork_identity_comes_from_uuid_filename_not_inherited_prefix(self):
        sid = "11111111-1111-4111-8111-111111111111"
        path = self.projects / "fork" / (sid + ".jsonl")
        self.write_jsonl(
            path,
            [
                {
                    "sessionId": "parent-session",
                    "cwd": "/work",
                    "type": "user",
                    "message": {"content": "inherited context"},
                }
            ],
        )
        self.assertEqual(discover_claude(self.projects, self.desktop)[0].session_id, sid)

    def test_publish_unions_accounts_preserves_fields_and_is_idempotent(self):
        source_path = self.projects / "p" / "s1.jsonl"
        self.write_jsonl(
            source_path,
            [{"sessionId": "s1", "cwd": "/work", "type": "user", "message": {"content": "A title"}}],
        )
        source = SessionSource("claude", "s1", source_path, "/work", "A title", archived=False)
        for account in ("a", "b"):
            (self.desktop / account / "org").mkdir(parents=True)
        existing = self.desktop / "a" / "org" / "local_s1.json"
        existing.write_text(
            json.dumps(
                {
                    "sessionId": "local_s1",
                    "cliSessionId": "s1",
                    "title": "Custom",
                    "isArchived": True,
                    "accountOnly": "keep",
                    "createdAt": 11,
                }
            )
        )
        publish_claude_index(source, self.desktop)
        for account in ("a", "b"):
            data = json.loads((self.desktop / account / "org" / "local_s1.json").read_text())
            self.assertEqual(data.get("accountOnly"), "keep" if account == "a" else None)
            self.assertEqual(data["title"], "A title")
            self.assertTrue(data["isArchived"] if account == "a" else not data["isArchived"])
        first = {p: p.read_bytes() for p in self.desktop.rglob("local_s1.json")}
        publish_claude_index(source, self.desktop)
        self.assertEqual(first, {p: p.read_bytes() for p in self.desktop.rglob("local_s1.json")})

    def make_db(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE threads (id TEXT, title TEXT, cwd TEXT, rollout_path TEXT, "
            "archived INTEGER, source TEXT, agent_path TEXT)"
        )
        rows = [
            ("human", "Human", "/w", str(self.root / "rollout.jsonl"), 1, "codex", None),
            ("agent", "Agent", "/w", str(self.root / "agent.jsonl"), 0, "codex", "parent/agent"),
            ("bad-source", "Bad", "/w", str(self.root / "bad.jsonl"), 0, "unsupported", None),
        ]
        conn.executemany("INSERT INTO threads VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        conn.close()

    def test_codex_discovery_is_read_only_and_filters_sources(self):
        db = self.root / "codex.sqlite"
        rollout = self.root / "rollout.jsonl"
        rollout.write_text('{"type":"session_meta","payload":{"cwd":"/w"}}\n')
        (self.root / "agent.jsonl").write_text("x\n")
        (self.root / "bad.jsonl").write_text("x\n")
        self.make_db(db)
        before = db.stat().st_mtime_ns
        found = discover_codex(db)
        self.assertEqual([(s.session_id, s.archived) for s in found], [("human", True)])
        self.assertEqual(before, db.stat().st_mtime_ns)

    def test_codex_discovery_accepts_native_human_sources_and_name(self):
        db = self.root / "codex.sqlite"
        rollout = self.root / "rollout.jsonl"
        rollout.write_text('{"type":"session_meta","payload":{"cwd":"/w"}}\n')
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE threads (id TEXT, name TEXT, title TEXT, cwd TEXT, "
            "rollout_path TEXT, source TEXT, agent_path TEXT)"
        )
        conn.executemany(
            "INSERT INTO threads VALUES (?,?,?,?,?,?,?)",
            [
                ("v", "Native name", "Old", "/w", str(rollout), "vscode", None),
                ("e", "", "Exec", "/w", str(rollout), "exec", None),
            ],
        )
        conn.commit()
        conn.close()
        self.assertEqual([s.title for s in discover_codex(db)], ["Native name", "Exec"])

    def test_codex_discovery_reports_corrupt_and_invalid_databases(self):
        broken = self.root / "broken.sqlite"
        broken.write_text("not sqlite")
        with self.assertRaisesRegex(ValueError, "Codex database"):
            discover_codex(broken)
        invalid = self.root / "invalid.sqlite"
        connection = sqlite3.connect(invalid)
        connection.close()
        with self.assertRaisesRegex(ValueError, "threads"):
            discover_codex(invalid)

    def test_codex_discovery_rejects_rollout_outside_database_parent(self):
        db = self.root / "codex.sqlite"
        outside = Path(tempfile.mkdtemp()) / "outside.jsonl"
        outside.write_text("{}\n")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE threads (id TEXT, title TEXT, cwd TEXT, rollout_path TEXT)")
        conn.execute("INSERT INTO threads VALUES (?,?,?,?)", ("x", "x", "/x", str(outside)))
        conn.commit()
        conn.close()
        self.assertEqual(discover_codex(db), [])

    def test_digest_ignores_metadata_ids_and_partial_tail(self):
        a = self.root / "a.jsonl"
        b = self.root / "b.jsonl"
        records_a = [
            {"timestamp": "1", "type": "user", "message": {"role": "user", "content": "hello"}},
            {
                "timestamp": "2",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "x", "name": "run", "input": {"cmd": "ok"}}],
                },
            },
        ]
        records_b = [
            {
                "timestamp": "9",
                "uuid": "other",
                "type": "user",
                "message": {"role": "user", "content": "hello"},
            },
            {
                "timestamp": "8",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "y", "name": "run", "input": {"cmd": "ok"}}],
                },
            },
        ]
        self.write_jsonl(a, records_a, '{"partial":')
        self.write_jsonl(b, records_b)
        self.assertEqual(semantic_digest(a, "claude"), semantic_digest(b, "claude"))

    def test_digest_reports_malformed_complete_json(self):
        path = self.root / "broken.jsonl"
        path.write_text('{"type":"user"}\nnot-json\n{"partial":')
        with self.assertRaisesRegex(ValueError, "malformed JSON"):
            semantic_digest(path, "claude")


if __name__ == "__main__":
    unittest.main()
