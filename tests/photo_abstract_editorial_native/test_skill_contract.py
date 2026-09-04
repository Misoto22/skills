from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "plugins" / "photography" / "skills" / "photo-abstract-editorial-native"
SKILL_PATH = SKILL_DIR / "SKILL.md"
CONTRACT_PATH = SKILL_DIR / "references" / "composition-contract.md"
EXAMPLES_DIR = SKILL_DIR / "assets" / "examples"
READER_DIR = ROOT / "reader" / "photo-abstract-editorial-native"

EXAMPLES = (
    "whale-native-board.jpg",
    "harbour-bridge-native-board.jpg",
    "portrait-native-board.jpg",
)

# The examples carry proportion, not detail. The evaluation runner drops binaries
# from a prompt and the agent never renders one, so every byte above this is paid
# for by whoever clones or packages the skill and read by nobody.
EXAMPLE_BUDGET = 300 * 1024


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
        self.assertIn("Portrait side-by-side exception", contract)
        self.assertIn("source on the left", contract)
        self.assertIn("lower-art on the right", contract)

    def test_step_two_runs_the_composer_rather_than_describing_it(self) -> None:
        """The geometry is a script; the step that lays a board out has to say so."""

        skill = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("python3 scripts/compose_board.py", skill)
        self.assertIn("--source-class", skill)
        self.assertTrue((SKILL_DIR / "scripts" / "compose_board.py").is_file())

    def test_the_skill_declares_the_dependency_its_script_needs(self) -> None:
        requirements = SKILL_DIR / "requirements.txt"

        self.assertTrue(requirements.is_file(), "compose_board.py imports Pillow undeclared")
        self.assertIn("pillow", requirements.read_text(encoding="utf-8").lower())

    def test_the_gallery_is_published_to_readers_not_embedded_in_the_instructions(self) -> None:
        """The runner strips binaries, so an embedded gallery is weight with no reader."""

        skill = SKILL_PATH.read_text(encoding="utf-8")
        self.assertEqual(skill.count("(assets/examples/"), 0)

        for locale in ("en", "zh"):
            document = (READER_DIR / f"{locale}.md").read_text(encoding="utf-8")
            for example in EXAMPLES:
                with self.subTest(locale=locale, example=example):
                    self.assertIn(example, document)

    def test_every_example_stays_inside_the_size_budget(self) -> None:
        for example in EXAMPLES:
            path = EXAMPLES_DIR / example
            with self.subTest(example=example):
                self.assertTrue(path.is_file())
                self.assertLessEqual(
                    path.stat().st_size,
                    EXAMPLE_BUDGET,
                    f"{example} is {path.stat().st_size / 1024:.0f}K;"
                    f" the budget is {EXAMPLE_BUDGET / 1024:.0f}K",
                )


if __name__ == "__main__":
    unittest.main()
