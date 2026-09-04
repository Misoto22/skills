"""The Zi Wei half of the gate, and the pairing check only a cross-reading needs.

Zi Wei's defects are structural rather than numeric: eleven palaces, two life
palaces, a 化忌 on a star that sits nowhere. Each hashes perfectly and each becomes
a paragraph about structure the chart does not have, which is why the prose asking
a model to check them by eye was never a check at all.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from bazi.artifacts import add_checksum
from bazi.engine import build_chart
from bazi.validation import CHART, ZIWEI, ArtifactDefect, defects, pairing_defects, validate
from bazi_skill.ephemeris_double import MeanSolarEphemeris
from ziwei.engine import build_chart as place_chart

BIRTH = {
    "name": "Subject A",
    "birth_place": "Greenwich, United Kingdom",
    "birth_date": "1990-03-14",
    "birth_time": "09:15",
    "calendar": "gregorian",
    "timezone": "UTC",
    "latitude": 51.48,
    "longitude": 0.0,
    "gender": "male",
}


class ZiweiValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        cls.chart = place_chart(dict(BIRTH), ephemeris)
        cls.late = place_chart(dict(BIRTH) | {"birth_time": "23:30"}, ephemeris)

    def test_the_gate_accepts_what_the_placer_actually_emits(self) -> None:
        """The seam. A rule the placer's own output fails is a rule that is wrong."""

        self.assertEqual(defects(self.chart, ZIWEI), [])
        self.assertEqual(defects(self.late, ZIWEI), [])
        self.assertTrue(self.late["sensitivity"]["alternate_day_boundary"])
        self.assertEqual(validate(self.chart, ZIWEI)["checksum"], self.chart["checksum"])

    def test_a_chart_short_of_a_palace_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        del broken["chart"]["primary"]["palaces"][4]

        self.assertIn("twelve palaces, found 11", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_two_life_palaces_are_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        for palace in broken["chart"]["primary"]["palaces"]:
            palace["is_life_palace"] = True

        self.assertIn("the life palace, found 12", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_no_body_palace_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        for palace in broken["chart"]["primary"]["palaces"]:
            palace["is_body_palace"] = False

        self.assertIn("the body palace, found 0", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_a_life_palace_pointer_disagreeing_with_the_mark_is_named(self) -> None:
        """Two records of one fact, and a reading would cite whichever it read first."""

        broken = copy.deepcopy(self.chart)
        marked = next(p for p in broken["chart"]["primary"]["palaces"] if p["is_life_palace"])
        other = next(p for p in broken["chart"]["primary"]["palaces"] if not p["is_life_palace"])
        broken["chart"]["primary"]["life_palace"]["branch"] = other["branch"]

        problems = "; ".join(defects(add_checksum(broken), ZIWEI))
        self.assertIn("life_palace.branch", problems)
        self.assertIn(marked["branch"], problems)

    def test_a_transformation_naming_a_star_that_sits_nowhere_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        broken["chart"]["primary"]["transformations"]["placed"].append(
            {"star": "無此星", "label": "禄", "palace": "子"}
        )

        self.assertIn("which sits in no palace", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_a_transformation_pointing_at_the_wrong_palace_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        placed = broken["chart"]["primary"]["transformations"]["placed"]
        self.assertTrue(placed, "this chart places no transformation to move")
        occupied = {placed[0]["palace"]}
        placed[0]["palace"] = next(
            palace["branch"]
            for palace in broken["chart"]["primary"]["palaces"]
            if palace["branch"] not in occupied
        )

        self.assertIn("and it is placed in", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_a_dropped_unplaced_list_is_named(self) -> None:
        """A gap this release does not place is recorded, never silently absent."""

        broken = copy.deepcopy(self.chart)
        del broken["chart"]["primary"]["transformations"]["unplaced"]

        self.assertIn("transformations.unplaced", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_decades_that_reverse_halfway_are_named(self) -> None:
        """Direction comes from one polarity-and-gender rule, so it cannot change."""

        broken = copy.deepcopy(self.chart)
        decades = broken["chart"]["primary"]["decades"]
        for index, decade in enumerate(decades[6:], start=6):
            decade["palace_index"] = (decades[5]["palace_index"] - (index - 5)) % 12

        self.assertIn("do not run in one direction", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_a_decade_window_that_is_not_ten_years_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        broken["chart"]["primary"]["decades"][3]["end_age"] += 5

        self.assertIn("is not a ten-year window", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_eleven_decade_ranges_are_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        del broken["chart"]["primary"]["decades"][0]

        self.assertIn("twelve decade ranges, found 11", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_a_declared_alternate_that_is_absent_is_named(self) -> None:
        broken = copy.deepcopy(self.late)
        broken["chart"]["alternate"] = None

        self.assertIn("chart.alternate", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_defects_inside_the_alternate_are_reported_too(self) -> None:
        """The alternate is read as its own chart, so it is checked as one."""

        broken = copy.deepcopy(self.late)
        del broken["chart"]["alternate"]["palaces"][2]

        self.assertIn("chart.alternate.palaces", "; ".join(defects(add_checksum(broken), ZIWEI)))

    def test_an_absent_sensitivity_flag_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        del broken["sensitivity"]

        self.assertIn(
            "sensitivity.alternate_day_boundary",
            "; ".join(defects(add_checksum(broken), ZIWEI)),
        )

    def test_a_structural_defect_is_named_before_the_checksum(self) -> None:
        broken = copy.deepcopy(self.chart)
        del broken["chart"]["primary"]["palaces"][0]

        with self.assertRaises(ArtifactDefect) as raised:
            validate(broken, ZIWEI)
        self.assertIn("palaces", str(raised.exception))
        self.assertNotIn("checksum", str(raised.exception))

    def test_a_bazi_chart_handed_to_the_ziwei_gate_is_refused(self) -> None:
        chart = build_chart(
            {key: value for key, value in BIRTH.items() if key != "gender"}, MeanSolarEphemeris()
        )
        problems = defects(chart, ZIWEI)

        self.assertEqual(len(problems), 1)
        self.assertIn("chinese-metaphysics.ziwei-chart", problems[0])


class CrossPairingTests(unittest.TestCase):
    """Two impeccable charts that are not one person's is the invisible failure."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ephemeris = MeanSolarEphemeris()
        cls.bazi = build_chart({key: value for key, value in BIRTH.items() if key != "gender"}, cls.ephemeris)
        cls.ziwei = place_chart(dict(BIRTH), cls.ephemeris)

    def test_one_person_at_one_moment_pairs(self) -> None:
        self.assertEqual(pairing_defects(self.bazi, self.ziwei), [])

    def test_a_different_birth_minute_is_named(self) -> None:
        other = build_chart(
            {key: value for key, value in BIRTH.items() if key != "gender"} | {"birth_time": "20:30"},
            self.ephemeris,
        )
        problems = "; ".join(pairing_defects(other, self.ziwei))

        self.assertIn("input.birth_time", problems)
        self.assertIn("20:30", problems)

    def test_a_different_day_is_named(self) -> None:
        other = build_chart(
            {key: value for key, value in BIRTH.items() if key != "gender"} | {"birth_date": "1990-03-15"},
            self.ephemeris,
        )

        self.assertIn("resolved_gregorian_date", "; ".join(pairing_defects(other, self.ziwei)))

    def test_a_different_person_is_named(self) -> None:
        other = build_chart(
            {key: value for key, value in BIRTH.items() if key != "gender"} | {"name": "Subject B"},
            self.ephemeris,
        )

        self.assertIn("input.name", "; ".join(pairing_defects(other, self.ziwei)))

    def test_only_one_chart_carrying_a_boundary_alternate_is_named(self) -> None:
        """Both systems emit one on the same true solar hour, so this cannot happen."""

        late = build_chart(
            {key: value for key, value in BIRTH.items() if key != "gender"} | {"birth_time": "23:30"},
            self.ephemeris,
        )
        ziwei = place_chart(dict(BIRTH) | {"birth_time": "23:30"}, self.ephemeris)

        self.assertEqual(pairing_defects(late, ziwei), [])
        self.assertIn("alternate_day_boundary", "; ".join(pairing_defects(late, self.ziwei)))

    def test_the_same_moment_entered_in_two_calendars_still_pairs(self) -> None:
        """Refusing this pair would be the check inventing a defect of its own."""

        lunar = self.ziwei["chart"]["primary"]["lunar"]
        entered = {key: value for key, value in BIRTH.items() if key != "gender"} | {
            "birth_date": f"{lunar['year']:04d}-{lunar['month']:02d}-{lunar['day']:02d}",
            "calendar": "lunar",
            "leap_month": bool(lunar["leap_month"]),
        }
        chart = build_chart(entered, self.ephemeris)

        self.assertNotEqual(chart["input"]["birth_date"], self.ziwei["input"]["birth_date"])
        self.assertEqual(defects(chart, CHART), [])
        self.assertEqual(pairing_defects(chart, self.ziwei), [])


if __name__ == "__main__":
    unittest.main()
