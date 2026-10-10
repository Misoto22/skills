"""The github-account skills and everything they generate are English: no CJK text may ship in it.

The Chinese reader document and i18n entry are the repository's translations for
the website, outside the skill directory, and are not covered here.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from star_lists_skill import fakes
from star_lists_skill.fakes import ROOT, account

lists_plan = fakes.load("lists_plan")
lists_review = fakes.load("lists_review")


COVERED = (
    ROOT / "plugins" / "github-account",
    ROOT / "reader" / "star-lists" / "en.md",
    ROOT / "reader" / "star-prune" / "en.md",
    ROOT / "evals" / "star-lists",
    ROOT / "evals" / "star-prune",
    ROOT / "tests" / "star_lists_skill",
    ROOT / "tests" / "star_prune_skill",
)


def files() -> list[Path]:
    found = []
    for root in COVERED:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        found += [path for path in paths if path.is_file() and "__pycache__" not in path.parts]
    return found


class EnglishOnlyTests(unittest.TestCase):
    def test_skill_files_contain_no_cjk(self) -> None:
        offenders = []
        for path in files():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if lists_plan.has_cjk(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(offenders, [])

    def test_generated_review_page_is_english_apart_from_repository_data(self) -> None:
        plan = lists_plan.snapshot_to_plan(account())
        page = lists_review.render(plan)
        self.assertFalse(lists_plan.has_cjk(page))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            self.assertFalse(lists_plan.has_cjk(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
