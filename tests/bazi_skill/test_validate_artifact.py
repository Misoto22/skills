"""The BaZi gates as a skill runs them: a subprocess, an exit code, a named defect.

Run as a subprocess rather than imported, because the thing most likely to break
is not the logic — it is the two lines that put the *vendored* `shared/` on the
path. A skill directory is copied out on its own, so a gate that only resolves
from this repository's tree is a gate that fails on every installed copy.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "chinese-metaphysics"
sys.path.insert(0, str(PLUGIN / "shared"))

from bazi.artifacts import add_checksum
from bazi.compatibility import compare_charts
from bazi.engine import build_chart

from bazi_skill.ephemeris_double import MeanSolarEphemeris

CHART_GATES = ("bazi-chart", "bazi-reading")
COMPATIBILITY_GATES = ("bazi-compatibility", "bazi-compatibility-reading")


def gate(skill: str) -> Path:
    return PLUGIN / "skills" / skill / "scripts" / "validate_artifact.py"


def run(skill: str, *arguments: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(gate(skill)), *arguments],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )


def birth(name: str, birth_date: str, birth_time: str = "12:00") -> dict:
    return {
        "name": name,
        "birth_place": "Greenwich, United Kingdom",
        "birth_date": birth_date,
        "birth_time": birth_time,
        "calendar": "gregorian",
        "timezone": "UTC",
        "latitude": 51.48,
        "longitude": 0.0,
    }


class ChartGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        cls.chart = build_chart(birth("Subject A", "1990-03-14"), ephemeris)

    def test_every_chart_gate_ships_and_accepts_a_real_chart(self) -> None:
        for skill in CHART_GATES:
            with self.subTest(skill=skill):
                self.assertTrue(gate(skill).is_file(), f"{skill} ships no validate_artifact.py")
                result = run(skill, "-", stdin=json.dumps(self.chart, ensure_ascii=False))

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Subject A", result.stdout)
                self.assertIn(self.chart["checksum"], result.stdout)

    def test_a_chart_read_off_disk_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chart.json"
            path.write_text(json.dumps(self.chart, ensure_ascii=False), encoding="utf-8")
            result = run("bazi-reading", str(path))

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_missing_hour_pillar_exits_two_and_names_the_field(self) -> None:
        """The completion criterion the prose stated and nothing could meet."""

        broken = copy.deepcopy(self.chart)
        del broken["pillars"]["primary"]["hour"]
        result = run("bazi-reading", "-", stdin=json.dumps(add_checksum(broken), ensure_ascii=False))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("pillars.primary.hour", result.stderr)

    def test_a_tampered_chart_exits_two_and_names_the_checksum(self) -> None:
        tampered = copy.deepcopy(self.chart)
        tampered["scores"]["primary"]["day_master_strength"]["score"] = 99.0
        result = run("bazi-reading", "-", stdin=json.dumps(tampered, ensure_ascii=False))

        self.assertEqual(result.returncode, 2)
        self.assertIn("checksum", result.stderr)

    def test_the_reading_gate_routes_a_defect_back_to_the_calculator(self) -> None:
        result = run("bazi-reading", "-", stdin="{}")

        self.assertEqual(result.returncode, 2)
        self.assertIn("bazi-chart", result.stderr)

    def test_the_calculator_gate_stops_the_hand_off_rather_than_routing_to_itself(self) -> None:
        result = run("bazi-chart", "-", stdin="{}")

        self.assertEqual(result.returncode, 2)
        self.assertIn("do not invoke `bazi-reading`", result.stderr)

    def test_a_file_that_is_not_json_exits_two_rather_than_crashing(self) -> None:
        result = run("bazi-reading", "-", stdin="not json at all")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_a_json_array_is_refused(self) -> None:
        result = run("bazi-reading", "-", stdin="[]")

        self.assertEqual(result.returncode, 2)
        self.assertIn("one JSON object", result.stderr)

    def test_a_missing_file_exits_two_rather_than_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run("bazi-reading", str(Path(directory) / "absent.json"))

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")


class CompatibilityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        left = build_chart(birth("Subject A", "1990-03-14"), ephemeris)
        right = build_chart(birth("Subject B", "1992-06-08"), ephemeris)
        cls.comparison = compare_charts(left, right, "marriage")
        cls.chart = left

    def test_every_comparison_gate_ships_and_accepts_a_real_comparison(self) -> None:
        for skill in COMPATIBILITY_GATES:
            with self.subTest(skill=skill):
                self.assertTrue(gate(skill).is_file(), f"{skill} ships no validate_artifact.py")
                result = run(skill, "-", stdin=json.dumps(self.comparison, ensure_ascii=False))

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Subject A and Subject B", result.stdout)

    def test_a_general_score_its_dimensions_do_not_produce_exits_two(self) -> None:
        broken = copy.deepcopy(self.comparison)
        broken["scores"]["general"] = round(broken["scores"]["general"] + 12.0, 2)
        result = run(
            "bazi-compatibility-reading", "-", stdin=json.dumps(add_checksum(broken), ensure_ascii=False)
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("scores.general", result.stderr)

    def test_a_chart_handed_to_the_comparison_gate_is_refused(self) -> None:
        """Each gate names the one artifact its skill reads, so a mix-up stops here."""

        result = run("bazi-compatibility-reading", "-", stdin=json.dumps(self.chart, ensure_ascii=False))

        self.assertEqual(result.returncode, 2)
        self.assertIn("chinese-metaphysics.bazi-compatibility", result.stderr)


if __name__ == "__main__":
    unittest.main()
