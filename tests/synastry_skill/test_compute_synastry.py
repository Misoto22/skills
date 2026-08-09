from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

import compute_synastry  # type: ignore[import-not-found]
from ephemeris import EphemerisError  # type: ignore[import-not-found]
from synastry_schema import validate_artifact  # type: ignore[import-not-found]

from tests.synastry_skill.test_artifact import exact_charts
from tests.synastry_skill.test_request_schema import exact_request


def resolver(subject: object, options: object) -> object:
    del options
    return {chart.subject_id: chart for chart in exact_charts()}[subject.id]


class CalculatorCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, argv: list[str], selected_resolver: object = resolver) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = compute_synastry.main(argv, resolver=selected_resolver)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_json_cli_writes_one_valid_canonical_artifact_without_echoing_birth_data(self) -> None:
        payload = exact_request()

        with patch.object(compute_synastry, "set_ephemeris_path") as configured:
            code, stdout, stderr = self.invoke(["--json", json.dumps(payload), "--out", str(self.directory)])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        configured.assert_called_once_with(None)
        written = Path(stdout.removeprefix("wrote ").strip())
        self.assertEqual(written.parent, self.directory)
        self.assertEqual(written.suffix, ".json")
        document = json.loads(written.read_bytes())
        self.assertEqual(validate_artifact(document), document)
        self.assertEqual(document["provenance"]["actual_backend"], "swiss")
        self.assertNotIn("1990-03-14", stdout)
        self.assertNotIn("07:42", stdout)

    def test_ephemeris_path_is_routed_and_overwrite_must_be_explicit(self) -> None:
        inline = json.dumps(exact_request())

        with patch.object(compute_synastry, "set_ephemeris_path") as configured:
            first_code, first_stdout, _ = self.invoke(
                ["--json", inline, "--out", str(self.directory), "--ephemeris-path", "/ephe"]
            )
            second_code, _, second_stderr = self.invoke(
                ["--json", inline, "--out", str(self.directory), "--ephemeris-path", "/ephe"]
            )
            third_code, third_stdout, third_stderr = self.invoke(
                [
                    "--json",
                    inline,
                    "--out",
                    str(self.directory),
                    "--ephemeris-path",
                    "/ephe",
                    "--overwrite",
                ]
            )

        self.assertEqual((first_code, second_code, third_code), (0, 2, 0))
        self.assertEqual(configured.call_count, 3)
        configured.assert_called_with("/ephe")
        self.assertIn("--overwrite", second_stderr)
        self.assertEqual(third_stderr, "")
        self.assertEqual(first_stdout, third_stdout)

    def test_v1_flat_request_and_txt_reading_input_are_rejected_without_tracebacks(self) -> None:
        legacy = {
            "people": [
                {"name": "Alex", "date": "1990-03-14", "time": "07:42"},
                {"name": "Morgan", "date": "1992-06-08", "time": "12:15"},
            ]
        }
        reading = self.directory / "existing-reading.txt"
        reading.write_text(json.dumps(exact_request()), encoding="utf-8")

        with patch.object(compute_synastry, "set_ephemeris_path"):
            legacy_code, legacy_stdout, legacy_stderr = self.invoke(
                ["--json", json.dumps(legacy), "--out", str(self.directory)]
            )
            text_code, text_stdout, text_stderr = self.invoke(
                ["--request", str(reading), "--out", str(self.directory)]
            )

        self.assertEqual((legacy_code, text_code), (2, 2))
        self.assertEqual((legacy_stdout, text_stdout), ("", ""))
        self.assertNotIn("Traceback", legacy_stderr + text_stderr)
        self.assertNotIn("1990-03-14", legacy_stderr + text_stderr)
        self.assertNotIn("07:42", legacy_stderr + text_stderr)
        self.assertIn("TXT", text_stderr)

    def test_ephemeris_failure_keeps_safe_remediation_without_echoing_coordinates(self) -> None:
        def polar_failure(subject: object, options: object) -> object:
            del subject, options
            raise EphemerisError(
                "could not calculate placidus houses at latitude 72.5; "
                "choose whole-sign or equal houses explicitly"
            )

        with patch.object(compute_synastry, "set_ephemeris_path"):
            code, stdout, stderr = self.invoke(
                ["--json", json.dumps(exact_request()), "--out", str(self.directory)],
                selected_resolver=polar_failure,
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("whole-sign or equal", stderr)
        self.assertNotIn("72.5", stderr)

    def test_request_file_io_error_returns_two_without_a_traceback(self) -> None:
        missing = self.directory / "missing.json"

        code, stdout, stderr = self.invoke(["--request", str(missing), "--out", str(self.directory)])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("error:", stderr)
        self.assertNotIn("Traceback", stderr)


if __name__ == "__main__":
    unittest.main()
