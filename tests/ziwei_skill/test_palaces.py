from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from ziwei.palaces import (
    Bureau,
    ZiweiError,
    body_palace_index,
    build_palaces,
    bureau_for,
    decade_cycles,
    life_palace_index,
    palace_stem,
)

RULES = json.loads((SHARED / "rules" / "ziwei-v1.json").read_text(encoding="utf-8")) | {
    "nayin": json.loads((SHARED / "rules" / "chart-v1.json").read_text(encoding="utf-8"))["nayin"]
}


class PalacePlacementTests(unittest.TestCase):
    def test_life_palace_counts_months_forward_then_hours_backward(self):
        # 寅 starts month one, so month 1 at 子 hour lands on 寅 itself.
        self.assertEqual(life_palace_index(1, 0), 2)
        # Lunar month 11 at 午 hour is the documented 午 life palace.
        self.assertEqual(life_palace_index(11, 6), 6)

    def test_body_palace_counts_hours_forward_instead(self):
        self.assertEqual(body_palace_index(11, 6), 6)
        self.assertEqual(body_palace_index(2, 4), 7)

    def test_life_and_body_meet_only_at_the_extreme_hours(self):
        for month in range(1, 13):
            for hour in range(12):
                same = life_palace_index(month, hour) == body_palace_index(month, hour)
                self.assertEqual(same, hour in (0, 6), (month, hour))

    def test_out_of_range_input_is_refused(self):
        with self.assertRaises(ZiweiError):
            life_palace_index(13, 0)
        with self.assertRaises(ZiweiError):
            body_palace_index(1, 12)

    def test_palace_stem_follows_the_five_tiger_rule(self):
        # 甲 year opens 寅 with 丙; 戊 year opens it with 甲.
        self.assertEqual(palace_stem(2, 0), "丙")
        self.assertEqual(palace_stem(2, 4), "甲")
        # 己 shares 甲's opening stem, five places later in the cycle.
        self.assertEqual(palace_stem(2, 5), "丙")
        # Stems advance with the branch, so 午 in a 己 year carries 庚.
        self.assertEqual(palace_stem(6, 5), "庚")

    def test_bureau_comes_from_the_life_palace_sound(self):
        bureau = bureau_for(6, 5, RULES)  # 庚午 -> 路旁土
        self.assertEqual((bureau.element, bureau.name, bureau.value), ("土", "土五局", 5))

    def test_every_life_palace_and_year_stem_resolves_a_bureau(self):
        for life_index in range(12):
            for stem_index in range(10):
                bureau = bureau_for(life_index, stem_index, RULES)
                self.assertIn(bureau.value, (2, 3, 4, 5, 6))


class PalaceNamingTests(unittest.TestCase):
    def test_names_run_backward_from_the_life_palace(self):
        palaces = build_palaces(6, 6, 5, RULES)
        self.assertEqual(palaces[6].name, "命宫")
        self.assertEqual(palaces[5].name, "兄弟")
        self.assertEqual(palaces[7].name, "父母")

    def test_all_twelve_names_appear_exactly_once(self):
        palaces = build_palaces(3, 9, 0, RULES)
        self.assertCountEqual([p.name for p in palaces], RULES["palace_names"])

    def test_life_and_body_flags_mark_the_right_palaces(self):
        palaces = build_palaces(6, 9, 5, RULES)
        self.assertTrue(palaces[6].is_life)
        self.assertTrue(palaces[9].is_body)
        self.assertFalse(palaces[9].is_life)


class DecadeCycleTests(unittest.TestCase):
    bureau = Bureau(element="土", name="土五局", value=5)

    def palaces(self):
        return build_palaces(6, 6, 5, RULES)

    def test_yang_year_male_runs_forward(self):
        decades = decade_cycles(6, self.bureau, 0, "male", self.palaces())
        self.assertEqual([d["palace_index"] for d in decades[:3]], [6, 7, 8])

    def test_yin_year_male_runs_backward(self):
        decades = decade_cycles(6, self.bureau, 5, "male", self.palaces())
        self.assertEqual([d["palace_index"] for d in decades[:3]], [6, 5, 4])

    def test_gender_flips_the_direction(self):
        forward = decade_cycles(6, self.bureau, 0, "male", self.palaces())
        backward = decade_cycles(6, self.bureau, 0, "female", self.palaces())
        self.assertNotEqual(forward[1]["palace_index"], backward[1]["palace_index"])

    def test_ages_open_at_the_bureau_value(self):
        decades = decade_cycles(6, self.bureau, 0, "male", self.palaces())
        self.assertEqual((decades[0]["start_age"], decades[0]["end_age"]), (5, 14))
        self.assertEqual((decades[1]["start_age"], decades[1]["end_age"]), (15, 24))
        self.assertEqual(len(decades), 12)

    def test_missing_gender_is_refused_rather_than_defaulted(self):
        for value in ("", "unknown", "other", None):
            with self.assertRaises(ZiweiError):
                decade_cycles(6, self.bureau, 0, value, self.palaces())


if __name__ == "__main__":
    unittest.main()
