from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "astrology" / "skills" / "synastry" / "scripts"))

from report import ASPECT_BODIES, OVERLAY_BODIES, display_width, natal_block, pad, render

EQUAL_CUSPS = [index * 30.0 for index in range(12)]

BODY_ORDER = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "Chiron",
    "Ceres",
    "Pallas",
    "Juno",
    "Vesta",
    "Lilith",
    "North_Node",
    "Vertex",
    "East_Point",
)


def chart(name: str, offset: float, *, retrograde: tuple[str, ...] = ()) -> dict:
    """A complete synthetic chart: every body spaced evenly, rotated by `offset`."""

    longitudes = {body: (offset + index * 17.0) % 360.0 for index, body in enumerate(BODY_ORDER)}
    longitudes["South_Node"] = (longitudes["North_Node"] + 180.0) % 360.0
    longitudes["Ascendant"] = offset
    longitudes["Descendant"] = (offset + 180.0) % 360.0
    longitudes["Medium_Coeli"] = (offset + 270.0) % 360.0
    longitudes["Imum_Coeli"] = (offset + 90.0) % 360.0
    return {
        "name": name,
        "birth_local": "1990-03-14 07:42",
        "birth_place": "Sample City",
        "residence": "Sample City",
        "timezone": "Asia/Shanghai",
        "utc_offset_hours": 8.0,
        "latitude": 31.23,
        "longitude": 121.47,
        "house_system": "placidus",
        "longitudes": longitudes,
        "retrograde": list(retrograde),
        "cusps": list(EQUAL_CUSPS),
    }


class WidthTests(unittest.TestCase):
    def test_a_wide_character_counts_as_two_columns(self) -> None:
        self.assertEqual(display_width("Sun"), 3)
        self.assertEqual(display_width("太阳"), 4)
        self.assertEqual(display_width("太阳 Sun"), 8)

    def test_padding_reaches_the_column_in_both_scripts(self) -> None:
        self.assertEqual(display_width(pad("太阳", 10)), 10)
        self.assertEqual(display_width(pad("Sun", 10)), 10)

    def test_padding_never_truncates_an_overlong_field(self) -> None:
        self.assertEqual(pad("a very long body name", 4), "a very long body name")


class NatalBlockTests(unittest.TestCase):
    def test_every_section_is_present(self) -> None:
        lines = "\n".join(natal_block(chart("Person A", 5.0), language="en"))

        for heading in (
            "Birth data",
            "Big three",
            "Planets",
            "Angles",
            "Asteroids and sensitive points",
            "Classical lots",
            "House cusps",
            "House occupants",
        ):
            self.assertIn(heading, lines)

    def test_dignity_retrograde_and_critical_degree_are_stated(self) -> None:
        subject = chart("Person A", 5.0, retrograde=("Mercury",))
        subject["longitudes"]["Sun"] = 125.0
        subject["longitudes"]["Moon"] = 29.5
        lines = "\n".join(natal_block(subject, language="en"))

        self.assertIn("domicile", lines)
        self.assertIn("retrograde", lines)
        self.assertIn("critical degree", lines)

    def test_an_absent_point_is_skipped_rather_than_faked(self) -> None:
        subject = chart("Person A", 5.0)
        del subject["longitudes"]["Vertex"]
        lines = "\n".join(natal_block(subject, language="en"))

        self.assertNotIn("Vertex", lines)
        self.assertIn("East Point", lines)

    def test_a_body_the_ephemeris_could_not_resolve_is_named(self) -> None:
        """Silently absent reads as nothing to report, which is the opposite of the truth."""

        subject = chart("Person A", 5.0)
        del subject["longitudes"]["Ceres"]
        subject["unavailable"] = ["Ceres"]

        english = "\n".join(natal_block(subject, language="en"))
        chinese = "\n".join(natal_block(subject, language="zh"))

        self.assertIn("Not resolved, ephemeris data file missing: Ceres", english)
        self.assertIn("未能解析", chinese)
        self.assertIn("谷神星", chinese)

    def test_nothing_is_said_when_every_body_resolved(self) -> None:
        lines = "\n".join(natal_block(chart("Person A", 5.0), language="en"))

        self.assertNotIn("Not resolved", lines)

    def test_an_empty_house_says_so(self) -> None:
        subject = chart("Person A", 5.0)
        subject["longitudes"] = dict.fromkeys(subject["longitudes"], 10.0)
        lines = "\n".join(natal_block(subject, language="en"))

        self.assertIn("empty", lines)


class RenderTests(unittest.TestCase):
    def test_both_people_and_the_synastry_appear_once_each(self) -> None:
        document = render(chart("Person A", 5.0), chart("Person B", 95.0))

        self.assertEqual(document.count("Natal chart: Person A"), 1)
        self.assertEqual(document.count("Natal chart: Person B"), 1)
        self.assertIn("Synastry: Person A x Person B", document)
        self.assertIn("End of data", document)

    def test_overlays_run_in_both_directions(self) -> None:
        document = render(chart("Person A", 5.0), chart("Person B", 95.0))

        self.assertIn("Person B bodies falling in the houses of Person A", document)
        self.assertIn("Person A bodies falling in the houses of Person B", document)

    def test_the_orbs_in_force_are_stated_and_obeyed(self) -> None:
        wide = render(chart("Person A", 5.0), chart("Person B", 95.0), major_orb=8.0, minor_orb=3.0)
        narrow = render(chart("Person A", 5.0), chart("Person B", 95.0), major_orb=1.0, minor_orb=0.5)

        self.assertIn("within 8.0°", wide)
        self.assertIn("within 1.0°", narrow)
        self.assertLess(_aspect_count(narrow), _aspect_count(wide))

    def test_the_mirrored_points_stay_out_of_the_aspect_pass(self) -> None:
        """Each would restate a contact already listed under the body opposite it."""

        for mirrored in ("Descendant", "Imum_Coeli", "South_Node"):
            self.assertNotIn(mirrored, ASPECT_BODIES)
        for body in ("Ascendant", "Medium_Coeli", "Juno", "Vertex"):
            self.assertIn(body, ASPECT_BODIES)
        self.assertEqual(OVERLAY_BODIES[-2:], ("Ascendant", "Medium_Coeli"))

    def test_chinese_labels_replace_every_english_one(self) -> None:
        document = render(chart("甲", 5.0), chart("乙", 95.0), language="zh")

        for expected in ("本命盘", "合盘", "十大行星", "阿拉伯点", "宫位互入", "数据结束"):
            self.assertIn(expected, document)
        for absent in ("Natal chart", "Synastry:", "House occupants"):
            self.assertNotIn(absent, document)

    def test_an_unknown_language_is_refused_rather_than_defaulted(self) -> None:
        with self.assertRaises(ValueError):
            render(chart("Person A", 5.0), chart("Person B", 95.0), language="fr")

    def test_the_same_input_renders_the_same_bytes(self) -> None:
        first = render(chart("Person A", 5.0), chart("Person B", 95.0))
        second = render(chart("Person A", 5.0), chart("Person B", 95.0))

        self.assertEqual(first, second)


def _aspect_count(document: str) -> int:
    line = next(line for line in document.splitlines() if line.strip().endswith("aspects"))
    return int(line.strip().split()[0])


if __name__ == "__main__":
    unittest.main()
