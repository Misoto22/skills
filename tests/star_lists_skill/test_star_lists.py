"""star_lists and lists_review: the command line a person or agent drives."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from star_lists_skill import fakes
from star_lists_skill.fakes import FakeGitHub

lists_plan = fakes.load("lists_plan")
lists_review = fakes.load("lists_review")
star_lists = fakes.load("star_lists")


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.github = FakeGitHub()

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = star_lists.main(list(argv), github=self.github)
        finally:
            os.chdir(cwd)
        return code, out.getvalue(), err.getvalue()

    def exported_plan(self) -> Path:
        code, out, _ = self.run_cli("export", "--out", "plan.json")
        self.assertEqual(code, 0, out)
        return self.dir / "plan.json"

    def test_export_reports_counts(self) -> None:
        code, out, _ = self.run_cli("export", "--out", "plan.json")
        self.assertEqual(code, 0)
        self.assertIn("3 starred repositories, 2 lists, 1 repositories in no list", out)
        self.assertEqual(json.loads((self.dir / "plan.json").read_text())["account"], "octo")

    def test_check_fails_on_an_unassigned_repository(self) -> None:
        self.exported_plan()
        code, _, err = self.run_cli("check", "plan.json")
        self.assertEqual(code, 1)
        self.assertIn("c/notes: starred but in no list", err)
        self.assertEqual(self.run_cli("check", "plan.json", "--allow-unassigned")[0], 0)

    def test_apply_without_yes_writes_nothing(self) -> None:
        path = self.exported_plan()
        plan = json.loads(path.read_text())
        plan["assignments"]["c/notes"] = ["tools"]
        path.write_text(json.dumps(plan))
        code, out, _ = self.run_cli("apply", "plan.json")
        self.assertEqual(code, star_lists.EXIT_NEEDS_CONFIRMATION)
        self.assertIn("Nothing was written", out)
        self.assertEqual(self.github.calls, [])
        self.assertFalse((self.dir / "star-lists-backups").exists())

    def test_apply_backs_up_applies_and_verifies(self) -> None:
        path = self.exported_plan()
        plan = json.loads(path.read_text())
        plan["lists"].append({"key": "notes", "name": "Notes", "description": "", "private": False})
        plan["assignments"]["c/notes"] = ["notes"]
        path.write_text(json.dumps(plan))
        code, out, _ = self.run_cli("apply", "plan.json", "--yes")
        self.assertEqual(code, 0, out)
        self.assertIn("Applied and verified", out)
        backups = list((self.dir / "star-lists-backups").glob("star-lists-octo-*.json"))
        self.assertEqual(len(backups), 1)
        backup = lists_plan.load(json.loads(backups[0].read_text()))
        self.assertEqual(backup["assignments"]["c/notes"], [])
        code, out, _ = self.run_cli("apply", str(backups[0]), "--yes", "--allow-unassigned")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Notes", [item["name"] for item in self.github.snapshot()["lists"]])

    def test_unreadable_plan_is_a_clean_error(self) -> None:
        (self.dir / "broken.json").write_text("{not json")
        code, _, err = self.run_cli("diff", "broken.json")
        self.assertEqual(code, 1)
        self.assertIn("cannot read broken.json", err)

    def test_review_page_embeds_the_plan_safely(self) -> None:
        path = self.exported_plan()
        plan = json.loads(path.read_text())
        plan["repos"]["a/agent"]["description"] = "</script><b>x</b>"
        path.write_text(json.dumps(plan))
        code, _, _ = self.run_cli("review", "plan.json")
        self.assertEqual(code, 0)
        page = (self.dir / "plan.html").read_text()
        self.assertNotIn(lists_review.PLACEHOLDER, page)
        self.assertNotIn("</script><b>", page)
        self.assertIn('"account": "octo"', page)


if __name__ == "__main__":
    unittest.main()
