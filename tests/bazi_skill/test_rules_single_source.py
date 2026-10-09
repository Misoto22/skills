"""Hold each BaZi rule table to the one rules file that declares it.

The compatibility rules repeated the chart rules' stem and branch relations, and
both the scoring and compatibility rules repeated the five-element tables. The
copies agreed, so every comparison passed — until a lineage edit to a clash or
a combination landed in one file and the chart and the comparison began
disagreeing about the same pair of branches, with nothing comparing them.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
RULES = SHARED / "rules"
sys.path.insert(0, str(SHARED))

from bazi import compatibility, validation
from bazi.rules import ELEMENT_TABLES, element_tables, scoring_rules

DECLARED = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(RULES.glob("*.json"))}
CHART = DECLARED["chart-v1.json"]
CHART_TABLES = element_tables()
# Keys the chart rules own; any other rules file carrying one holds a copy.
CHART_OWNED = (*ELEMENT_TABLES, "relations")
RETIRED_COPIES = (
    "stem_combinations",
    "branch_combinations",
    "branch_clashes",
    "branch_harms",
    "branch_breaks",
)


class RulesFilesTests(unittest.TestCase):
    def test_the_chart_rules_declare_every_shared_table(self) -> None:
        for key in CHART_OWNED:
            with self.subTest(key=key):
                self.assertIn(key, CHART)

    def test_no_other_rules_file_repeats_a_chart_table(self) -> None:
        for name, rules in DECLARED.items():
            if name == "chart-v1.json":
                continue
            for key in (*CHART_OWNED, *RETIRED_COPIES):
                with self.subTest(rules=name, key=key):
                    self.assertNotIn(key, rules)

    def test_the_element_order_is_the_production_cycle(self) -> None:
        """The order every distribution is reported in, so it is checked, not assumed."""

        elements = CHART["elements"]
        self.assertEqual(len(elements), 5)
        for current, following in zip(elements, [*elements[1:], elements[0]], strict=True):
            with self.subTest(element=current):
                self.assertEqual(CHART["element_produces"][current], following)


class ComposedRulesTests(unittest.TestCase):
    def test_scoring_reads_the_chart_element_tables(self) -> None:
        composed = scoring_rules()
        for key in ELEMENT_TABLES:
            with self.subTest(key=key):
                self.assertIs(composed[key], CHART_TABLES[key])
        self.assertEqual(composed["model_id"], DECLARED["scoring-v1.json"]["model_id"])

    def test_compatibility_scores_the_chart_relations(self) -> None:
        rules = compatibility._rules()
        relations = CHART["relations"]
        expected = {
            "stem_combination": [item["members"] for item in relations["stem_combination"]],
            "branch_combination": [item["members"] for item in relations["branch_six_combination"]],
            "branch_clash": relations["branch_clash"],
            "branch_harm": relations["branch_harm"],
            "branch_break": relations["branch_break"],
        }
        self.assertEqual(rules["relation_pairs"], expected)
        self.assertEqual(rules["model_id"], DECLARED["compatibility-v1.json"]["model_id"])
        for key in ELEMENT_TABLES:
            with self.subTest(key=key):
                self.assertIs(rules[key], CHART_TABLES[key])

    def test_every_scored_relation_has_an_adjustment(self) -> None:
        """A relation read from the chart with no weight here would score as a KeyError."""

        rules = compatibility._rules()
        self.assertEqual(set(rules["relation_pairs"]), set(rules["interaction_adjustments"]))


class DimensionsTests(unittest.TestCase):
    def test_the_validator_derives_its_dimensions_from_the_weights(self) -> None:
        weights = DECLARED["compatibility-v1.json"]["general_weights"]
        self.assertEqual(validation.GENERAL_DIMENSIONS, tuple(weights))

    def test_every_profile_weights_the_same_dimensions(self) -> None:
        dimensions = set(validation.GENERAL_DIMENSIONS)
        for name, profile in DECLARED["compatibility-v1.json"]["relationship_profiles"].items():
            with self.subTest(profile=name):
                self.assertEqual(set(profile), dimensions)
                self.assertEqual(sum(profile.values()), 100)

    def test_the_validator_does_not_restate_the_dimensions(self) -> None:
        source = (SHARED / "bazi" / "validation.py").read_text(encoding="utf-8")
        for dimension in validation.GENERAL_DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.assertNotIn(f'"{dimension}"', source)


class ProseTests(unittest.TestCase):
    """The rules file is what an agent quotes; a table copied into prose is a second source."""

    PLUGIN = ROOT / "plugins" / "chinese-metaphysics"
    SKILL = PLUGIN / "skills" / "bazi-compatibility" / "SKILL.md"

    def published_prose(self) -> list[Path]:
        skills = self.PLUGIN / "skills"
        own = sorted(path for path in skills.rglob("*.md") if "shared" not in path.relative_to(skills).parts)
        return sorted(SHARED.rglob("*.md")) + own

    def test_the_skill_points_at_the_rules_file_it_resolves(self) -> None:
        text = self.SKILL.read_text(encoding="utf-8")
        reference = "shared/rules/compatibility-v1.json"
        self.assertIn(reference, text)
        self.assertTrue((self.SKILL.parent / reference).is_file(), "the pointer must resolve from the skill")

    def test_no_prose_restates_a_compatibility_weight(self) -> None:
        rules = DECLARED["compatibility-v1.json"]
        weights = set(rules["general_weights"].values())
        for profile in rules["relationship_profiles"].values():
            weights |= set(profile.values())
        pattern = r"\b(?:" + "|".join(str(value) for value in sorted(weights)) + r")\s?%"
        for path in self.published_prose():
            with self.subTest(file=str(path.relative_to(self.PLUGIN))):
                self.assertNotRegex(path.read_text(encoding="utf-8"), pattern)

    def test_the_retired_method_notes_stay_retired(self) -> None:
        """They restated weights, multipliers and thresholds, and nothing read them."""

        for name in ("compatibility-method.md", "scoring-method.md"):
            with self.subTest(note=name):
                self.assertEqual(list(self.PLUGIN.rglob(name)), [])


if __name__ == "__main__":
    unittest.main()
