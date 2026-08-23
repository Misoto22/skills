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
SCRIPT = ROOT / "plugins" / "chinese-metaphysics" / "skills" / "ziwei-chart" / "scripts" / "compute_ziwei.py"
sys.path.insert(0, str(SHARED))

from bazi.artifacts import validate_envelope
from bazi.ephemeris import EphemerisUnavailable, SwissEphemeris

VALID = {
    "name": "张三",
    "birth_place": "Shanghai, China",
    "birth_date": "2000-01-01",
    "birth_time": "12:00",
    "calendar": "gregorian",
    "timezone": "Asia/Shanghai",
    "latitude": 31.23,
    "longitude": 121.47,
    "gender": "male",
}


def load_script():
    spec = importlib.util.spec_from_file_location("ziwei_compute_chart", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def swiss_available() -> bool:
    try:
        SwissEphemeris()
    except EphemerisUnavailable:
        return False
    return True


def run(request, directory, *, factory=SwissEphemeris):
    module = load_script()
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = module.main(
            ["--json", json.dumps(request), "--out", str(directory)],
            ephemeris_factory=factory,
        )
    return code, out.getvalue().splitlines(), err.getvalue()


@unittest.skipUnless(swiss_available(), "pyswisseph is not installed")
class ComputeZiweiTests(unittest.TestCase):
    def test_a_valid_request_writes_a_verifiable_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            code, paths, _ = run(VALID, directory)
            self.assertEqual(code, 0)
            self.assertEqual(len(paths), 2)
            json_path, markdown_path = (Path(item) for item in paths)
            self.assertTrue(json_path.is_file() and markdown_path.is_file())

            envelope = json.loads(json_path.read_text(encoding="utf-8"))
            validate_envelope(envelope)
            self.assertEqual(envelope["schema"], "chinese-metaphysics.ziwei-chart")
            self.assertEqual(envelope["schema_version"], 1)
            self.assertIn(envelope["checksum"], markdown_path.read_text(encoding="utf-8"))

    def test_the_known_chart_places_ziwei_in_wu(self):
        with tempfile.TemporaryDirectory() as directory:
            _, paths, _ = run(VALID, directory)
            chart = json.loads(Path(paths[0]).read_text(encoding="utf-8"))["chart"]["primary"]
            self.assertEqual(chart["lunar"]["month"], 11)
            self.assertEqual(chart["lunar"]["day"], 25)
            self.assertEqual(chart["year_pillar"]["text"], "己卯")
            self.assertEqual(chart["bureau"]["name"], "土五局")
            self.assertEqual(chart["life_palace"]["branch"], "午")
            in_wu = {star["name"] for star in chart["palaces"][6]["stars"]}
            self.assertIn("紫微", in_wu)

    def test_every_palace_is_present_and_named(self):
        with tempfile.TemporaryDirectory() as directory:
            _, paths, _ = run(VALID, directory)
            chart = json.loads(Path(paths[0]).read_text(encoding="utf-8"))["chart"]["primary"]
            self.assertEqual(len(chart["palaces"]), 12)
            self.assertEqual(len({palace["name"] for palace in chart["palaces"]}), 12)
            self.assertEqual(sum(palace["is_life_palace"] for palace in chart["palaces"]), 1)
            self.assertEqual(sum(palace["is_body_palace"] for palace in chart["palaces"]), 1)
            self.assertEqual(len(chart["decades"]), 12)

    def test_a_late_zi_birth_emits_a_complete_alternate(self):
        with tempfile.TemporaryDirectory() as directory:
            _, paths, _ = run(VALID | {"birth_time": "23:30"}, directory)
            envelope = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
            self.assertTrue(envelope["sensitivity"]["alternate_day_boundary"])
            alternate = envelope["chart"]["alternate"]
            self.assertIsNotNone(alternate)
            self.assertEqual(len(alternate["palaces"]), 12)
            self.assertNotEqual(envelope["chart"]["primary"]["lunar"]["day"], alternate["lunar"]["day"])

    def test_a_daytime_birth_has_no_alternate(self):
        with tempfile.TemporaryDirectory() as directory:
            _, paths, _ = run(VALID, directory)
            envelope = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
            self.assertFalse(envelope["sensitivity"]["alternate_day_boundary"])
            self.assertIsNone(envelope["chart"]["alternate"])

    def test_a_lunar_request_resolves_before_placement(self):
        with tempfile.TemporaryDirectory() as directory:
            request = VALID | {"birth_date": "1999-11-25", "calendar": "lunar", "leap_month": False}
            code, paths, _ = run(request, directory)
            self.assertEqual(code, 0)
            envelope = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
            self.assertEqual(envelope["calendar"]["resolved_gregorian_date"], "2000-01-01")

    def test_missing_gender_is_refused_with_an_explanation(self):
        with tempfile.TemporaryDirectory() as directory:
            code, paths, error = run(VALID | {"gender": None}, directory)
            self.assertEqual(code, 2)
            self.assertEqual(paths, [])
            self.assertIn("gender", error)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_an_approximate_time_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            code, _, error = run(VALID | {"birth_time": "12"}, directory)
            self.assertEqual(code, 2)
            self.assertIn("birth_time", error)

    def test_rerunning_the_same_request_reuses_the_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            _, first, _ = run(VALID, directory)
            _, second, _ = run(VALID, directory)
            self.assertEqual(first, second)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)


class ComputeZiweiDependencyTests(unittest.TestCase):
    def test_a_missing_ephemeris_reports_the_install_error(self):
        def unavailable(_path):
            raise EphemerisUnavailable("pyswisseph is required for BaZi astronomy")

        with tempfile.TemporaryDirectory() as directory:
            code, paths, error = run(VALID, directory, factory=unavailable)
            self.assertEqual(code, 2)
            self.assertEqual(paths, [])
            self.assertIn("pyswisseph", error)


if __name__ == "__main__":
    unittest.main()
