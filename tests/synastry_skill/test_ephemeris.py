from __future__ import annotations

import sys
import unittest
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import replace
from datetime import date, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "astrology" / "skills" / "synastry" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ephemeris import (  # type: ignore[import-not-found]
    EphemerisError,
    PositionSamples,
    backend_name,
    resolve_subject,
    set_ephemeris_path,
)
from request_schema import CalculationOptions, DateOnlyBirth, ExactBirth, Subject, WindowBirth


class FakeSwe:
    class Error(Exception):
        pass

    FLG_JPLEPH = 1
    FLG_SWIEPH = 2
    FLG_MOSEPH = 4
    FLG_SPEED = 256

    SUN = 0
    MOON = 1
    MERCURY = 2
    VENUS = 3
    MARS = 4
    JUPITER = 5
    SATURN = 6
    URANUS = 7
    NEPTUNE = 8
    PLUTO = 9
    MEAN_NODE = 10
    MEAN_APOG = 12
    CHIRON = 15
    CERES = 17
    PALLAS = 18
    JUNO = 19
    VESTA = 20

    version = "2.10.03-test"

    def __init__(
        self,
        *,
        return_flags: int | Iterable[int] | None = None,
        house_error: str | None = None,
        body_errors: Iterable[int] = (),
    ) -> None:
        default_flags = self.FLG_SWIEPH | self.FLG_SPEED
        if isinstance(return_flags, int) or return_flags is None:
            self._return_flags = None if return_flags is None else iter((return_flags,))
            self._last_return_flags = default_flags if return_flags is None else return_flags
        else:
            values = tuple(return_flags)
            self._return_flags = iter(values)
            self._last_return_flags = values[-1]
        self.house_error = house_error
        self.body_errors = frozenset(body_errors)
        self.calc_ut_error = "missing file"
        self.julday_error: str | None = None
        self.julday_calls: list[tuple[int, int, int, float]] = []
        self.calc_calls: list[tuple[float, int, int]] = []
        self.house_calls: list[tuple[float, float, float, bytes]] = []
        self.ephemeris_paths: list[str | None] = []

    def set_ephe_path(self, path: str | None) -> None:
        self.ephemeris_paths.append(path)

    def julday(self, year: int, month: int, day: int, hour: float) -> float:
        self.julday_calls.append((year, month, day, hour))
        if self.julday_error is not None:
            raise self.Error(self.julday_error)
        return float(year * 10000 + month * 100 + day) + hour / 24.0

    def calc_ut(self, julian_day: float, code: int, flags: int) -> tuple[tuple[float, ...], int]:
        self.calc_calls.append((julian_day, code, flags))
        if code in self.body_errors:
            raise self.Error(f"{self.calc_ut_error} for body {code}")
        if self._return_flags is not None:
            with suppress(StopIteration):
                self._last_return_flags = next(self._return_flags)
        position = ((julian_day + code) % 360.0, code / 10.0, 1.0 + code / 100.0, code - 5.0, 0.0, 0.0)
        return position, self._last_return_flags

    def houses(
        self, julian_day: float, latitude: float, longitude: float, system: bytes
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        self.house_calls.append((julian_day, latitude, longitude, system))
        if self.house_error is not None:
            raise self.Error(self.house_error)
        cusps = tuple(float(index * 30) for index in range(12))
        angles = (11.0, 22.0, 0.0, 33.0, 44.0, 0.0, 0.0, 0.0)
        return cusps, angles


def exact_subject(*, latitude: float = 48.86) -> Subject:
    return Subject(
        id="subject-a",
        display_name="Alex",
        pronouns=None,
        birth=ExactBirth(
            mode="exact",
            date=date(1990, 3, 14),
            time=time(7, 42),
            time_accuracy_minutes=5,
            timezone="Europe/Paris",
            timezone_fold=None,
            latitude=latitude,
            longitude=2.35,
            utc_offset_hours=None,
            utc_offset_reason=None,
            place_label="Paris",
            location_source="user supplied",
        ),
    )


def polar_subject() -> Subject:
    return exact_subject(latitude=89.0)


def window_subject() -> Subject:
    return Subject(
        id="subject-b",
        display_name="Morgan",
        pronouns=None,
        birth=WindowBirth(
            mode="window",
            date=date(1992, 6, 8),
            start=time(9, 0),
            end=time(10, 0),
            timezone="UTC",
            utc_offset_hours=None,
            utc_offset_reason=None,
            place_label=None,
            location_source=None,
        ),
    )


def date_only_subject() -> Subject:
    return Subject(
        id="subject-c",
        display_name=None,
        pronouns=None,
        birth=DateOnlyBirth(
            mode="date-only",
            date=date(1992, 6, 8),
            timezone="UTC",
            utc_offset_hours=None,
            utc_offset_reason=None,
            place_label=None,
            location_source=None,
        ),
    )


def swiss_options() -> CalculationOptions:
    return CalculationOptions(
        language="en",
        house_system="whole-sign",
        major_orb=8.0,
        minor_orb=3.0,
        ephemeris_policy="swiss-only",
        calculation_profile="western-tropical-v1",
        aspect_profile="ptolemaic-minor-v1",
        include_derived=False,
        privacy="minimal",
    )


def moshier_options() -> CalculationOptions:
    return replace(swiss_options(), ephemeris_policy="allow-moshier")


class BackendPolicyTests(unittest.TestCase):
    def test_swiss_only_rejects_moshier_return_flags(self) -> None:
        fake = FakeSwe(return_flags=FakeSwe.FLG_MOSEPH | FakeSwe.FLG_SPEED)

        with self.assertRaisesRegex(EphemerisError, "requested Swiss.*used Moshier"):
            resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

    def test_allow_moshier_records_actual_backend_and_limitation(self) -> None:
        fake = FakeSwe(return_flags=FakeSwe.FLG_MOSEPH | FakeSwe.FLG_SPEED)

        chart = resolve_subject(exact_subject(), moshier_options(), swe_module=fake)

        self.assertEqual(chart.provenance.actual_backend, "moshier")
        self.assertIn("ephemeris-fallback", {item.code for item in chart.limitations})

    def test_backend_name_uses_returned_flags_not_requested_flags(self) -> None:
        self.assertEqual(backend_name(FakeSwe.FLG_SWIEPH | FakeSwe.FLG_SPEED, FakeSwe), "swiss")
        self.assertEqual(backend_name(FakeSwe.FLG_MOSEPH | FakeSwe.FLG_SPEED, FakeSwe), "moshier")
        with self.assertRaisesRegex(EphemerisError, "unrecognized ephemeris backend"):
            backend_name(FakeSwe.FLG_SPEED, FakeSwe)
        with self.assertRaisesRegex(EphemerisError, "ambiguous ephemeris backend"):
            backend_name(
                FakeSwe.FLG_JPLEPH | FakeSwe.FLG_SWIEPH | FakeSwe.FLG_SPEED,
                FakeSwe,
            )

    def test_returned_flags_must_confirm_requested_speed_data(self) -> None:
        fake = FakeSwe(return_flags=FakeSwe.FLG_SWIEPH)

        with self.assertRaisesRegex(EphemerisError, "returned flags.*speed"):
            resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

    def test_unknown_policy_never_authorizes_moshier(self) -> None:
        fake = FakeSwe(return_flags=FakeSwe.FLG_MOSEPH | FakeSwe.FLG_SPEED)
        invalid = replace(swiss_options(), ephemeris_policy="accept-anything")

        with self.assertRaisesRegex(EphemerisError, "unsupported ephemeris policy"):
            resolve_subject(exact_subject(), invalid, swe_module=fake)

    def test_provenance_records_each_distinct_return_flag(self) -> None:
        swiss = FakeSwe.FLG_SWIEPH | FakeSwe.FLG_SPEED
        moshier = FakeSwe.FLG_MOSEPH | FakeSwe.FLG_SPEED
        fake = FakeSwe(return_flags=(swiss, moshier))

        chart = resolve_subject(exact_subject(), moshier_options(), swe_module=fake)

        self.assertEqual(chart.provenance.return_flags, (swiss, moshier))
        self.assertEqual(chart.provenance.binding_version, FakeSwe.version)

    def test_configured_data_path_stays_inside_backend_and_is_recorded(self) -> None:
        fake = FakeSwe()

        set_ephemeris_path("/ephemeris/data", swe_module=fake)
        chart = resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

        self.assertEqual(fake.ephemeris_paths, ["/ephemeris/data"])
        self.assertEqual(chart.provenance.data_path, "/ephemeris/data")

        set_ephemeris_path(None, swe_module=fake)
        reset = resolve_subject(exact_subject(), swiss_options(), swe_module=fake)
        self.assertEqual(fake.ephemeris_paths, ["/ephemeris/data", None])
        self.assertIsNone(reset.provenance.data_path)


class ResolutionModeTests(unittest.TestCase):
    def test_exact_mode_resolves_one_sample_and_houses(self) -> None:
        fake = FakeSwe()

        chart = resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

        self.assertEqual(chart.precision_mode, "exact")
        self.assertEqual(len(fake.julday_calls), 1)
        self.assertEqual(len(fake.house_calls), 1)
        self.assertEqual(fake.house_calls[0][3], b"W")
        self.assertEqual(chart.houses, tuple(float(index * 30) for index in range(12)))
        self.assertEqual(chart.angles["ascendant"], 11.0)
        self.assertIsInstance(chart.positions["Sun"], PositionSamples)
        self.assertEqual(len(chart.positions["Sun"].longitude_degrees), 1)
        self.assertEqual(chart.interval.julian_start, fake.calc_calls[0][0])
        self.assertEqual(chart.interval.julian_end, fake.calc_calls[0][0])

    def test_window_mode_samples_every_fifteen_minutes_including_endpoints(self) -> None:
        fake = FakeSwe()

        chart = resolve_subject(window_subject(), swiss_options(), swe_module=fake)

        self.assertEqual(chart.precision_mode, "window")
        self.assertEqual([call[3] for call in fake.julday_calls], [9.0, 9.25, 9.5, 9.75, 10.0])
        self.assertEqual(len(chart.positions["Moon"].longitude_degrees), 5)
        self.assertEqual(fake.house_calls, [])
        self.assertIsNone(chart.houses)
        self.assertEqual(chart.angles, {})
        self.assertEqual(chart.interval.julian_start, fake.calc_calls[0][0])
        self.assertEqual(chart.interval.julian_end, fake.calc_calls[-1][0])

    def test_date_only_mode_samples_both_midnights_and_never_houses(self) -> None:
        fake = FakeSwe()

        chart = resolve_subject(date_only_subject(), swiss_options(), swe_module=fake)

        self.assertEqual(len(fake.julday_calls), 97)
        self.assertEqual(fake.julday_calls[0], (1992, 6, 8, 0.0))
        self.assertEqual(fake.julday_calls[-1], (1992, 6, 9, 0.0))
        self.assertEqual(len(chart.positions["Sun"].longitude_degrees), 97)
        self.assertEqual(fake.house_calls, [])

    def test_polar_house_failure_recommends_defined_systems(self) -> None:
        fake = FakeSwe(house_error="houses: error")

        with self.assertRaisesRegex(EphemerisError, "whole-sign|equal"):
            resolve_subject(polar_subject(), swiss_options(), swe_module=fake)


class BindingFailureTests(unittest.TestCase):
    def test_missing_optional_asteroid_file_is_a_structured_limitation(self) -> None:
        fake = FakeSwe(body_errors=(FakeSwe.CHIRON, FakeSwe.CERES))

        chart = resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

        self.assertNotIn("Chiron", chart.positions)
        self.assertNotIn("Ceres", chart.positions)
        limitations = {item.code: item for item in chart.limitations}
        self.assertIn("optional-ephemeris-data-missing", limitations)
        self.assertIn("positions.Chiron", limitations["optional-ephemeris-data-missing"].affected_fields)

    def test_core_body_failure_is_converted_to_a_concise_domain_error(self) -> None:
        fake = FakeSwe(body_errors=(FakeSwe.SUN,))

        with self.assertRaisesRegex(EphemerisError, "Sun.*missing file"):
            resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

    def test_non_missing_optional_body_error_remains_fatal(self) -> None:
        fake = FakeSwe(body_errors=(FakeSwe.CHIRON,))
        fake.calc_ut_error = "corrupt ephemeris data"

        with self.assertRaisesRegex(EphemerisError, "Chiron.*corrupt"):
            resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

    def test_non_file_not_found_optional_body_error_remains_fatal(self) -> None:
        fake = FakeSwe(body_errors=(FakeSwe.CHIRON,))
        fake.calc_ut_error = "asteroid record not found"

        with self.assertRaisesRegex(EphemerisError, "Chiron.*record not found"):
            resolve_subject(exact_subject(), swiss_options(), swe_module=fake)

    def test_julian_day_binding_error_is_converted_to_domain_error(self) -> None:
        fake = FakeSwe()
        fake.julday_error = "calendar conversion failed"

        with self.assertRaisesRegex(EphemerisError, "Julian day.*calendar conversion failed"):
            resolve_subject(exact_subject(), swiss_options(), swe_module=fake)


if __name__ == "__main__":
    unittest.main()
