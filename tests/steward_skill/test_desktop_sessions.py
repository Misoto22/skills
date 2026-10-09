"""The desktop index reader on its own, against a forged index tree.

The inventory tests drive it end to end; these pin the two decisions it makes for
itself: which index entries count as open, and which worktree an open one holds.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "dev" / "skills" / "steward" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import desktop_sessions
from session_trace import Session


class OpenSessionsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def entry(self, account: str, payload: dict | str, name: str = "x") -> None:
        org = self.root / account / "org"
        org.mkdir(parents=True, exist_ok=True)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (org / f"local_{name}.json").write_text(text, encoding="utf-8")

    def test_archived_unreadable_and_pathless_entries_hold_nothing(self) -> None:
        self.entry("a", {"sessionId": "s1", "cwd": "/w", "isArchived": True}, "s1")
        self.entry("a", "{torn", "s2")
        self.entry("a", {"sessionId": "s3"}, "s3")
        self.entry("a", {"sessionId": "s4", "cwd": "/w", "lastActivityAt": 5_000}, "s4")

        found = desktop_sessions.open_sessions(self.root)

        self.assertEqual([(s.id, s.cwd, s.last_activity, s.open) for s in found], [("s4", "/w", 5.0, True)])

    def test_one_conversation_under_two_accounts_is_read_once_per_path(self) -> None:
        payload = {"sessionId": "s1", "cwd": "/w/sub", "worktreePath": "/w"}
        self.entry("a", payload, "s1")
        self.entry("b", payload, "s1")

        found = desktop_sessions.open_sessions(self.root)

        self.assertEqual(sorted(s.cwd for s in found), ["/w", "/w/sub"])

    def test_no_index_is_none_not_empty(self) -> None:
        self.assertIsNone(desktop_sessions.open_sessions(self.root / "missing"))

    def test_the_override_names_the_root(self) -> None:
        with mock.patch.dict(os.environ, {desktop_sessions.SESSIONS_ROOT_ENV: str(self.root)}):
            self.assertEqual(desktop_sessions.sessions_root(), self.root)


class HeldByWorktreeTests(unittest.TestCase):
    def test_a_path_belongs_to_the_deepest_worktree_once_per_conversation(self) -> None:
        primary = os.path.realpath(tempfile.gettempdir())
        nested = os.path.join(primary, ".claude", "worktrees", "w")
        sessions = [
            Session("claude-desktop", "s1", nested, 1.0, open=True),
            Session("claude-desktop", "s1", os.path.join(nested, "src"), 1.0, open=True),
            Session("claude-desktop", "s2", os.path.join(primary, "docs"), 1.0, open=True),
            Session("claude-desktop", "s3", "/elsewhere", 1.0, open=True),
        ]

        held = desktop_sessions.held_by_worktree(sessions, [primary, nested])

        self.assertEqual({k: [s.id for s in v] for k, v in held.items()}, {nested: ["s1"], primary: ["s2"]})


if __name__ == "__main__":
    unittest.main()
