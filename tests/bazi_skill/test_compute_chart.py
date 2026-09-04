from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
SCRIPT = ROOT / "plugins" / "chinese-metaphysics" / "skills" / "bazi-chart" / "scripts" / "compute_chart.py"
sys.path.insert(0, str(SHARED))

from bazi.artifacts import validate_envelope
from bazi.ephemeris import EphemerisUnavailable

from bazi_skill.ephemeris_double import MeanSolarEphemeris

VALID = {
    "name": "张三",
    "birth_place": "Shanghai, China",
    "birth_date": "1990-03-14",
    "birth_time": "07:42",
    "calendar": "gregorian",
    "timezone": "Asia/Shanghai",
    "latitude": 31.23,
    "longitude": 121.47,
}


def load_script():
    spec = importlib.util.spec_from_file_location("bazi_compute_chart", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComputeChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = load_script()

    def run_main(self, arguments: list[str], factory=lambda path=None: MeanSolarEphemeris()):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = self.script.main(arguments, ephemeris_factory=factory)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_inline_json_writes_both_validated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, stdout, stderr = self.run_main(
                ["--json", json.dumps(VALID, ensure_ascii=False), "--out", directory]
            )

            self.assertEqual(code, 0, stderr)
            paths = [Path(line) for line in stdout.strip().splitlines()]
            self.assertEqual([path.suffix for path in paths], [".json", ".md"])
            payload = validate_envelope(json.loads(paths[0].read_text(encoding="utf-8")))
            self.assertEqual(payload["input"]["name"], "张三")
            self.assertEqual(
                set(payload["pillars"]["primary"]),
                {"year", "month", "day", "hour", "boundaries"},
            )

    def test_request_file_and_output_directory_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.json"
            request.write_text(json.dumps(VALID), encoding="utf-8")
            output = root / "nested" / "output"

            code, stdout, stderr = self.run_main(["--request", str(request), "--out", str(output)])

            self.assertEqual(code, 0, stderr)
            self.assertTrue(output.is_dir())
            self.assertTrue(all(Path(line).is_file() for line in stdout.strip().splitlines()))

    def test_invalid_input_exits_two_without_partial_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = {**VALID, "birth_time": "around seven"}
            code, stdout, stderr = self.run_main(["--json", json.dumps(invalid), "--out", directory])

            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("HH:MM", stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_ephemeris_is_actionable_and_writes_nothing(self) -> None:
        def missing(path=None):
            raise EphemerisUnavailable("install pyswisseph")

        with tempfile.TemporaryDirectory() as directory:
            code, stdout, stderr = self.run_main(
                ["--json", json.dumps(VALID), "--out", directory], factory=missing
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("pyswisseph", stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
