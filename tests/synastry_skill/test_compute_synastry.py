from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
sys.path.insert(0, str(SKILL / "scripts"))

from compute_synastry import (
    RequestError,
    build_chart,
    main,
    output_name,
    parse_request,
    resolve_moment,
)

from .test_report import BODY_ORDER, EQUAL_CUSPS

PERSON_A = {
    "name": "Person A",
    "date": "1990-03-14",
    "time": "07:42",
    "timezone": "Asia/Shanghai",
    "latitude": 31.23,
    "longitude": 121.47,
    "birth_place": "Sample City",
    "residence": "Sample City",
}
PERSON_B = {
    "name": "Person B",
    "date": "1988-11-02",
    "time": "21:05",
    "timezone": "America/New_York",
    "latitude": 40.71,
    "longitude": -74.01,
}


def stub_backend(person) -> dict:
    """What an ephemeris would return, derived from the name so the two charts differ."""

    offset = float(sum(ord(character) for character in person.name) % 360)
    longitudes = {body: (offset + index * 17.0) % 360.0 for index, body in enumerate(BODY_ORDER)}
    longitudes["South_Node"] = (longitudes["North_Node"] + 180.0) % 360.0
    longitudes["Ascendant"] = offset
    longitudes["Descendant"] = (offset + 180.0) % 360.0
    longitudes["Medium_Coeli"] = (offset + 270.0) % 360.0
    longitudes["Imum_Coeli"] = (offset + 90.0) % 360.0
    return {"longitudes": longitudes, "retrograde": ["Mercury"], "cusps": list(EQUAL_CUSPS)}


class ParseRequestTests(unittest.TestCase):
    def test_two_people_are_accepted_under_a_key_or_as_a_bare_list(self) -> None:
        keyed = parse_request({"people": [PERSON_A, PERSON_B]})
        bare = parse_request([PERSON_A, PERSON_B])

        self.assertEqual(keyed[0].name, "Person A")
        self.assertEqual(bare[1].name, "Person B")

    def test_a_request_that_is_not_a_pair_is_refused(self) -> None:
        for payload in ({"people": [PERSON_A]}, {"people": [PERSON_A, PERSON_B, PERSON_A]}, {}, "text"):
            with self.assertRaises(RequestError):
                parse_request(payload)

    def test_every_fault_is_reported_together(self) -> None:
        """One round trip per request. Reporting faults one at a time costs two more."""

        broken = {"name": "", "date": "14/03/1990", "time": "07", "timezone": "", "latitude": 999}
        with self.assertRaises(RequestError) as raised:
            parse_request({"people": [broken, PERSON_B]})

        problems = "\n".join(raised.exception.problems)
        self.assertIn("people[0].name: required", problems)
        self.assertIn("people[0].timezone: required", problems)
        self.assertIn("people[0].longitude: required", problems)
        self.assertIn("expected YYYY-MM-DD", problems)
        self.assertIn("outside ±90", problems)

    def test_an_hour_only_birth_time_is_refused_with_the_reason(self) -> None:
        for stated in ("07", "7am", "07:42:10", "0742"):
            with self.assertRaises(RequestError) as raised:
                parse_request({"people": [{**PERSON_A, "time": stated}, PERSON_B]})
            problems = "\n".join(raised.exception.problems)
            self.assertIn("HH:MM", problems)
            self.assertIn("Ascendant", problems)

    def test_a_non_numeric_coordinate_is_named_rather_than_coerced(self) -> None:
        with self.assertRaises(RequestError) as raised:
            parse_request({"people": [{**PERSON_A, "latitude": "north"}, PERSON_B]})

        self.assertIn("expected a decimal degree", "\n".join(raised.exception.problems))

    def test_an_entry_that_is_not_an_object_is_named(self) -> None:
        with self.assertRaises(RequestError) as raised:
            parse_request({"people": ["Person A", PERSON_B]})

        self.assertIn("people[0]: must be an object", raised.exception.problems)

    def test_optional_fields_fall_back_without_inventing_anything(self) -> None:
        person, _ = parse_request({"people": [PERSON_A, PERSON_B]})
        without = {key: value for key, value in PERSON_A.items() if key != "residence"}
        spare, _ = parse_request({"people": [without, PERSON_B]})

        self.assertEqual(person.residence, "Sample City")
        self.assertEqual(spare.residence, "-")

    def test_the_documented_example_request_still_parses(self) -> None:
        payload = json.loads((SKILL / "references" / "request.example.json").read_text(encoding="utf-8"))
        left, right = parse_request(payload)

        self.assertEqual(left.name, "Person A")
        self.assertEqual(right.timezone, "America/New_York")


class MomentTests(unittest.TestCase):
    def test_the_offset_is_resolved_against_the_birth_date(self) -> None:
        """A remembered constant gets summer time wrong; the zone database does not."""

        summer, _ = parse_request({"people": [{**PERSON_B, "date": "1988-07-02"}, PERSON_A]})
        winter, _ = parse_request({"people": [PERSON_B, PERSON_A]})

        self.assertAlmostEqual(resolve_moment(summer)[1], -4.0)
        self.assertAlmostEqual(resolve_moment(winter)[1], -5.0)

    def test_an_explicit_offset_overrides_the_zone(self) -> None:
        person, _ = parse_request({"people": [{**PERSON_B, "utc_offset_hours": 1.5}, PERSON_A]})
        moment, offset = resolve_moment(person)

        self.assertAlmostEqual(offset, 1.5)
        self.assertEqual((moment.hour, moment.minute), (19, 35))

    def test_local_time_converts_to_the_right_instant(self) -> None:
        person, _ = parse_request({"people": [PERSON_A, PERSON_B]})
        moment, offset = resolve_moment(person)

        self.assertAlmostEqual(offset, 8.0)
        self.assertEqual((moment.year, moment.month, moment.day), (1990, 3, 13))
        self.assertEqual((moment.hour, moment.minute), (23, 42))

    def test_an_unknown_zone_says_how_to_proceed(self) -> None:
        person, _ = parse_request({"people": [{**PERSON_A, "timezone": "Mars/Olympus"}, PERSON_B]})
        with self.assertRaises(RequestError) as raised:
            resolve_moment(person)

        self.assertIn("utc_offset_hours", "\n".join(raised.exception.problems))


