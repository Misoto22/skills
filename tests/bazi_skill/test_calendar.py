from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
FIXTURE = Path(__file__).parent / "fixtures" / "official-calendar.json"
BEIJING = timezone(timedelta(hours=8))
sys.path.insert(0, str(SHARED))

from bazi.calendar import CalendarError, lunar_to_gregorian, solar_term_instant
from bazi.ephemeris import EphemerisUnavailable, SwissEphemeris


class LinearEphemeris:
    """Deterministic ephemeris for exercising wrapped-angle root finding."""

    epoch = datetime(2024, 1, 1, tzinfo=UTC)

    def julian_day(self, moment: datetime) -> float:
        return (moment.astimezone(UTC) - self.epoch).total_seconds() / 86400.0

    def from_julian_day(self, value: float) -> datetime:
        return self.epoch + timedelta(days=value)

    def sun_longitude(self, value: float) -> float:
        return (280.0 + value) % 360.0

    def moon_longitude(self, value: float) -> float:
        return (20.0 + 14.0 * value) % 360.0

    def equation_of_time(self, value: float) -> float:
        return 0.0


class RootFindingTests(unittest.TestCase):
    def test_solar_crossing_handles_the_zero_degree_wrap(self) -> None:
        result = solar_term_instant(2024, 0.0, LinearEphemeris())

        self.assertLess(abs((result - datetime(2024, 3, 21, tzinfo=UTC)).total_seconds()), 0.5)

    def test_invalid_longitude_is_rejected(self) -> None:
        with self.assertRaisesRegex(CalendarError, "longitude"):
            solar_term_instant(2024, 360.0, LinearEphemeris())


class LazySwissTests(unittest.TestCase):
    def test_missing_dependency_has_one_actionable_error(self) -> None:
        if importlib.util.find_spec("swisseph") is not None:
            self.skipTest("pyswisseph is installed in this interpreter")

        with self.assertRaisesRegex(EphemerisUnavailable, "pyswisseph"):
            SwissEphemeris()


@unittest.skipUnless(importlib.util.find_spec("swisseph"), "requires pyswisseph")
class SwissIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ephemeris = SwissEphemeris()
        cls.fixtures = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_julian_conversion_round_trips_utc(self) -> None:
        expected = datetime(2026, 2, 3, 20, 2, 17, 500000, tzinfo=UTC)
        actual = self.ephemeris.from_julian_day(self.ephemeris.julian_day(expected))

        self.assertLess(abs((actual - expected).total_seconds()), 0.001)

    def test_official_solar_term_instants(self) -> None:
        for item in self.fixtures["solar_terms"]:
            with self.subTest(name=item["name"], year=item["year"]):
                expected = datetime.fromisoformat(item["utc"])
                actual = solar_term_instant(item["year"], item["longitude"], self.ephemeris)
                self.assertLessEqual(abs((actual - expected).total_seconds()), item["tolerance_seconds"])

    def test_official_solar_term_dates_across_supported_range(self) -> None:
        for item in self.fixtures["solar_term_dates"]:
            with self.subTest(name=item["name"], year=item["year"]):
                actual = solar_term_instant(item["year"], item["longitude"], self.ephemeris).astimezone(
                    BEIJING
                )
                self.assertEqual(actual.date(), date.fromisoformat(item["beijing_date"]))

    def test_official_lunar_conversion_dates(self) -> None:
        for item in self.fixtures["lunar_dates"]:
            with self.subTest(lunar=item["lunar"], leap=item["leap"]):
                year, month, day = (int(part) for part in item["lunar"].split("-"))
                self.assertEqual(
                    lunar_to_gregorian(year, month, day, item["leap"], self.ephemeris),
                    date.fromisoformat(item["gregorian"]),
                )

    def test_nonexistent_lunar_day_is_rejected(self) -> None:
        with self.assertRaisesRegex(CalendarError, "does not exist"):
            lunar_to_gregorian(2020, 4, 30, True, self.ephemeris)


if __name__ == "__main__":
    unittest.main()
