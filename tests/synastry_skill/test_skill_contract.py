from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "astrology"
SKILL = PLUGIN / "skills" / "synastry"
CALCULATOR_SKILL = SKILL / "SKILL.md"
READER = PLUGIN / "skills" / "synastry-reading"
READER_SKILL = READER / "SKILL.md"
EXAMPLES = SKILL / "references" / "examples.md"
CONVENTIONS = SKILL / "references" / "calculation-conventions.md"
REQUEST_EXAMPLE = SKILL / "references" / "request.example.json"
OPENAI = SKILL / "agents" / "openai.yaml"
EVALS = ROOT / "evals" / "synastry" / "evals.json"
sys.path.insert(0, str(SKILL / "scripts"))

from astro.request_schema import parse_request  # type: ignore[import-not-found]


class CalculatorSkillContractTests(unittest.TestCase):
    def test_astrology_license_and_json_contract_are_published(self) -> None:
        for manifest in (PLUGIN / "plugin.json", PLUGIN / ".claude-plugin" / "plugin.json"):
            self.assertEqual(
                json.loads(manifest.read_text(encoding="utf-8"))["license"],
                "AGPL-3.0-or-later",
            )
        for skill in (SKILL, READER):
            frontmatter = skill.joinpath("SKILL.md").read_text(encoding="utf-8")
            self.assertIn("license: AGPL-3.0-or-later", frontmatter)
            self.assertTrue((skill / "shared" / "LICENSE").is_file())

        english_readme = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        chinese_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8").splitlines()
        skills_readme = (PLUGIN / "skills" / "README.md").read_text(encoding="utf-8").splitlines()
        english_entries = {
            skill: next(line for line in english_readme if f"**[{skill}]" in line)
            for skill in ("synastry", "synastry-reading")
        }
        chinese_entries = {
            skill: next(line for line in chinese_readme if f"**[{skill}]" in line)
            for skill in ("synastry", "synastry-reading")
        }
        skills_entries = {
            skill: next(line for line in skills_readme if line.startswith(f"- [{skill}]("))
            for skill in ("synastry", "synastry-reading")
        }
        groupings = json.loads((ROOT / "skills.sh.json").read_text(encoding="utf-8"))["groupings"]
        astrology_group = next(group for group in groupings if group["title"] == "Astrology")
        unreleased_entry = next(
            line
            for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
            if line.startswith("- **Breaking:** The `astrology` plugin")
        )
        publication_descriptions = (
            json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))["description"],
            json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))[
                "description"
            ],
            *english_entries.values(),
            *chinese_entries.values(),
            *skills_entries.values(),
            astrology_group["description"],
            unreleased_entry,
        )
        for description in publication_descriptions:
            self.assertIn("JSON", description)
            self.assertNotIn("minute-only", description)
            self.assertNotIn("raw TXT", description)
            self.assertNotIn("raw data file", description)
            self.assertNotIn("fixed relationship mechanisms", description)

        self.assertIn("default", english_entries["synastry"])
        self.assertIn("archival", english_entries["synastry"])
        self.assertIn("默认", chinese_entries["synastry"])
        self.assertIn("归档", chinese_entries["synastry"])
        self.assertIn("default", astrology_group["description"])
        self.assertIn("archival", astrology_group["description"])

        conventions = CONVENTIONS.read_text(encoding="utf-8")
        self.assertIn("## Licensing", conventions)
        self.assertIn("AGPL-3.0-or-later", conventions)
        self.assertIn("Swiss Ephemeris professional license", conventions)
        self.assertIn("Astrodienst", conventions)
        self.assertIn("not granted by this repository", conventions)

    def test_frontmatter_names_the_skill_and_body_stays_short(self) -> None:
        text = CALCULATOR_SKILL.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: synastry\n")
        self.assertIn('version: "0.13.1"', text)
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

    def test_request_example_has_only_neutral_required_subject_data(self) -> None:
        payload = json.loads(REQUEST_EXAMPLE.read_text(encoding="utf-8"))
        people = payload["people"]

        self.assertEqual([person["id"] for person in people], ["subject-1", "subject-2"])
        for person in people:
            self.assertTrue({"display_name", "pronouns"}.isdisjoint(person))
            self.assertTrue({"place_label", "location_source"}.isdisjoint(person["birth"]))
        exact_birth = people[0]["birth"]
        self.assertEqual(exact_birth["timezone"], "UTC")
        self.assertEqual((exact_birth["latitude"], exact_birth["longitude"]), (0.0, 0.0))
        self.assertEqual(
            payload["relationship_context"],
            {"description": "unspecified", "requested_domains": []},
        )

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

    def test_eval_categories_match_calculator_discovery_boundary(self) -> None:
        suite = json.loads(EVALS.read_text(encoding="utf-8"))
        non_trigger_ids = {case["id"] for case in suite["non_triggers"]}
        behavior_ids = {case["id"] for case in suite["behaviors"]}

        self.assertIn("legacy-txt-input-refusal", non_trigger_ids)
        self.assertNotIn("legacy-txt-input-refusal", behavior_ids)


if __name__ == "__main__":
    unittest.main()
