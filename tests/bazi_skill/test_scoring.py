from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
CHART_RULES = json.loads((SHARED / "rules" / "chart-v1.json").read_text(encoding="utf-8"))
SCORING_RULES = json.loads((SHARED / "rules" / "scoring-v1.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(SHARED))

from bazi.pillars import FourPillars, Pillar
from bazi.relations import derive_chart_facts
from bazi.scoring import score_chart


def chart(*texts: str) -> FourPillars:
    return FourPillars(
        *(Pillar.from_text(text) for text in texts),
        year_boundary_utc=None,
        month_boundary_name="test",
        month_boundary_utc=None,
        day_boundary="23:00",
    )


def score(pillars: FourPillars) -> dict:
    return score_chart(pillars, derive_chart_facts(pillars, CHART_RULES), SCORING_RULES)


class ScoringTests(unittest.TestCase):
    def test_distributions_sum_to_one_hundred(self) -> None:
        result = score(chart("甲子", "丙寅", "戊辰", "庚申"))

        for key in ("base_distribution", "adjusted_distribution"):
            self.assertAlmostEqual(sum(result[key].values()), 100.0, delta=0.01)
            self.assertTrue(all(0.0 <= value <= 100.0 for value in result[key].values()))

    def test_every_visible_and_hidden_contribution_precedes_normalization(self) -> None:
        result = score(chart("甲子", "丙寅", "戊辰", "庚申"))
        ids = {item["id"] for item in result["ledger"]}

        for position in ("year", "month", "day", "hour"):
            self.assertIn(f"base.visible.{position}", ids)
            hidden_count = len(CHART_RULES["hidden_stems"][result["pillars"][position]["branch"]])
            for index in range(hidden_count):
                self.assertIn(f"base.hidden.{position}.{index}", ids)

    def test_strength_is_bounded_and_each_component_is_named(self) -> None:
        result = score(chart("壬子", "壬子", "壬子", "庚子"))

        strength = result["day_master_strength"]
        self.assertGreaterEqual(strength["score"], 0.0)
        self.assertLessEqual(strength["score"], 100.0)
        self.assertEqual(
            {item["component"] for item in strength["ledger"]},
            {
                "base",
                "seasonal",
                "root",
                "visible_support",
                "control",
                "production",
                "drainage",
                "structural",
            },
        )

    def test_changing_one_root_changes_the_documented_root_entry(self) -> None:
        rooted = score(chart("甲子", "丙寅", "壬子", "庚子"))
        unrooted = score(chart("甲子", "丙寅", "壬子", "庚午"))

        def root_hour(result: dict) -> float:
            root = next(
                item
                for item in result["day_master_strength"]["details"]
                if item["id"] == "strength.root.hour"
            )
            return root["amount"]

        self.assertGreater(root_hour(rooted), root_hour(unrooted))

    def test_candidate_transformations_contribute_nothing(self) -> None:
        candidate = score(chart("甲申", "丙子", "戊辰", "庚戌"))
        entries = [item for item in candidate["ledger"] if item["id"].startswith("adjust.transform")]

        self.assertTrue(entries)
        self.assertTrue(all(item["applied"] is False and item["amount"] == 0.0 for item in entries))

    def test_numeric_strength_never_declares_a_following_structure(self) -> None:
        result = score(chart("壬子", "壬子", "壬子", "庚子"))

        self.assertGreater(result["day_master_strength"]["score"], 65.0)
        self.assertEqual(result["special_structure"]["status"], "not_established")
        self.assertIn("prerequisite", result["special_structure"]["reason"])

    def test_model_identity_and_confidence_are_explicit(self) -> None:
        result = score(chart("甲子", "丙寅", "戊辰", "庚申"))
        self.assertEqual(result["model_version"], "bazi-score-v1")
        self.assertIn(result["confidence"]["level"], {"high", "medium", "low"})
        self.assertIn("heuristic", result["score_semantics"])


if __name__ == "__main__":
    unittest.main()
