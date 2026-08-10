from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "chinese-metaphysics"
VERSION = "0.8.4"
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
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

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

    def test_reading_skills_separate_reader_reports_from_evidence_artifacts(self) -> None:
        """Reader reports stay human-first; machine audit trails are separate files."""
        for skill, reader_name, evidence_name in (
            ("bazi-reading", "bazi_reading_<name>.md", "bazi_reading_evidence_<name>.md"),
            (
                "bazi-compatibility-reading",
                "bazi_compatibility_reading_<name-a>_<name-b>.md",
                "bazi_compatibility_evidence_<name-a>_<name-b>.md",
            ),
        ):
            with self.subTest(skill=skill):
                skill_root = PLUGIN / "skills" / skill
                instruction = (skill_root / "SKILL.md").read_text(encoding="utf-8")
                template = (skill_root / "references" / "output-template.md").read_text(encoding="utf-8")

                self.assertIn(reader_name, instruction)
                self.assertIn(evidence_name, instruction)
                self.assertIn("separate evidence artifact", instruction.lower())
                self.assertIn("Model data card", template)
                self.assertNotIn(chr(0x3014), template)

    def test_reader_templates_require_substantive_narrative_depth(self) -> None:
        """A reader report is a full interpretation, not a bare executive summary."""
        presentation = (PLUGIN / "shared" / "report-presentation.md").read_text(encoding="utf-8")
        natal_template = (PLUGIN / "skills" / "bazi-reading" / "references" / "output-template.md").read_text(
            encoding="utf-8"
        )
        compatibility_template = (
            PLUGIN / "skills" / "bazi-compatibility-reading" / "references" / "output-template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Minimum narrative depth", presentation)
        self.assertIn(f"1,400{chr(0x2013)}1,900 Chinese characters", presentation)
        self.assertIn("two or three paragraphs", natal_template)
        self.assertIn("two or three paragraphs", compatibility_template)


if __name__ == "__main__":
    unittest.main()
