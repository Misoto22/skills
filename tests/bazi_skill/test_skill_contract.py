from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "chinese-metaphysics"
VERSION = "0.8.1"
SKILLS = {
    "bazi-chart": ("bazi_<name>.json", "bazi-reading"),
    "bazi-reading": ("bazi_reading_<name>.md", None),
    "bazi-compatibility": (
        "bazi_compatibility_<name-a>_<name-b>.json",
        "bazi-compatibility-reading",
    ),
    "bazi-compatibility-reading": (
        "bazi_compatibility_reading_<name-a>_<name-b>.md",
        None,
    ),
}
BIRTH_DATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")


class SkillContractTests(unittest.TestCase):
    def test_plugin_registers_exactly_the_four_approved_skills(self) -> None:
        manifest = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["name"], "chinese-metaphysics")
        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(
            manifest["skills"],
            [f"./skills/{name}" for name in sorted(SKILLS)],
        )

    def test_each_skill_declares_its_artifact_and_handoff_boundary(self) -> None:
        for name, (artifact, handoff) in SKILLS.items():
            with self.subTest(skill=name):
                text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertRegex(text, rf"\A---\nname: {re.escape(name)}\n")
                self.assertIn(f'version: "{VERSION}"', text)
                self.assertIn(artifact, text)
                if handoff:
                    self.assertIn(handoff, text)
                    self.assertIn("automatically", text.lower())
                self.assertLess(len(text.splitlines()), 500)

    def test_no_skill_hard_codes_personal_birth_data(self) -> None:
        for path in sorted((PLUGIN / "skills").rglob("*")):
            if path.is_file() and path.suffix in {".md", ".json", ".yaml", ".py"}:
                self.assertEqual(BIRTH_DATE.findall(path.read_text(encoding="utf-8")), [], str(path))


if __name__ == "__main__":
    unittest.main()
