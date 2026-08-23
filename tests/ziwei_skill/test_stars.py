from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from ziwei.palaces import Bureau, ZiweiError
from ziwei.stars import (
    place_stars,
    stars_by_palace,
    tianfu_palace_index,
    unplaced_transformations,
    ziwei_palace_index,
)

RULES = json.loads((SHARED / "rules" / "ziwei-v1.json").read_text(encoding="utf-8"))
BUREAUS = {
    2: Bureau("水", "水二局", 2),
    3: Bureau("木", "木三局", 3),
    4: Bureau("金", "金四局", 4),
    5: Bureau("土", "土五局", 5),
    6: Bureau("火", "火六局", 6),
}


class ZiweiPlacementTests(unittest.TestCase):
    def test_day_one_matches_the_published_table(self):
        # 水二局 丑, 木三局 辰, 金四局 亥, 土五局 午, 火六局 酉.
        expected = {2: 1, 3: 4, 4: 11, 5: 6, 6: 9}
        for value, index in expected.items():
            self.assertEqual(ziwei_palace_index(BUREAUS[value], 1), index, value)

    def test_water_bureau_walks_the_first_days_correctly(self):
        walk = [ziwei_palace_index(BUREAUS[2], day) for day in range(1, 7)]
        self.assertEqual(walk, [1, 2, 2, 3, 3, 4])

    def test_earth_bureau_day_twenty_five_lands_on_wu(self):
        self.assertEqual(ziwei_palace_index(BUREAUS[5], 25), 6)

    def test_every_bureau_and_day_stays_inside_the_cycle(self):
        for bureau in BUREAUS.values():
            for day in range(1, 31):
                self.assertIn(ziwei_palace_index(bureau, day), range(12))

    def test_out_of_range_day_is_refused(self):
        for day in (0, 31, -1):
            with self.assertRaises(ZiweiError):
                ziwei_palace_index(BUREAUS[2], day)

    def test_tianfu_mirrors_ziwei_across_the_yin_shen_axis(self):
        self.assertEqual(tianfu_palace_index(2), 2)  # 寅 maps to itself
        self.assertEqual(tianfu_palace_index(8), 8)  # 申 maps to itself
        self.assertEqual(tianfu_palace_index(0), 4)
        self.assertEqual(tianfu_palace_index(6), 10)


class StarSetTests(unittest.TestCase):
    def place(self, **overrides):
        arguments = {
            "bureau": BUREAUS[5],
            "lunar_month": 11,
            "lunar_day": 25,
            "hour_branch": 6,
            "year_stem": "己",
            "rules": RULES,
        }
        return place_stars(**(arguments | overrides))

    def test_the_ziwei_in_wu_chart_matches_the_standard_arrangement(self):
        placed = {star.name: star.palace_index for star in self.place()}
        expected = {
            "紫微": 6,
            "天机": 5,
            "太阳": 3,
            "武曲": 2,
            "天同": 1,
            "廉贞": 10,
            "天府": 10,
            "太阴": 11,
            "贪狼": 0,
            "巨门": 1,
            "天相": 2,
            "天梁": 3,
            "七杀": 4,
            "破军": 8,
        }
        self.assertEqual({k: placed[k] for k in expected}, expected)

    def test_support_stars_follow_their_month_and_hour_anchors(self):
        placed = {star.name: star.palace_index for star in self.place()}
        self.assertEqual(placed["左辅"], 2)
        self.assertEqual(placed["右弼"], 0)
        self.assertEqual(placed["文昌"], 4)
        self.assertEqual(placed["文曲"], 10)

    def test_malefics_sit_either_side_of_the_year_stem_lu_cun(self):
        placed = {star.name: star.palace_index for star in self.place()}
        self.assertEqual(placed["禄存"], 6)
        self.assertEqual(placed["擎羊"], 7)
        self.assertEqual(placed["陀罗"], 5)

    def test_year_stem_carries_exactly_four_transformations(self):
        carried = {star.transformation: star.name for star in self.place() if star.transformation}
        self.assertEqual(carried, {"禄": "武曲", "权": "贪狼", "科": "天梁", "忌": "文曲"})

    def test_every_year_stem_places_all_four_transformations(self):
        for stem in RULES["stems"]:
            stars = self.place(year_stem=stem)
            carried = [star for star in stars if star.transformation]
            self.assertEqual(len(carried), 4, stem)
            self.assertEqual(unplaced_transformations(stars, RULES, stem), [], stem)

    def test_main_stars_carry_brightness_and_support_stars_do_not(self):
        for star in self.place():
            if star.name in RULES["star_classes"]["主星"]:
                self.assertIn(star.brightness, ("庙", "旺", "得", "利", "平", "陷"), star.name)
            else:
                self.assertIsNone(star.brightness, star.name)

    def test_unknown_year_stem_is_refused(self):
        with self.assertRaises(ZiweiError):
            self.place(year_stem="X")

    def test_grouping_covers_all_twelve_palaces_without_losing_a_star(self):
        stars = self.place()
        grouped = stars_by_palace(stars)
        self.assertEqual(sorted(grouped), list(range(12)))
        self.assertEqual(sum(len(items) for items in grouped.values()), len(stars))

    def test_fourteen_main_stars_are_always_placed(self):
        for month in range(1, 13):
            for day in (1, 14, 30):
                names = {star.name for star in self.place(lunar_month=month, lunar_day=day)}
                self.assertTrue(set(RULES["star_classes"]["主星"]) <= names, (month, day))


if __name__ == "__main__":
    unittest.main()
