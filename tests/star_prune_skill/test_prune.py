"""prune: scan, apply with a backup, restore, and the exit codes an agent branches on."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from star_lists_skill.fakes import FakeGitHub

from star_prune_skill.helpers import NOW, account, load

prune = load("prune")


class PruneCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.github = FakeGitHub(account())
        patcher = mock.patch.object(prune, "_now", return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = prune.main(list(argv), github=self.github)
        finally:
            os.chdir(cwd)
        return code, out.getvalue(), err.getvalue()

    def scanned(self) -> dict:
        code, out, _ = self.run_cli("scan", "--out", "prune.json")
        self.assertEqual(code, 0, out)
        return json.loads((self.dir / "prune.json").read_text())

    def test_scan_writes_candidates_and_a_summary(self) -> None:
        code, out, _ = self.run_cli("scan", "--out", "prune.json")
        self.assertEqual(code, 0)
        self.assertIn("6 of 8 starred repositories flagged", out)
        self.assertIn("Proposed: unstar 4, keep 2.", out)
        document = json.loads((self.dir / "prune.json").read_text())
        self.assertEqual(document["format"], "github-star-prune/v1")
        self.assertEqual(document["account"], "octo")

    def test_apply_without_yes_writes_nothing(self) -> None:
        self.scanned()
        code, out, _ = self.run_cli("apply", "prune.json")
        self.assertEqual(code, prune.EXIT_NEEDS_CONFIRMATION)
        self.assertIn("4 repositories to unstar", out)
        self.assertEqual(self.github.calls, [])

    def test_apply_backs_up_unstars_and_restore_puts_everything_back(self) -> None:
        self.scanned()
        code, out, _ = self.run_cli("apply", "prune.json", "--yes")
        self.assertEqual(code, 0, out)
        self.assertIn("Unstarred and verified: 4 repositories", out)
        starred = {star["name"] for star in self.github.snapshot()["stars"]}
        self.assertNotIn("old/archived", starred)
        self.assertIn("quiet/lib", starred)
        backup = next((self.dir / "star-prune-backups").glob("*.json"))
        saved = json.loads(backup.read_text())
        entry = next(repo for repo in saved["repos"] if repo["name"] == "old/archived")
        self.assertEqual(sorted(item["name"] for item in entry["lists"]), ["Old", "Tools"])
        code, out, _ = self.run_cli("restore", str(backup), "--yes")
        self.assertEqual(code, 0, out)
        after = self.github.snapshot()
        self.assertIn("old/archived", {star["name"] for star in after["stars"]})
        self.assertIn("old/archived", next(i for i in after["lists"] if i["id"] == "L2")["items"])

    def test_keep_overrides_the_proposal(self) -> None:
        document = self.scanned()
        for candidate in document["candidates"]:
            candidate["action"] = "keep"
        (self.dir / "prune.json").write_text(json.dumps(document))
        code, out, _ = self.run_cli("apply", "prune.json", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("Nothing to unstar", out)
        self.assertEqual(self.github.calls, [])

    def test_unknown_action_and_wrong_account_are_refused(self) -> None:
        document = self.scanned()
        document["candidates"][0]["action"] = "delete"
        (self.dir / "prune.json").write_text(json.dumps(document))
        code, _, err = self.run_cli("apply", "prune.json", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("action must be one of unstar, keep", err)
        document["account"] = "someone"
        (self.dir / "prune.json").write_text(json.dumps(document))
        self.assertIn("gh is signed in as 'octo'", self.run_cli("apply", "prune.json")[2])

    def test_restore_skips_lists_that_no_longer_exist(self) -> None:
        self.scanned()
        self.run_cli("apply", "prune.json", "--yes")
        backup = next((self.dir / "star-prune-backups").glob("*.json"))
        self.github.delete_list("L2")
        code, out, _ = self.run_cli("restore", str(backup))
        self.assertEqual(code, prune.EXIT_NEEDS_CONFIRMATION)
        self.assertIn("list no longer exists, skipped: Old", out)
        self.assertEqual(self.run_cli("restore", str(backup), "--yes")[0], 0)

    def test_generated_files_are_english(self) -> None:
        state = account()
        state["stars"][1]["description"] = chr(0x5DE5) + chr(0x5177)
        self.github = FakeGitHub(state)
        self.scanned()
        self.run_cli("apply", "prune.json", "--yes")
        lists_plan = load("lists_plan")
        for path in self.dir.rglob("*.json"):
            self.assertFalse(lists_plan.has_cjk(path.read_text()), path.name)


if __name__ == "__main__":
    unittest.main()
