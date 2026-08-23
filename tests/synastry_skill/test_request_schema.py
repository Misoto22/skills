from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
sys.path.insert(0, str(SKILL / "scripts"))

from astro.request_schema import (  # type: ignore[import-not-found]
    DateOnlyBirth,
    ExactBirth,
    RequestError,
    WindowBirth,
    canonical_request,
    parse_request,
    resolve_interval,
)


def exact_request() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "people": [
            {
                "id": "a",
                "display_name": "Alex",
                "pronouns": "they/them",
                "birth": {
                    "date": "1990-03-14",
                    "time_mode": "exact",
                    "time": "07:42",
                    "time_accuracy_minutes": 5,
                    "timezone": "Europe/Paris",
                    "latitude": 48.86,
                    "longitude": 2.35,
                    "place_label": "Paris",
                    "location_source": "user supplied",
                },
            },
            {
                "id": "b",
                "display_name": "Morgan",
                "birth": {
                    "date": "1992-06-08",
                    "time_mode": "exact",
                    "time": "12:15",
                    "time_accuracy_minutes": 3,
                    "timezone": "America/Los_Angeles",
                    "latitude": 34.05,
                    "longitude": -118.24,
                },
            },
        ],
        "options": {
            "language": "en",
            "house_system": "whole-sign",
            "major_orb": 8.0,
            "minor_orb": 3.0,
            "ephemeris_policy": "swiss-only",
            "calculation_profile": "western-tropical-v1",
            "aspect_profile": "ptolemaic-minor-v1",
            "include_derived": False,
            "privacy": "minimal",
        },
        "relationship_context": {
            "description": "Creative collaborators",
            "requested_domains": ["communication", "creative collaboration"],
        },
    }


def mixed_precision_request() -> dict[str, object]:
    payload = exact_request()
    people = payload["people"]
    assert isinstance(people, list)
    second = people[1]
    assert isinstance(second, dict)
    second["birth"] = {
        "date": "1992-06-08",
        "time_mode": "date-only",
        "timezone": "America/Los_Angeles",
    }
    return payload


