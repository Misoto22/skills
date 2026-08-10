from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
SCRIPT = (
    ROOT
    / "plugins"
    / "chinese-metaphysics"
    / "skills"
    / "bazi-compatibility"
    / "scripts"
    / "compute_compatibility.py"
)
sys.path.insert(0, str(SHARED))

from bazi.artifacts import add_checksum, validate_envelope
from bazi.engine import build_chart


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


def birth(name: str, date: str) -> dict:
    return {
        "name": name,
        "birth_place": "Greenwich, United Kingdom",
        "birth_date": date,
        "birth_time": "12:00",
        "calendar": "gregorian",
        "timezone": "UTC",
        "latitude": 51.48,
        "longitude": 0.0,
    }


def load_script():
    spec = importlib.util.spec_from_file_location("bazi_compute_compatibility", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComputeCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = load_script()
        cls.ephemeris = MeanSolarEphemeris()

    def run_main(self, request: dict, output: Path):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = self.script.main(
                ["--json", json.dumps(request), "--out", str(output)],
                ephemeris_factory=lambda path=None: self.ephemeris,
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def write_chart(self, directory: Path, name: str, date: str) -> Path:
        path = directory / f"{name}.json"
        path.write_text(
            json.dumps(build_chart(birth(name, date), self.ephemeris), ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def assert_success(self, code: int, stdout: str, stderr: str) -> dict:
        self.assertEqual(code, 0, stderr)
        paths = [Path(line) for line in stdout.strip().splitlines()]
        self.assertEqual([path.suffix for path in paths], [".json", ".md"])
        return validate_envelope(json.loads(paths[0].read_text(encoding="utf-8")))

    def test_chart_plus_chart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = self.write_chart(root, "Left", "1990-03-14")
            right = self.write_chart(root, "Right", "1992-06-08")
            code, stdout, stderr = self.run_main(
                {"left": {"chart_path": str(left)}, "right": {"chart_path": str(right)}},
                root / "out",
            )
            result = self.assert_success(code, stdout, stderr)
            self.assertEqual(result["people"]["left"]["name"], "Left")

    def test_raw_plus_raw_and_chart_plus_raw(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests = [
                {
                    "left": {"birth": birth("Left", "1990-03-14")},
                    "right": {"birth": birth("Right", "1992-06-08")},
                },
                {
                    "left": {"chart_path": str(self.write_chart(root, "Left", "1990-03-14"))},
                    "right": {"birth": birth("Right", "1992-06-08")},
                },
            ]
            for index, request in enumerate(requests):
                with self.subTest(index=index):
                    result = self.assert_success(*self.run_main(request, root / f"out-{index}"))
                    self.assertIn("general", result["scores"])

    def test_invalid_checksum_and_schema_version_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = build_chart(birth("Left", "1990-03-14"), self.ephemeris)
            invalids = []
            corrupt = dict(valid)
            corrupt["input"] = {**valid["input"], "name": "Changed"}
            invalids.append(corrupt)
            wrong_version = dict(valid)
            wrong_version["schema_version"] = 2
            invalids.append(add_checksum(wrong_version))

            for index, invalid in enumerate(invalids):
                chart_path = root / f"invalid-{index}.json"
                chart_path.write_text(json.dumps(invalid), encoding="utf-8")
                output = root / f"out-{index}"
                code, stdout, stderr = self.run_main(
                    {"left": {"chart_path": str(chart_path)}, "right": {"birth": birth("R", "1992-06-08")}},
                    output,
                )
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertTrue("checksum" in stderr or "version" in stderr)
                self.assertFalse(output.exists())

    def test_collision_safe_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = {
                "left": {"birth": birth("A", "1990-03-14")},
                "right": {"birth": birth("B", "1992-06-08")},
            }
            second = {**first, "relationship_type": "work"}
            one = self.assert_success(*self.run_main(first, output))
            two = self.assert_success(*self.run_main(second, output))
            self.assertNotEqual(one["checksum"], two["checksum"])
            self.assertEqual(len(list(output.glob("*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
