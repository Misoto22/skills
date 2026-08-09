from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
CALCULATOR_SKILL = SKILL / "SKILL.md"
EXAMPLES = SKILL / "references" / "examples.md"
CONVENTIONS = SKILL / "references" / "calculation-conventions.md"
REQUEST_EXAMPLE = SKILL / "references" / "request.example.json"
OPENAI = SKILL / "agents" / "openai.yaml"
sys.path.insert(0, str(SKILL / "scripts"))

from request_schema import parse_request  # type: ignore[import-not-found]


class CalculatorSkillContractTests(unittest.TestCase):
    def test_frontmatter_names_the_skill_and_body_stays_short(self) -> None:
        text = CALCULATOR_SKILL.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: synastry\n")
        self.assertIn('version: "0.8.1"', text)
        self.assertLess(len(text.splitlines()), 500)

    def test_calculator_is_json_only_and_has_no_fixed_identity(self) -> None:
        text = CALCULATOR_SKILL.read_text(encoding="utf-8")
        for required in ("schema_version", "exact", "window", "date-only", "swiss-only"):
            self.assertIn(required, text)
        for forbidden in ("synastry_*.txt", "老板", "Shanghai", "residence"):
            self.assertNotIn(forbidden, text)

    def test_body_documents_only_the_authoritative_cli_flags(self) -> None:
        text = CALCULATOR_SKILL.read_text(encoding="utf-8")
        script = (SKILL / "scripts" / "compute_synastry.py").read_text(encoding="utf-8")

        for flag in ("--request", "--json", "--out", "--ephemeris-path", "--overwrite"):
            self.assertIn(flag, text)
            self.assertIn(f'"{flag}"', script)
        for stale_flag in ("--language", "--house-system", "--major-orb", "--minor-orb"):
            self.assertNotIn(stale_flag, text)

    def test_request_example_is_strict_v2_and_parses(self) -> None:
        payload = json.loads(REQUEST_EXAMPLE.read_text(encoding="utf-8"))

        request = parse_request(payload)

        self.assertEqual(payload["schema_version"], "2.0")
        self.assertEqual(len(request.people), 2)
        self.assertEqual(request.options.ephemeris_policy, "swiss-only")
        self.assertEqual({person.birth.mode for person in request.people}, {"exact", "date-only"})

    def test_progressive_references_cover_fragile_cases(self) -> None:
        skill = CALCULATOR_SKILL.read_text(encoding="utf-8")
        self.assertTrue(CONVENTIONS.is_file(), "calculation conventions reference is missing")
        conventions = CONVENTIONS.read_text(encoding="utf-8")
        examples = EXAMPLES.read_text(encoding="utf-8")

        for path in (
            "references/request.example.json",
            "references/calculation-conventions.md",
            "references/examples.md",
        ):
            self.assertIn(path, skill)
        self.assertIn("## Contents", conventions)
        for required in ("western-tropical-v1", "ptolemaic-minor-v1", "classical-derived-v1"):
            self.assertIn(required, conventions)
        for required in ("exact", "date-only", "ambiguous", "swiss-only"):
            self.assertIn(required, examples)

    def test_metadata_matches_json_v2_uncertainty_workflow(self) -> None:
        text = OPENAI.read_text(encoding="utf-8")

        self.assertIn("$synastry", text)
        self.assertIn("JSON v2", text)
        self.assertIn("uncertainty", text)


if __name__ == "__main__":
    unittest.main()
