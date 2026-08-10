from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from bazi.models import BirthDataError, BirthInput
from bazi.timekeeping import apply_true_solar_time, resolve_civil_time

VALID = {
    "name": "Example Person",
    "birth_place": "Shanghai, China",
    "birth_date": "1990-03-14",
    "birth_time": "07:42",
    "calendar": "gregorian",
    "timezone": "Asia/Shanghai",
    "latitude": 31.23,
    "longitude": 121.47,
}


class BirthInputTests(unittest.TestCase):
    def test_valid_gregorian_input_is_immutable_and_normalized(self) -> None:
        birth = BirthInput.from_mapping(VALID)

        self.assertEqual(birth.name, "Example Person")
        self.assertEqual(birth.calendar, "gregorian")
        self.assertIsNone(birth.gender)
        with self.assertRaises(AttributeError):
            birth.name = "Changed"  # type: ignore[misc]

    def test_every_fault_is_reported_in_one_error(self) -> None:
        with self.assertRaises(BirthDataError) as raised:
            BirthInput.from_mapping(
                {
                    "name": "",
                    "birth_place": "",
                    "birth_date": "1899-13-40",
                    "birth_time": "7am",
                    "calendar": "martian",
                    "timezone": "",
                    "latitude": 100,
                    "longitude": 200,
                }
            )

        message = "\n".join(raised.exception.problems)
        for expected in (
            "name: required",
            "birth_place: required",
            "birth_date",
            "birth_time: expected HH:MM",
            "calendar",
            "timezone: required",
            "latitude",
            "longitude",
        ):
            self.assertIn(expected, message)

    def test_birth_time_requires_an_exact_minute(self) -> None:
        for value in ("07", "7:42", "07:42:00", "around seven"):
            with self.subTest(value=value), self.assertRaisesRegex(BirthDataError, "HH:MM"):
                BirthInput.from_mapping({**VALID, "birth_time": value})

    def test_supported_years_are_inclusive(self) -> None:
        self.assertEqual(BirthInput.from_mapping({**VALID, "birth_date": "1900-01-01"}).year, 1900)
        self.assertEqual(BirthInput.from_mapping({**VALID, "birth_date": "2100-12-31"}).year, 2100)
        for value in ("1899-12-31", "2101-01-01"):
            with self.assertRaisesRegex(BirthDataError, "1900 through 2100"):
                BirthInput.from_mapping({**VALID, "birth_date": value})

    def test_lunar_input_requires_an_explicit_leap_month_flag(self) -> None:
        lunar = {**VALID, "calendar": "lunar"}
        with self.assertRaisesRegex(BirthDataError, "leap_month"):
            BirthInput.from_mapping(lunar)

        self.assertFalse(BirthInput.from_mapping({**lunar, "leap_month": False}).leap_month)
        self.assertTrue(BirthInput.from_mapping({**lunar, "leap_month": True}).leap_month)

    def test_gregorian_input_rejects_a_true_leap_month_flag(self) -> None:
        with self.assertRaisesRegex(BirthDataError, "only valid for lunar"):
            BirthInput.from_mapping({**VALID, "leap_month": True})

    def test_fold_and_offset_fields_are_strict(self) -> None:
        for field, value, expected in (
            ("fold", 2, "fold"),
            ("fold", "0", "fold"),
            ("utc_offset_minutes", 900, "utc_offset_minutes"),
            ("utc_offset_minutes", "480", "utc_offset_minutes"),
        ):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(BirthDataError, expected):
                BirthInput.from_mapping({**VALID, field: value})


class CivilTimeTests(unittest.TestCase):
    def test_iana_offset_is_resolved_on_the_birth_date(self) -> None:
        summer = BirthInput.from_mapping(
            {
                **VALID,
                "birth_place": "New York, USA",
                "birth_date": "2021-07-01",
                "timezone": "America/New_York",
                "latitude": 40.71,
                "longitude": -74.01,
            }
        )
        winter = BirthInput.from_mapping({**summer.to_mapping(), "birth_date": "2021-12-01"})

        self.assertEqual(resolve_civil_time(summer).utc_offset_minutes, -240)
        self.assertEqual(resolve_civil_time(winter).utc_offset_minutes, -300)

    def test_repeated_dst_time_requires_a_fold(self) -> None:
        repeated = {
            **VALID,
            "birth_place": "New York, USA",
            "birth_date": "2021-11-07",
            "birth_time": "01:30",
            "timezone": "America/New_York",
            "latitude": 40.71,
            "longitude": -74.01,
        }
        with self.assertRaisesRegex(BirthDataError, "ambiguous"):
            resolve_civil_time(BirthInput.from_mapping(repeated))

        first = resolve_civil_time(BirthInput.from_mapping({**repeated, "fold": 0}))
        second = resolve_civil_time(BirthInput.from_mapping({**repeated, "fold": 1}))
        self.assertEqual(first.utc_offset_minutes, -240)
        self.assertEqual(second.utc_offset_minutes, -300)
        self.assertNotEqual(first.utc, second.utc)

    def test_nonexistent_dst_time_is_rejected(self) -> None:
        missing = BirthInput.from_mapping(
            {
                **VALID,
                "birth_place": "New York, USA",
                "birth_date": "2021-03-14",
                "birth_time": "02:30",
                "timezone": "America/New_York",
                "latitude": 40.71,
                "longitude": -74.01,
            }
        )

        with self.assertRaisesRegex(BirthDataError, "does not exist"):
            resolve_civil_time(missing)

    def test_explicit_offset_overrides_the_zone_database(self) -> None:
        birth = BirthInput.from_mapping({**VALID, "utc_offset_minutes": 510})
        moment = resolve_civil_time(birth)

        self.assertEqual(moment.utc_offset_minutes, 510)
        self.assertEqual(moment.source, "explicit-offset")
        self.assertEqual((moment.utc.hour, moment.utc.minute), (23, 12))

    def test_unknown_iana_zone_is_actionable(self) -> None:
        with self.assertRaisesRegex(BirthDataError, "IANA"):
            resolve_civil_time(BirthInput.from_mapping({**VALID, "timezone": "Mars/Olympus"}))


class TrueSolarTimeTests(unittest.TestCase):
    def test_longitude_and_equation_of_time_are_recorded_separately(self) -> None:
        birth = BirthInput.from_mapping({**VALID, "birth_time": "12:00"})
        normalized = apply_true_solar_time(birth, resolve_civil_time(birth), 2.0 / 1440.0)

        self.assertAlmostEqual(normalized.longitude_correction_minutes, 5.88, places=2)
        self.assertAlmostEqual(normalized.equation_of_time_minutes, 2.0, places=6)
        self.assertEqual(normalized.true_solar, datetime(1990, 3, 14, 12, 7, 52, 800000))

    def test_true_solar_correction_can_cross_the_civil_date(self) -> None:
        birth = BirthInput.from_mapping(
            {
                **VALID,
                "birth_place": "Sample Place",
                "birth_date": "2000-01-02",
                "birth_time": "00:05",
                "timezone": "Etc/GMT+9",
                "longitude": -150.0,
                "utc_offset_minutes": -540,
            }
        )
        normalized = apply_true_solar_time(birth, resolve_civil_time(birth), 0.0)

        self.assertEqual(normalized.true_solar, datetime(2000, 1, 1, 23, 5))


if __name__ == "__main__":
    unittest.main()
