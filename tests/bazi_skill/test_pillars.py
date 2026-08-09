from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from bazi.calendar import solar_term_instant
from bazi.models import BirthInput, NormalizedMoment
from bazi.pillars import (
    BRANCHES,
    STEMS,
    alternate_midnight_pillars,
    calculate_pillars,
)


class MeanSolarEphemeris:
    epoch = datetime(2024, 1, 1, tzinfo=UTC)
    rate = 360.0 / 365.2422

    def julian_day(self, moment: datetime) -> float:
        return (moment.astimezone(UTC) - self.epoch).total_seconds() / 86400.0

    def from_julian_day(self, value: float) -> datetime:
        return self.epoch + timedelta(days=value)

    def sun_longitude(self, value: float) -> float:
        return (280.0 + value * self.rate) % 360.0

    def moon_longitude(self, value: float) -> float:
        return (20.0 + value * 13.0) % 360.0

    def equation_of_time(self, value: float) -> float:
        return 0.0


EPHEMERIS = MeanSolarEphemeris()
VALID = {
    "name": "Example Person",
    "birth_place": "Greenwich, United Kingdom",
    "birth_date": "2024-06-01",
    "birth_time": "12:00",
    "calendar": "gregorian",
    "timezone": "UTC",
    "latitude": 51.48,
    "longitude": 0.0,
}


def moment(instant: datetime, *, true_solar: datetime | None = None) -> NormalizedMoment:
    aware = instant.astimezone(UTC)
    return NormalizedMoment(
        local=aware,
        utc=aware,
        utc_offset_minutes=0.0,
        fold=0,
        source="test",
        longitude_correction_minutes=0.0,
        equation_of_time_minutes=0.0,
        true_solar=true_solar or aware.replace(tzinfo=None),
    )


def birth(instant: datetime) -> BirthInput:
    return BirthInput.from_mapping(
        {
            **VALID,
            "birth_date": instant.date().isoformat(),
            "birth_time": instant.strftime("%H:%M"),
        }
    )


class PillarBoundaryTests(unittest.TestCase):
    def test_year_changes_at_the_exact_li_chun_instant(self) -> None:
        boundary = solar_term_instant(2024, 315.0, EPHEMERIS)
        before = calculate_pillars(
            birth(boundary - timedelta(minutes=1)), moment(boundary - timedelta(minutes=1)), EPHEMERIS
        )
        at = calculate_pillars(birth(boundary), moment(boundary), EPHEMERIS)

        self.assertEqual(before.year.text, "癸卯")
        self.assertEqual(at.year.text, "甲辰")
        self.assertEqual(at.year_boundary_utc, boundary)

    def test_each_month_changes_at_its_exact_jie(self) -> None:
        cases = [
            (315.0, "寅"),
            (345.0, "卯"),
            (15.0, "辰"),
            (45.0, "巳"),
            (75.0, "午"),
            (105.0, "未"),
            (135.0, "申"),
            (165.0, "酉"),
            (195.0, "戌"),
            (225.0, "亥"),
            (255.0, "子"),
            (285.0, "丑"),
        ]
        for longitude, expected_branch in cases:
            boundary = solar_term_instant(2024, longitude, EPHEMERIS)
            with self.subTest(longitude=longitude):
                before = calculate_pillars(
                    birth(boundary - timedelta(minutes=1)),
                    moment(boundary - timedelta(minutes=1)),
                    EPHEMERIS,
                )
                at = calculate_pillars(birth(boundary), moment(boundary), EPHEMERIS)
                self.assertNotEqual(before.month.branch, expected_branch)
                self.assertEqual(at.month.branch, expected_branch)

    def test_sexagenary_day_uses_a_documented_jia_zi_anchor(self) -> None:
        anchor = datetime(2000, 1, 7, 12, tzinfo=UTC)
        for offset in range(60):
            instant = anchor + timedelta(days=offset)
            with self.subTest(offset=offset):
                pillar = calculate_pillars(birth(instant), moment(instant), EPHEMERIS).day
                self.assertEqual(pillar.stem, STEMS[offset % 10])
                self.assertEqual(pillar.branch, BRANCHES[offset % 12])

    def test_twenty_three_hundred_starts_the_primary_day(self) -> None:
        base = datetime(2000, 1, 7, 22, 59, tzinfo=UTC)
        expected = ["甲子", "乙丑", "乙丑", "乙丑"]
        instants = [
            base,
            base + timedelta(minutes=1),
            base + timedelta(hours=1),
            base + timedelta(hours=1, minutes=1),
        ]
        for instant, text in zip(instants, expected, strict=True):
            with self.subTest(instant=instant):
                self.assertEqual(
                    calculate_pillars(birth(instant), moment(instant), EPHEMERIS).day.text,
                    text,
                )

    def test_all_hour_branches_and_five_zi_hour_stem_groups(self) -> None:
        anchor = datetime(2000, 1, 7, 0, 30, tzinfo=UTC)
        for branch_index in range(12):
            hour = 0 if branch_index == 0 else branch_index * 2 - 1
            instant = anchor.replace(hour=hour)
            chart = calculate_pillars(birth(instant), moment(instant), EPHEMERIS)
            self.assertEqual(chart.hour.branch, BRANCHES[branch_index])

        for day_offset, expected_stem in enumerate(("甲", "丙", "戊", "庚", "壬")):
            instant = anchor + timedelta(days=day_offset)
            chart = calculate_pillars(birth(instant), moment(instant), EPHEMERIS)
            self.assertEqual(chart.hour.text, f"{expected_stem}子")

    def test_midnight_boundary_alternate_only_exists_during_zi_hour(self) -> None:
        late = datetime(2000, 1, 7, 23, 30, tzinfo=UTC)
        primary = calculate_pillars(birth(late), moment(late), EPHEMERIS)
        alternate = alternate_midnight_pillars(birth(late), moment(late), EPHEMERIS)

        self.assertIsNotNone(alternate)
        assert alternate is not None
        self.assertNotEqual(primary.day, alternate.day)
        self.assertEqual(alternate.day_boundary, "00:00")
        noon = datetime(2000, 1, 7, 12, tzinfo=UTC)
        self.assertIsNone(alternate_midnight_pillars(birth(noon), moment(noon), EPHEMERIS))


if __name__ == "__main__":
    unittest.main()
