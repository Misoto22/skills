"""The nine types live in the hook and in SKILL.md, and this holds the two copies together.

The hook injects the vocabulary into every new session; SKILL.md carries it for the
batch that renames existing ones. Two readers, two copies — so the copy nobody ran
would drift the day a type was renamed, and every new session would be named from a
set the batch no longer recognised.
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "dev" / "skills" / "retitle"
HOOK = SKILL / "assets" / "session-naming-hook.py"


def _schemes() -> dict[str, dict[str, str]]:
    spec = importlib.util.spec_from_file_location("session_naming_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.SCHEMES


class TypesSingleSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.schemes = _schemes()

    def test_the_english_table_lists_exactly_the_hook_types_in_order(self) -> None:
        rows = re.findall(r"^\| ([A-Z]{4,5}) \| ", self.skill, flags=re.MULTILINE)
        rows = [row for row in rows if row != "TYPE"]  # the header cell, not a type
        self.assertEqual(rows, self.schemes["en"]["types"].split(", "))

    def test_the_chinese_list_matches_the_hook_in_order(self) -> None:
        expected = self.schemes["zh"]["types"]
        self.assertIn(expected, self.skill)
        listed = re.search(r"^((?:[一-鿿]{2}, ){8}[一-鿿]{2})", self.skill, flags=re.MULTILINE)
        self.assertIsNotNone(listed)
        self.assertEqual(listed.group(1), expected)

    def test_both_vocabularies_hold_nine(self) -> None:
        for lang, scheme in self.schemes.items():
            with self.subTest(lang=lang):
                self.assertEqual(len(scheme["types"].split(", ")), 9)


if __name__ == "__main__":
    unittest.main()