class ChartAndNameTests(unittest.TestCase):
    def test_the_chart_carries_the_stated_data_and_the_resolved_offset(self) -> None:
        person, _ = parse_request({"people": [PERSON_A, PERSON_B]})
        built = build_chart(person, stub_backend(person), "placidus")

        self.assertEqual(built["birth_local"], "1990-03-14 07:42")
        self.assertEqual(built["birth_place"], "Sample City")
        self.assertAlmostEqual(built["utc_offset_hours"], 8.0)
        self.assertEqual(len(built["cusps"]), 12)

    def test_bodies_the_backend_could_not_resolve_reach_the_report(self) -> None:
        """A dropped asteroid has to survive the hand-off, or the report cannot say so."""

        person, _ = parse_request({"people": [PERSON_A, PERSON_B]})
        positions = stub_backend(person)
        del positions["longitudes"]["Ceres"]
        positions["unavailable"] = ["Ceres"]

        self.assertEqual(list(build_chart(person, positions, "placidus")["unavailable"]), ["Ceres"])

    def test_a_backend_that_reports_nothing_missing_says_nothing(self) -> None:
        person, _ = parse_request({"people": [PERSON_A, PERSON_B]})

        self.assertEqual(list(build_chart(person, stub_backend(person), "placidus")["unavailable"]), [])

    def test_a_name_cannot_steer_the_output_path(self) -> None:
        left, right = parse_request({"people": [{**PERSON_A, "name": "a/b c"}, {**PERSON_B, "name": " . "}]})

        self.assertEqual(output_name(left, right), "synastry_a-b-c_unnamed.txt")

    def test_a_chinese_name_survives_the_filename(self) -> None:
        left, right = parse_request({"people": [{**PERSON_A, "name": "甲"}, {**PERSON_B, "name": "乙"}]})

        self.assertEqual(output_name(left, right), "synastry_甲_乙.txt")


class CommandLineTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(arguments), backend=stub_backend)
        return code, out.getvalue(), err.getvalue()

    def test_a_valid_request_writes_the_named_file(self) -> None:
        request = self.directory / "request.json"
        request.write_text(json.dumps({"people": [PERSON_A, PERSON_B]}), encoding="utf-8")

        code, stdout, _ = self.run_main("--request", str(request), "--out", str(self.directory))
        written = self.directory / "synastry_Person-A_Person-B.txt"

        self.assertEqual(code, 0)
        self.assertIn(written.name, stdout)
        self.assertIn("Synastry: Person A x Person B", written.read_text(encoding="utf-8"))

    def test_the_output_directory_is_created(self) -> None:
        nested = self.directory / "charts" / "2026"
        code, _, _ = self.run_main(
            "--json", json.dumps({"people": [PERSON_A, PERSON_B]}), "--out", str(nested)
        )

        self.assertEqual(code, 0)
        self.assertTrue((nested / "synastry_Person-A_Person-B.txt").is_file())

    def test_the_language_flag_reaches_the_report(self) -> None:
        code, _, _ = self.run_main(
            "--json",
            json.dumps({"people": [PERSON_A, PERSON_B]}),
            "--out",
            str(self.directory),
            "--language",
            "zh",
        )
        written = (self.directory / "synastry_Person-A_Person-B.txt").read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("合盘", written)

    def test_a_bad_request_exits_two_and_writes_nothing(self) -> None:
        code, _, stderr = self.run_main(
            "--json",
            json.dumps({"people": [{**PERSON_A, "time": "07"}, PERSON_B]}),
            "--out",
            str(self.directory),
        )

        self.assertEqual(code, 2)
        self.assertIn("HH:MM", stderr)
        self.assertEqual(list(self.directory.glob("*.txt")), [])

    def test_unreadable_json_exits_two_rather_than_traces_back(self) -> None:
        code, _, stderr = self.run_main("--json", "{not json", "--out", str(self.directory))

        self.assertEqual(code, 2)
        self.assertIn("cannot read the request", stderr)

    def test_a_missing_request_file_exits_two(self) -> None:
        code, _, stderr = self.run_main(
            "--request", str(self.directory / "absent.json"), "--out", str(self.directory)
        )

        self.assertEqual(code, 2)
        self.assertIn("cannot read the request", stderr)

    def test_an_unknown_zone_reaches_the_command_line_as_an_error(self) -> None:
        payload = {"people": [{**PERSON_A, "timezone": "Mars/Olympus"}, PERSON_B]}
        code, _, stderr = self.run_main("--json", json.dumps(payload), "--out", str(self.directory))

        self.assertEqual(code, 2)
        self.assertIn("utc_offset_hours", stderr)


if __name__ == "__main__":
    unittest.main()
