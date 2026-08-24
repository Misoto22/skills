from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
RULES = SHARED / "rules" / "chart-v1.json"
sys.path.insert(0, str(SHARED))

from bazi.pillars import FourPillars, Pillar
from bazi.relations import derive_chart_facts, ten_god


def chart(*texts: str) -> FourPillars:
    return FourPillars(
        *(Pillar.from_text(text) for text in texts),
        year_boundary_utc=None,
        month_boundary_name="test",
        month_boundary_utc=None,
        day_boundary="23:00",
    )


class RelationRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = json.loads(RULES.read_text(encoding="utf-8"))

    def test_hidden_stems_are_complete_and_versioned(self) -> None:
        expected = {
            "子": ["癸"],
            "丑": ["己", "癸", "辛"],
            "寅": ["甲", "丙", "戊"],
            "卯": ["乙"],
            "辰": ["戊", "乙", "癸"],
            "巳": ["丙", "戊", "庚"],
            "午": ["丁", "己"],
            "未": ["己", "丁", "乙"],
            "申": ["庚", "壬", "戊"],
            "酉": ["辛"],
            "戌": ["戊", "辛", "丁"],
            "亥": ["壬", "甲"],
        }
        self.assertEqual(self.rules["hidden_stems"], expected)
        self.assertEqual(self.rules["model_id"], "bazi-chart-rules-v1")

    def test_ten_gods_cover_all_relationship_and_polarity_cases(self) -> None:
        expected = {
            "甲": "比肩",
            "乙": "劫财",
            "丙": "食神",
            "丁": "伤官",
            "戊": "偏财",
            "己": "正财",
            "庚": "七杀",
            "辛": "正官",
            "壬": "偏印",
            "癸": "正印",
        }
        self.assertEqual({stem: ten_god("甲", stem, self.rules) for stem in expected}, expected)

    def test_nayin_twelve_stages_and_xun_kong_are_derived(self) -> None:
        facts = derive_chart_facts(chart("甲子", "丙寅", "甲子", "乙丑"), self.rules)

        self.assertEqual(facts["pillars"]["year"]["nayin"], "海中金")
        self.assertEqual(facts["pillars"]["month"]["twelve_stage"], "临官")
        self.assertEqual(facts["xun_kong"], ["戌", "亥"])

    def test_every_structural_relation_family_is_detected(self) -> None:
        cases = {
            "stem_combination": chart("甲子", "己丑", "丙寅", "丁卯"),
            "branch_six_combination": chart("甲子", "乙丑", "丙辰", "丁巳"),
            "branch_three_combination": chart("甲申", "丙子", "戊辰", "丁亥"),
            "branch_three_meeting": chart("甲寅", "乙卯", "丙辰", "丁亥"),
            "branch_clash": chart("甲子", "丙午", "戊辰", "丁巳"),
            "branch_punishment": chart("甲寅", "乙巳", "丙申", "丁亥"),
            "branch_harm": chart("甲子", "乙未", "丙辰", "丁巳"),
            "branch_break": chart("甲子", "乙酉", "丙辰", "丁巳"),
        }
        for relation_type, pillars in cases.items():
            with self.subTest(relation_type=relation_type):
                actual = derive_chart_facts(pillars, self.rules)["interactions"]
                self.assertIn(relation_type, {item["type"] for item in actual})

    def test_transformations_remain_candidates_until_every_prerequisite_passes(self) -> None:
        formed = derive_chart_facts(chart("甲申", "丙子", "戊辰", "丁亥"), self.rules)
        disrupted = derive_chart_facts(chart("甲申", "丙子", "戊辰", "庚戌"), self.rules)

        formed_water = next(
            item for item in formed["interactions"] if item["type"] == "branch_three_combination"
        )
        disrupted_water = next(
            item for item in disrupted["interactions"] if item["type"] == "branch_three_combination"
        )
        self.assertEqual(formed_water["transformation"]["status"], "formed")
        self.assertTrue(all(formed_water["transformation"]["prerequisites"].values()))
        self.assertEqual(disrupted_water["transformation"]["status"], "candidate")
        self.assertFalse(all(disrupted_water["transformation"]["prerequisites"].values()))

    def test_shen_sha_can_never_be_primary_evidence(self) -> None:
        facts = derive_chart_facts(chart("甲子", "丙寅", "甲子", "乙丑"), self.rules)
        self.assertTrue(all(item["evidence_level"] == "secondary" for item in facts["shen_sha"]))


if __name__ == "__main__":
    unittest.main()
