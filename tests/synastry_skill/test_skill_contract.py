from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
SKILL_PATH = SKILL / "SKILL.md"
EXAMPLE_PATH = SKILL / "references" / "request.example.json"
sys.path.insert(0, str(SKILL / "scripts"))

from compute_synastry import HOUSE_SYSTEMS, REQUIRED_FIELDS

# A birth date sitting in the skill rather than arriving in a request means
# somebody's chart was hard-coded again, which is what this import removed. The
# documentation needs example dates, so those two are named rather than guessed
# at by pattern — anything else matching is a real person's data.
BIRTH_DATE = re.compile(r"\b(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b")
DOCUMENTED_EXAMPLES = {"1990-03-14", "1988-11-02"}
SKILL_SOURCES = (
    SKILL_PATH,
    EXAMPLE_PATH,
    SKILL / "references" / "examples.md",
    SKILL / "agents" / "openai.yaml",
    *sorted((SKILL / "scripts").glob("*.py")),
)


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_names_the_skill_and_the_body_stays_short(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: synastry\n")
        self.assertIn('version: "0.8.2"', text)
        self.assertLess(len(text.splitlines()), 500)

    def test_the_precondition_and_the_refusal_are_both_written_down(self) -> None:
        """The skill is only as good as its refusal: an assumed birth time is a wrong chart."""

        text = SKILL_PATH.read_text(encoding="utf-8")

        for phrase in ("to the minute", "Do not substitute noon", "Ascendant"):
            self.assertIn(phrase, text)

    def test_every_documented_flag_exists_on_the_script(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        script = (SKILL / "scripts" / "compute_synastry.py").read_text(encoding="utf-8")

        for flag in (
            "--request",
            "--json",
            "--out",
            "--language",
            "--major-orb",
            "--minor-orb",
            "--house-system",
            "--ephemeris-path",
        ):
            self.assertIn(flag, text, flag)
            self.assertIn(f'"{flag}"', script, flag)
        for system in HOUSE_SYSTEMS:
            self.assertIn(system, text, system)

    def test_the_worked_examples_cover_the_refusal_and_the_degraded_run(self) -> None:
        """The two cases a reader gets wrong are the ones that produce no full chart."""

        examples = (SKILL / "references" / "examples.md").read_text(encoding="utf-8")

        self.assertIn("references/examples.md", SKILL_PATH.read_text(encoding="utf-8"))
        self.assertIn("--language zh", examples)
        self.assertIn("to the minute", examples)
        self.assertIn("未能解析", examples)

    def test_the_linked_example_matches_the_documented_fields(self) -> None:
        self.assertIn("references/request.example.json", SKILL_PATH.read_text(encoding="utf-8"))
        payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(payload["people"]), 2)
        for person in payload["people"]:
            for field in REQUIRED_FIELDS:
                self.assertIn(field, person, field)

    def test_the_skill_carries_nobody_s_birth_data(self) -> None:
        """The point of the import: a reference chart is an input, never a constant."""

        for path in SKILL_SOURCES:
            text = path.read_text(encoding="utf-8")
            dates = {match.group(0) for match in BIRTH_DATE.finditer(text)}
            self.assertLessEqual(dates, DOCUMENTED_EXAMPLES, f"{path.name} carries an undocumented date")
            self.assertNotIn("laoban", text.lower(), path.name)
            self.assertNotIn("老板", text, path.name)

        # The scripts have no reason to name a date at all: every one they see
        # arrives in a request.
        for script in sorted((SKILL / "scripts").glob("*.py")):
            self.assertIsNone(BIRTH_DATE.search(script.read_text(encoding="utf-8")), script.name)

    def test_neither_person_is_privileged_by_the_interface(self) -> None:
        script = (SKILL / "scripts" / "compute_synastry.py").read_text(encoding="utf-8")

        self.assertIn("exactly two people", script)
        # A default person, or a natal file shipped beside the skill, is the shape
        # the original had. Either one puts somebody's chart in the repository.
        self.assertFalse(list((SKILL / "references").glob("*natal*")))
        self.assertNotIn("DEFAULT_PERSON", script)

    def test_the_ephemeris_import_stays_inside_the_backend(self) -> None:
        """Request parsing and rendering must import on a machine with no ephemeris."""

        script = (SKILL / "scripts" / "compute_synastry.py").read_text(encoding="utf-8")
        before_backend = script.split("def swiss_ephemeris", 1)[0]

        self.assertIn("import swisseph", script)
        self.assertNotIn("import swisseph", before_backend)
        for module in ("astro_math.py", "report.py"):
            self.assertNotIn("swisseph", (SKILL / "scripts" / module).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
