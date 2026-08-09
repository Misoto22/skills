from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
READER_SKILL = SKILL / "SKILL.md"
TEMPLATE = SKILL / "references" / "output-template.md"
EDITORIAL = SKILL / "references" / "editorial-policy.md"
EXAMPLES = SKILL / "references" / "examples.md"
OPENAI = SKILL / "agents" / "openai.yaml"

UNIVERSAL_HEADINGS = (
    "Basis, provenance, and limitations",
    "Repeated interaction patterns",
    "Reciprocity and asymmetry",
    "Communication and coordination",
    "Tension, boundaries, and repair",
    "Growth and shared direction",
    "Requested or context-specific domains",
    "Overall synthesis",
    "Evidence index",
)


class ReaderSkillContractTests(unittest.TestCase):
    def test_frontmatter_names_the_skill_and_body_stays_short(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: synastry-reading\n")
        self.assertLess(len(text.splitlines()), 500)

    def test_reader_uses_universal_core_and_conditional_domains(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")
        self.assertIn("validate_synastry.py", text)
        self.assertIn("validate_reading.py", text)
        self.assertIn("explicit relationship context", text)
        self.assertNotIn("Use every fixed core heading", text)

    def test_reader_refuses_txt_and_finalizes_only_validated_markdown(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        for required in ("JSON v2", "draft", "synastry_reading_<chart-id>.md", "atomically"):
            self.assertIn(required, text)
        self.assertRegex(text, r"(?i)TXT[^\n]+(?:refus|recalculat|not supported)")
        self.assertIn("untrusted data", text)

    def test_template_has_exact_universal_order_and_conditional_modules(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        for heading in UNIVERSAL_HEADINGS:
            self.assertIn(f"## {heading}", text)
        positions = [text.index(f"## {heading}") for heading in UNIVERSAL_HEADINGS]

        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("## Attraction, romance, and intimacy", text)
        for module in (
            "Romance and intimacy",
            "Friendship and community",
            "Family and care",
            "Work and creative collaboration",
            "Money and shared resources",
        ):
            self.assertIn(module, text)

    def test_progressive_references_cover_editorial_and_adversarial_cases(self) -> None:
        skill = READER_SKILL.read_text(encoding="utf-8")
        self.assertTrue(EDITORIAL.is_file(), "editorial policy reference is missing")
        editorial = EDITORIAL.read_text(encoding="utf-8")
        examples = EXAMPLES.read_text(encoding="utf-8")

        for path in (
            "references/output-template.md",
            "references/editorial-policy.md",
            "references/examples.md",
        ):
            self.assertIn(path, skill)
        for required in ("editorial-v1", "independent", "conditional", "confirmed", "possible"):
            self.assertIn(required, editorial)
        for required in ("neutral", "romantic", "weak", "adversarial", "TXT"):
            self.assertIn(required, examples)

    def test_metadata_matches_validated_json_v2_workflow(self) -> None:
        text = OPENAI.read_text(encoding="utf-8")

        self.assertIn("$synastry-reading", text)
        self.assertIn("JSON v2", text)
        self.assertIn("evidence", text)


if __name__ == "__main__":
    unittest.main()