class ParseRequestTests(unittest.TestCase):
    def test_valid_instances_for_all_time_modes(self) -> None:
        exact = parse_request(exact_request())
        window_payload = mixed_precision_request()
        people = window_payload["people"]
        assert isinstance(people, list)
        second = people[1]
        assert isinstance(second, dict)
        second["birth"] = {
            "date": "1992-06-08",
            "time_mode": "window",
            "time_window": {"start": "09:00", "end": "11:00"},
            "timezone": "America/Los_Angeles",
        }
        window = parse_request(window_payload)
        date_only = parse_request(mixed_precision_request())

        self.assertIsInstance(exact.people[0].birth, ExactBirth)
        self.assertIsInstance(window.people[1].birth, WindowBirth)
        self.assertIsInstance(date_only.people[1].birth, DateOnlyBirth)

    def test_documented_v2_example_parses(self) -> None:
        payload = json.loads((SKILL / "references" / "request.example.json").read_text(encoding="utf-8"))

        parsed = parse_request(payload)

        self.assertEqual(parsed.people[0].id, "subject-1")
        self.assertEqual(parsed.people[1].birth.mode, "date-only")

    def test_invalid_civil_values_and_non_finite_numbers_are_collected(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        birth.update(date="1990-02-31", time="25:99", latitude=float("nan"), longitude=float("inf"))
        options = payload["options"]
        assert isinstance(options, dict)
        options["major_orb"] = 16.0

        with self.assertRaises(RequestError) as raised:
            parse_request(payload)

        message = "\n".join(raised.exception.problems)
        for expected in ("valid calendar date", "valid 24-hour time", "finite", "major_orb"):
            self.assertIn(expected, message)

    def test_exact_time_requires_declared_accuracy_and_location(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        del birth["time_accuracy_minutes"]

        with self.assertRaisesRegex(RequestError, "time_accuracy_minutes"):
            parse_request(payload)

    def test_window_and_date_only_do_not_require_coordinates(self) -> None:
        parsed = parse_request(mixed_precision_request())

        self.assertEqual(parsed.people[1].birth.mode, "date-only")

    def test_unknown_fields_are_rejected_at_every_object_level(self) -> None:
        cases = (
            (exact_request(), "extra", "request"),
            (exact_request(), "people.0.extra", "people[0]"),
            (exact_request(), "people.0.birth.extra", "people[0].birth"),
            (exact_request(), "options.extra", "options"),
            (exact_request(), "relationship_context.extra", "relationship_context"),
        )
        for payload, target, expected in cases:
            with self.subTest(target=target):
                self._insert_unknown(payload, target)
                with self.assertRaises(RequestError) as raised:
                    parse_request(payload)
                self.assertIn(expected, "\n".join(raised.exception.problems))
                self.assertIn("unknown field", "\n".join(raised.exception.problems))

    def test_invalid_identity_and_label_values_are_rejected(self) -> None:
        cases = (
            ("", "must not be blank"),
            ("\n", "must not be blank"),
            ("a\x00", "control character"),
            ("x" * 121, "at most 120"),
        )
        for value, expected in cases:
            with self.subTest(value=repr(value)):
                payload = exact_request()
                people = payload["people"]
                assert isinstance(people, list)
                first = people[0]
                assert isinstance(first, dict)
                first["id"] = value
                with self.assertRaises(RequestError) as raised:
                    parse_request(payload)
                self.assertIn(expected, "\n".join(raised.exception.problems))

        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        first["display_name"] = "bad\x1f label"
        with self.assertRaisesRegex(RequestError, "control character"):
            parse_request(payload)

    def test_duplicate_ids_are_rejected(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        second = people[1]
        assert isinstance(second, dict)
        second["id"] = "a"

        with self.assertRaisesRegex(RequestError, "duplicate"):
            parse_request(payload)

    def test_override_requires_reason_and_strictly_bounded_offset(self) -> None:
        for offset, reason, expected in (
            (1.5, None, "utc_offset_reason"),
            (-24.0, "historical record", "between -24 and 24"),
            (24.0, "historical record", "between -24 and 24"),
            (float("nan"), "historical record", "finite"),
        ):
            with self.subTest(offset=offset):
                payload = exact_request()
                people = payload["people"]
                assert isinstance(people, list)
                first = people[0]
                assert isinstance(first, dict)
                birth = first["birth"]
                assert isinstance(birth, dict)
                birth["utc_offset_hours"] = offset
                if reason is not None:
                    birth["utc_offset_reason"] = reason
                with self.assertRaises(RequestError) as raised:
                    parse_request(payload)
                self.assertIn(expected, "\n".join(raised.exception.problems))

    def test_orb_bounds_and_profile_strings_are_enforced(self) -> None:
        cases = (
            ("major_orb", -0.1, "from 0 through 15"),
            ("major_orb", 15.1, "from 0 through 15"),
            ("minor_orb", -0.1, "from 0 through 3"),
            ("minor_orb", 3.1, "from 0 through 3"),
            ("calculation_profile", "other", "unsupported profile"),
            ("aspect_profile", "other", "unsupported profile"),
            ("ephemeris_policy", "other", "unsupported"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                payload = exact_request()
                options = payload["options"]
                assert isinstance(options, dict)
                options[field] = value
                with self.assertRaises(RequestError) as raised:
                    parse_request(payload)
                self.assertIn(expected, "\n".join(raised.exception.problems))

    def test_aspect_profile_rejects_positive_orb_overlap(self) -> None:
        payload = exact_request()
        options = payload["options"]
        assert isinstance(options, dict)
        options.update(major_orb=9.1, minor_orb=3.0)

        with self.assertRaises(RequestError) as raised:
            parse_request(payload)

        self.assertIn("overlap", "\n".join(raised.exception.problems))

    def test_aspect_profile_accepts_boundary_ties(self) -> None:
        for major_orb, minor_orb in ((12.0, 0.0), (9.0, 3.0)):
            with self.subTest(major_orb=major_orb, minor_orb=minor_orb):
                payload = exact_request()
                options = payload["options"]
                assert isinstance(options, dict)
                options.update(major_orb=major_orb, minor_orb=minor_orb)

                parsed = parse_request(payload)

                self.assertEqual(parsed.options.major_orb, major_orb)
                self.assertEqual(parsed.options.minor_orb, minor_orb)

    def test_array_and_object_enum_values_are_collected_as_request_errors(self) -> None:
        cases = (
            ("birth.time_mode", [], "expected a string"),
            ("birth.time_mode", {}, "expected a string"),
            ("options.language", [], "expected a string"),
            ("options.house_system", {}, "expected a string"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                payload = exact_request()
                self._set_field(payload, field, value)
                with self.assertRaises(RequestError) as raised:
                    parse_request(payload)
                self.assertIn(expected, "\n".join(raised.exception.problems))

    def test_representational_boundaries_become_request_errors(self) -> None:
        payload = mixed_precision_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        second = people[1]
        assert isinstance(first, dict)
        assert isinstance(second, dict)
        exact_birth = first["birth"]
        date_only_birth = second["birth"]
        assert isinstance(exact_birth, dict)
        assert isinstance(date_only_birth, dict)
        exact_birth["latitude"] = 10**10000
        date_only_birth["date"] = "9999-12-31"
        options = payload["options"]
        assert isinstance(options, dict)
        options["major_orb"] = 10**10000

        with self.assertRaises(RequestError) as raised:
            parse_request(payload)

        message = "\n".join(raised.exception.problems)
        self.assertIn("latitude", message)
        self.assertIn("major_orb", message)
        self.assertIn("date", message)

    def test_near_twenty_four_hour_offset_is_rejected_before_resolution(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        birth.update(
            utc_offset_hours=23.999999999999,
            utc_offset_reason="contemporary local record",
        )

        with self.assertRaises(RequestError) as raised:
            parse_request(payload)

        self.assertIn("utc_offset_hours", "\n".join(raised.exception.problems))

    def test_ambiguous_exact_time_requires_a_fold_or_reasoned_override(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        birth.update(date="2024-11-03", time="01:30", timezone="America/New_York")

        with self.assertRaisesRegex(RequestError, "timezone_fold"):
            parse_request(payload)

    def test_non_ambiguous_exact_time_rejects_timezone_fold(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        birth["timezone_fold"] = 0

        with self.assertRaisesRegex(RequestError, "only for ambiguous"):
            parse_request(payload)

    def test_reasoned_offset_override_resolves_an_ambiguous_exact_time(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        birth.update(
            date="2024-11-03",
            time="01:30",
            timezone="America/New_York",
            utc_offset_hours=-5.0,
            utc_offset_reason="contemporary local record",
        )

        request = parse_request(payload)
        interval = resolve_interval(request.people[0].birth)

        self.assertEqual(interval.start_utc, datetime(2024, 11, 3, 6, 30, tzinfo=UTC))

    def test_nonexistent_exact_time_and_ambiguous_window_are_rejected(self) -> None:
        nonexistent = exact_request()
        people = nonexistent["people"]
        assert isinstance(people, list)
        first = people[0]
        assert isinstance(first, dict)
        birth = first["birth"]
        assert isinstance(birth, dict)
        birth.update(date="2024-03-10", time="02:30", timezone="America/New_York")
        with self.assertRaisesRegex(RequestError, "nonexistent"):
            parse_request(nonexistent)

        ambiguous = mixed_precision_request()
        people = ambiguous["people"]
        assert isinstance(people, list)
        second = people[1]
        assert isinstance(second, dict)
        second["birth"] = {
            "date": "2024-11-03",
            "time_mode": "window",
            "time_window": {"start": "01:00", "end": "02:00"},
            "timezone": "America/New_York",
        }
        with self.assertRaisesRegex(RequestError, "ambiguous"):
            parse_request(ambiguous)

    def test_resolve_interval_and_canonical_request_preserve_v2_semantics(self) -> None:
        request = parse_request(mixed_precision_request())
        exact = resolve_interval(request.people[0].birth)
        date_only = resolve_interval(request.people[1].birth)
        canonical = canonical_request(request)

        self.assertEqual(exact.start_utc, exact.end_utc)
        self.assertEqual(exact.start_utc.tzinfo, UTC)
        self.assertLess(date_only.start_utc, date_only.end_utc)
        self.assertEqual(canonical["schema_version"], "2.0")
        self.assertEqual(canonical["people"][1]["birth"]["time_mode"], "date-only")

    @staticmethod
    def _insert_unknown(payload: dict[str, object], target: str) -> None:
        if target == "extra":
            payload["extra"] = True
            return
        if target == "people.0.extra":
            people = payload["people"]
            assert isinstance(people, list)
            first = people[0]
            assert isinstance(first, dict)
            first["extra"] = True
            return
        if target == "people.0.birth.extra":
            people = payload["people"]
            assert isinstance(people, list)
            first = people[0]
            assert isinstance(first, dict)
            birth = first["birth"]
            assert isinstance(birth, dict)
            birth["extra"] = True
            return
        value = payload[target.removesuffix(".extra")]
        assert isinstance(value, dict)
        value["extra"] = True

    @staticmethod
    def _set_field(payload: dict[str, object], field: str, value: object) -> None:
        if field == "birth.time_mode":
            people = payload["people"]
            assert isinstance(people, list)
            person = people[0]
            assert isinstance(person, dict)
            birth = person["birth"]
            assert isinstance(birth, dict)
            birth["time_mode"] = value
            return
        options = payload["options"]
        assert isinstance(options, dict)
        options[field.removeprefix("options.")] = value


if __name__ == "__main__":
    unittest.main()
