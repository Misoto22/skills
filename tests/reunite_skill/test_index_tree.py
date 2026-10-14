"""Reading the per-account index tree: what counts as an entry, an account, and a scope."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import index_tree


class IndexTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def entry(self, account: str, org: str, sid: str, activity: int = 1) -> None:
        path = self.root / account / org / f"local_{sid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"sessionId": sid, "cliSessionId": f"cli-{sid}", "lastActivityAt": activity}
        path.write_text(json.dumps(data))

    def test_only_session_entries_under_account_directories_are_read(self) -> None:
        self.entry("acct", "org", "s1")
        (self.root / "acct" / "org" / "scheduled-tasks.json").write_text('{"tasks": []}')
        (self.root / "acct" / "org" / "local_broken.json").write_text("{")
        (self.root / ".session-merge-backup" / "acct" / "org").mkdir(parents=True)

        tree = index_tree.scan(self.root)

        self.assertEqual(list(tree), ["acct"])
        self.assertEqual([e.session_id for e in index_tree.flatten(tree)], ["s1"])

    def test_the_landing_org_and_scope_follow_the_latest_activity(self) -> None:
        self.entry("acct", "old-org", "s1", activity=5)
        self.entry("acct", "new-org", "s2", activity=9)
        (self.root / "empty" / "only-org").mkdir(parents=True)

        tree = index_tree.scan(self.root)

        self.assertEqual(index_tree.landing_org(tree["acct"]), "new-org")
        self.assertEqual(index_tree.scopes_of(tree), {"acct": "acct/new-org", "empty": "empty/only-org"})

    def test_transcript_ids_are_the_jsonl_stems_one_level_down(self) -> None:
        projects = self.root / "projects"
        (projects / "proj").mkdir(parents=True)
        (projects / "proj" / "cli-s1.jsonl").write_text("{}")
        (projects / "stray.jsonl").write_text("{}")

        self.assertEqual(index_tree.transcript_ids(projects), {"cli-s1"})
        self.assertEqual(index_tree.transcript_ids(self.root / "missing"), set())


if __name__ == "__main__":
    unittest.main()
