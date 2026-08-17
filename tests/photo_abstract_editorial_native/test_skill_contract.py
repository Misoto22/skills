from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "plugins" / "photography" / "skills" / "photo-abstract-editorial-native"
SKILL_PATH = SKILL_DIR / "SKILL.md"
CONTRACT_PATH = SKILL_DIR / "references" / "composition-contract.md"


class SkillContractTests(unittest.TestCase):
    def test_examples_and_sections_describe_the_proportion_safe_layout(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        contract = CONTRACT_PATH.read_text(encoding="utf-8")

        for heading in (
            "## 1. Establish the two inputs",
            "## 2. Compose without distortion",
            "## 3. Audit before delivery",
            "## 4. Visual examples",
            "## 5. Attribution and scope",
        ):
            self.assertIn(heading, skill)
        self.assertEqual(skill.count('(assets/examples/'), 3)
        self.assertIn("Portrait side-by-side exception", contract)
        self.assertIn("source on the left", contract)
        self.assertIn("lower-art on the right", contract)


if __name__ == "__main__":
    unittest.main()
