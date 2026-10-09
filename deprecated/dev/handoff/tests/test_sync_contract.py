"""Acceptance tests for the continuous sync contract using realistic local stores."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from plugins.dev.skills.handoff.scripts import formats, sync
from plugins.dev.skills.handoff.scripts.stores import SessionSource


class RealisticNative:
    """Fake native boundary that writes a real Codex rollout and SQLite row."""

    def __init__(self, paths: sync.Paths):
        self.paths = paths
        self.calls: list[tuple[str, str]] = []
        self.imports: dict[str, str] = {}
        self.hashes: dict[str, str] = {}
        self.rollouts: dict[str, Path] = {}
        self.counter = 0
        self.fail_next = False
        self.fail_calls: set[int] = set()
        self.unchanged_once = False
        self.resumed: set[str] = set()

    def existing_imports(self):
        return [
            {
                "source_path": source,
                "imported_thread_id": thread,
                "content_sha256": self.hashes.get(source),
            }
            for source, thread in self.imports.items()
        ]

    def import_session(self, source: SessionSource):
        if self.fail_next or self.counter + 1 in self.fail_calls:
            self.fail_next = False
            raise RuntimeError("native unavailable")
        if str(source.path) in self.imports and str(source.path) not in self.resumed:
            thread = self.imports[str(source.path)]
            return {"thread_id": thread, "rollout_path": self.rollouts[str(source.path)], "changed": False}
        self.counter += 1
        thread = f"native-{self.counter}"
        rollout = self.paths.codex_sessions / "2026" / f"rollout-{self.counter}.jsonl"
        records, _ = formats.read_jsonl(source.path)
        lines = [formats.codex_session_meta(thread, source.cwd, "Claude Code")]
        lines.extend(formats.claude_to_codex(records, turn_id=thread))
        rollout.parent.mkdir(parents=True, exist_ok=True)
        rollout.write_text("".join(json.dumps(line) + "\n" for line in lines))
        self._insert(thread, source, rollout)
        self.calls.append((str(source.path), thread))
        self.imports[str(source.path)] = thread
        self.hashes[str(source.path)] = hashlib.sha256(source.path.read_bytes()).hexdigest()
        self.rollouts[str(source.path)] = rollout
        changed = not self.unchanged_once
        self.unchanged_once = False
        return {"thread_id": thread, "rollout_path": rollout, "changed": changed}

    def _insert(self, thread: str, source: SessionSource, rollout: Path):
        with closing(sqlite3.connect(self.paths.codex_database)) as conn:
            conn.execute(
                "INSERT INTO threads VALUES (?,?,?,?,?,?,?,?)",
                (thread, source.title, source.title, source.cwd, str(rollout), 0, "vscode", None),
            )
            conn.commit()

    def read_thread(self, thread_id: str):
        with closing(sqlite3.connect(self.paths.codex_database)) as conn:
            row = conn.execute("SELECT rollout_path FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if not row or not Path(row[0]).is_file():
            raise RuntimeError("native thread path is unreadable")
        return {"id": thread_id, "path": row[0]}


class SyncContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = sync.Paths(
            self.root,
            codex_database=self.root / "codex.sqlite",
            codex_sessions=self.root / "codex-sessions",
        )
        self.paths.claude_projects.mkdir(parents=True)
        self.paths.claude_desktop.mkdir(parents=True)
        self.paths.codex_sessions.mkdir(parents=True)
        for account in ("account-a", "account-b"):
            (self.paths.claude_desktop / account / "org").mkdir(parents=True)
        with closing(sqlite3.connect(self.paths.codex_database)) as conn:
            conn.execute(
                "CREATE TABLE threads (id TEXT, name TEXT, title TEXT, cwd TEXT, "
                "rollout_path TEXT, archived INTEGER, source TEXT, agent_path TEXT)"
            )
            conn.commit()
        self.native = RealisticNative(self.paths)
        self.addCleanup(self.tmp.cleanup)

    def claude(self, name="claude.jsonl", text="hello") -> Path:
        path = self.paths.claude_projects / "project" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "sessionId": "claude-session",
                    "cwd": str(self.root),
                    "type": "user",
                    "message": {"content": text},
                }
            )
            + "\n"
        )
        return path

    def codex(self, name="original.jsonl", text="from codex") -> Path:
        path = self.root / name
        path.write_text(
            json.dumps(formats.codex_session_meta("codex-original", str(self.root), "Codex"))
            + "\n"
            + json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    },
                }
            )
            + "\n"
        )
        with closing(sqlite3.connect(self.paths.codex_database)) as conn:
            conn.execute(
                "INSERT INTO threads VALUES (?,?,?,?,?,?,?,?)",
                ("codex-original", "Original", "Original", str(self.root), str(path), 0, "vscode", None),
            )
            conn.commit()
        return path

    def test_claude_import_is_stable_for_three_cycles_and_never_bounces(self):
        self.claude()
        for _ in range(3):
            report = sync.synchronize(self.paths, self.native, apply=True)
            self.assertFalse(report["errors"])
        self.assertEqual(len(self.native.calls), 1)
        self.assertEqual(len(list(self.paths.codex_sessions.rglob("rollout-*.jsonl"))), 1)

    def test_codex_original_is_mirrored_to_both_accounts_with_target_identity(self):
        rollout = self.codex()
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(report["results"][0]["status"], "copied")
        targets = list(self.paths.claude_projects.rglob("*.jsonl"))
        self.assertEqual(len(targets), 1)
        target_id = targets[0].stem
        self.assertTrue(target_id)
        for account in ("account-a", "account-b"):
            entry = self.paths.claude_desktop / account / "org" / f"local_{target_id}.json"
            self.assertTrue(entry.is_file())
            self.assertEqual(json.loads(entry.read_text())["cliSessionId"], target_id)
        self.assertTrue(rollout.is_file())

    def test_continuations_create_one_distinct_native_import_per_changed_claude_branch(self):
        source = self.claude()
        sync.synchronize(self.paths, self.native, apply=True)
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "claude-session",
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "continued one"},
                    }
                )
                + "\n"
            )
        sync.synchronize(self.paths, self.native, apply=True)
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "claude-session",
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "continued two"},
                    }
                )
                + "\n"
            )
        sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(len(self.native.calls), 3)
        self.assertEqual(len({thread for _, thread in self.native.calls}), 3)

    def test_continued_native_source_arrives_once_without_duplicate_lines(self):
        rollout = self.codex()
        sync.synchronize(self.paths, self.native, apply=True)
        target = next(self.paths.claude_projects.rglob("*.jsonl"))
        before = target.read_text()
        with rollout.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "answer"}],
                        },
                    }
                )
                + "\n"
            )
        sync.synchronize(self.paths, self.native, apply=True)
        after = target.read_text()
        self.assertGreater(len(after), len(before))
        sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(target.read_text(), after)

    def test_generated_claude_mirror_continuation_creates_one_native_branch(self):
        self.codex()
        sync.synchronize(self.paths, self.native, apply=True)
        target = next(self.paths.claude_projects.rglob("*.jsonl"))
        with target.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": target.stem,
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "Claude continuation"},
                    }
                )
                + "\n"
            )
        for _ in range(3):
            sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(len(self.native.calls), 1)
        self.assertEqual(len({path for path, _ in self.native.calls}), 1)

    def test_source_and_mirror_divergence_preserves_original_bytes_and_branches(self):
        source = self.claude()
        original = source.read_bytes()
        sync.synchronize(self.paths, self.native, apply=True)
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "claude-session",
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "source divergence"},
                    }
                )
                + "\n"
            )
        sync.synchronize(self.paths, self.native, apply=True)
        self.assertNotEqual(source.read_bytes(), original)
        self.assertGreaterEqual(len(list((self.paths.codex_sessions).rglob("rollout-*.jsonl"))), 2)

    def test_simultaneous_source_and_mirror_changes_preserve_both_original_files(self):
        source = self.claude()
        sync.synchronize(self.paths, self.native, apply=True)
        rollout = self.native.rollouts[str(source)]
        source_before = source.read_bytes()
        rollout_before = rollout.read_bytes()
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "claude-session",
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "Claude side"},
                    }
                )
                + "\n"
            )
        with rollout.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "Codex side"}],
                        },
                    }
                )
                + "\n"
            )
        sync.synchronize(self.paths, self.native, apply=True)
        self.assertTrue(source.read_bytes().startswith(source_before))
        self.assertTrue(rollout.read_bytes().startswith(rollout_before))
        self.assertGreaterEqual(len(self.native.calls), 2)

    def test_changed_source_retries_after_native_failure(self):
        source = self.claude()
        self.native.fail_next = True
        failed = sync.synchronize(self.paths, self.native, apply=True)
        self.assertTrue(failed["errors"])
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "claude-session",
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "retry"},
                    }
                )
                + "\n"
            )
        retried = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(retried["errors"])
        self.assertEqual(len(self.native.calls), 1)

    def test_partial_tail_is_imported_once_when_completed(self):
        source = self.paths.claude_projects / "project" / "partial.jsonl"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps(
                {"sessionId": "partial", "cwd": str(self.root), "type": "user", "message": {"content": "one"}}
            )
            + "\n{"
        )
        sync.synchronize(self.paths, self.native, apply=True)
        source.write_text(
            source.read_text()[:-1]
            + json.dumps(
                {"sessionId": "partial", "cwd": str(self.root), "type": "user", "message": {"content": "two"}}
            )
            + "\n"
        )
        sync.synchronize(self.paths, self.native, apply=True)
        sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(len(self.native.calls), 2)

    def test_existing_import_adoption_requires_matching_source_digest(self):
        source = self.claude()
        self.native.import_session(SessionSource("claude", "claude-session", source, str(self.root), "hello"))
        self.native.calls.clear()
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(self.native.calls, [])
        with source.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "sessionId": "claude-session",
                        "cwd": str(self.root),
                        "type": "user",
                        "message": {"content": "changed"},
                    }
                )
                + "\n"
            )
        sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(len(self.native.calls), 1)

    def test_snapshot_path_is_reused_after_managed_import_failure(self):
        self.claude()
        self.native.unchanged_once = True
        self.native.fail_calls.add(2)
        sync.synchronize(self.paths, self.native, apply=True)
        state = json.loads(self.paths.state.read_text())
        snapshots = [
            item.get("snapshot_path") for item in state["claude"].values() if item.get("snapshot_path")
        ]
        self.assertEqual(len(snapshots), 1)
        self.native.fail_calls.clear()
        self.native.unchanged_once = True
        sync.synchronize(self.paths, self.native, apply=True)
        state = json.loads(self.paths.state.read_text())
        self.assertEqual(
            snapshots[0],
            next(item["snapshot_path"] for item in state["claude"].values() if item.get("snapshot_path")),
        )

    def test_corrupt_state_stops_without_any_import(self):
        self.claude()
        self.paths.state.parent.mkdir(parents=True)
        self.paths.state.write_text("{broken")
        with self.assertRaises(ValueError):
            sync.synchronize(self.paths, self.native, apply=True)
        self.assertEqual(self.native.calls, [])

    def test_state_target_cannot_escape_project_store(self):
        self.codex()
        sync.synchronize(self.paths, self.native, apply=True)
        state = json.loads(self.paths.state.read_text())
        outside = self.root / "protected.txt"
        outside.write_text("preserve")
        next(iter(state["codex"].values()))["target_path"] = str(outside)
        self.paths.state.write_text(json.dumps(state))
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertTrue(report["errors"])
        self.assertEqual(outside.read_text(), "preserve")

    def test_adopted_archived_import_does_not_echo_but_preserves_continuation(self):
        source = self.claude()
        self.native.import_session(SessionSource("claude", "claude-session", source, str(self.root), "hello"))
        old = self.native.rollouts[str(source)]
        archived = self.root / "archived_sessions" / old.name
        archived.parent.mkdir()
        old.rename(archived)
        with closing(sqlite3.connect(self.paths.codex_database)) as conn:
            conn.execute("UPDATE threads SET rollout_path = ?, archived = 1", (str(archived),))
            conn.commit()
        for _ in range(3):
            report = sync.synchronize(self.paths, self.native, apply=True)
            self.assertFalse(report["errors"])
            self.assertFalse(json.loads(self.paths.state.read_text())["codex"])
        self.paths.state.unlink()
        with archived.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "existing native continuation"}],
                        },
                    }
                )
                + "\n"
            )
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(len(json.loads(self.paths.state.read_text())["codex"]), 1)

    def test_archived_import_keeps_identity_and_propagates_real_continuation(self):
        self.claude()
        sync.synchronize(self.paths, self.native, apply=True)
        old = next(iter(self.native.rollouts.values()))
        archived = self.root / "archived_sessions" / old.name
        archived.parent.mkdir()
        old.rename(archived)
        with closing(sqlite3.connect(self.paths.codex_database)) as conn:
            conn.execute("UPDATE threads SET rollout_path = ?, archived = 1", (str(archived),))
            conn.commit()
        for _ in range(3):
            report = sync.synchronize(self.paths, self.native, apply=True)
            self.assertFalse(report["errors"])
            self.assertFalse(json.loads(self.paths.state.read_text())["codex"])
        with archived.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "continued after archive"}],
                        },
                    }
                )
                + "\n"
            )
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(len(json.loads(self.paths.state.read_text())["codex"]), 1)

    def test_old_import_remains_owned_after_source_forks(self):
        source = self.claude()
        sync.synchronize(self.paths, self.native, apply=True)
        source.write_text(source.read_text().replace("hello", "updated"))
        sync.synchronize(self.paths, self.native, apply=True)
        for _ in range(3):
            report = sync.synchronize(self.paths, self.native, apply=True)
            self.assertFalse(report["errors"])
        self.assertEqual(len(self.native.calls), 2)
        self.assertFalse(json.loads(self.paths.state.read_text())["codex"])

    def test_generated_target_rejects_a_symlinked_project_directory(self):
        import re

        self.codex()
        outside = self.root / "outside"
        outside.mkdir()
        project = self.paths.claude_projects / re.sub(r"[^a-zA-Z0-9]", "-", str(self.root))
        project.symlink_to(outside, target_is_directory=True)
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertTrue(report["errors"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_deleted_generated_file_is_rebuilt_with_its_full_history(self):
        self.codex()
        sync.synchronize(self.paths, self.native, apply=True)
        target = next(self.paths.claude_projects.rglob("*.jsonl"))
        expected = sync.semantic_digest(target, "claude")
        target.unlink()
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(sync.semantic_digest(target, "claude"), expected)

    def test_partial_journaled_write_recovers_exact_bytes_without_duplicate_lines(self):
        self.codex()
        sync.synchronize(self.paths, self.native, apply=True)
        target = next(self.paths.claude_projects.rglob("*.jsonl"))
        expected = target.read_bytes()
        state = json.loads(self.paths.state.read_text())
        item = next(iter(state["codex"].values()))
        stage = target.parent / ".handoff-interrupted"
        stage.write_bytes(expected)
        item["pending"] = {key: value for key, value in item.items() if key != "pending"}
        item["pending"]["stage_path"] = str(stage)
        item.pop("source_digest")
        item.pop("generated_digest")
        target.write_bytes(expected[: len(expected) // 2])
        self.paths.state.write_text(json.dumps(state))
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(target.read_bytes(), expected)
        self.assertFalse(stage.exists())

    def test_removed_worktree_import_uses_a_snapshot_and_preserves_original(self):
        source = self.claude()
        missing = self.root / "removed-worktree"
        records = source.read_text().replace(str(self.root), str(missing))
        source.write_text(records)
        original = source.read_bytes()
        for _ in range(2):
            report = sync.synchronize(self.paths, self.native, apply=True)
            self.assertFalse(report["errors"])
        self.assertEqual(len(self.native.calls), 1)
        imported_path = Path(self.native.calls[0][0])
        self.assertNotEqual(imported_path, source)
        self.assertEqual(imported_path.stat().st_mode & 0o777, 0o600)
        imported = json.loads(imported_path.read_text().splitlines()[0])
        self.assertEqual(imported["cwd"], str(self.root))
        self.assertEqual(source.read_bytes(), original)
        source.write_text(source.read_text().replace("hello", "continued after import"))
        report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(len(self.native.calls), 2)

    def test_generated_target_uses_claude_project_directory(self):
        self.codex()
        sync.synchronize(self.paths, self.native, apply=True)
        import re

        target = next(self.paths.claude_projects.rglob("*.jsonl"))
        self.assertEqual(target.parent.name, re.sub(r"[^a-zA-Z0-9]", "-", str(self.root)))

    def test_unchanged_scan_writes_one_checkpoint_instead_of_one_per_source(self):
        for name in ("one", "two", "three"):
            source = self.claude(name + ".jsonl")
            source.write_text(source.read_text().replace("claude-session", name))
        sync.synchronize(self.paths, self.native, apply=True)
        with patch.object(sync, "_save", wraps=sync._save) as save:
            report = sync.synchronize(self.paths, self.native, apply=True)
        self.assertFalse(report["errors"])
        self.assertEqual(save.call_count, 1)

    def test_native_read_thread_rejects_missing_rollout_path(self):
        with self.assertRaisesRegex(RuntimeError, "unreadable"):
            self.native.read_thread("missing-thread")


if __name__ == "__main__":
    unittest.main()
