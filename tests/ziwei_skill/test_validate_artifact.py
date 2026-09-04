"""The Zi Wei and cross-reading gates as a skill runs them.

The cross gate is the one that carries a rule no single artifact can hold: two
charts have to be one person's. It is tested here rather than beside the Zi Wei
rules because it is the only gate that reads two files, and the order it does
that in is itself a decision — a pairing report over a chart that is already
broken names the wrong problem.
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
from bazi.engine import build_chart
from bazi_skill.ephemeris_double import MeanSolarEphemeris
from ziwei.engine import build_chart as place_chart

ZIWEI_GATES = ("ziwei-chart", "ziwei-reading")
BIRTH = {
    "name": "Subject A",
    "birth_place": "Greenwich, United Kingdom",
    "birth_date": "1990-03-14",
    "birth_time": "09:15",
    "calendar": "gregorian",
    "timezone": "UTC",
    "latitude": 51.48,
    "longitude": 0.0,
    "gender": "male",
}
CHART_BIRTH = {key: value for key, value in BIRTH.items() if key != "gender"}


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


def written(directory: str, name: str, envelope: dict) -> str:
    path = Path(directory) / name
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    return str(path)


class ZiweiGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chart = place_chart(dict(BIRTH), MeanSolarEphemeris())

    def test_every_ziwei_gate_ships_and_accepts_a_real_chart(self) -> None:
        for skill in ZIWEI_GATES:
            with self.subTest(skill=skill):
                self.assertTrue(gate(skill).is_file(), f"{skill} ships no validate_artifact.py")
                result = run(skill, "-", stdin=json.dumps(self.chart, ensure_ascii=False))

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Subject A", result.stdout)
                self.assertIn(self.chart["checksum"], result.stdout)

    def test_a_missing_palace_exits_two_and_names_the_field(self) -> None:
        broken = copy.deepcopy(self.chart)
        del broken["chart"]["primary"]["palaces"][3]
        result = run("ziwei-reading", "-", stdin=json.dumps(add_checksum(broken), ensure_ascii=False))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("twelve palaces", result.stderr)

    def test_a_transformation_on_an_unplaced_star_exits_two(self) -> None:
        broken = copy.deepcopy(self.chart)
        broken["chart"]["primary"]["transformations"]["placed"].append(
            {"star": "無此星", "label": "禄", "palace": "子"}
        )
        result = run("ziwei-reading", "-", stdin=json.dumps(add_checksum(broken), ensure_ascii=False))

        self.assertEqual(result.returncode, 2)
        self.assertIn("sits in no palace", result.stderr)

    def test_the_reading_gate_routes_a_defect_back_to_the_placer(self) -> None:
        result = run("ziwei-reading", "-", stdin="{}")

        self.assertEqual(result.returncode, 2)
        self.assertIn("ziwei-chart", result.stderr)

    def test_the_placer_gate_stops_the_hand_off_rather_than_routing_to_itself(self) -> None:
        result = run("ziwei-chart", "-", stdin="{}")

        self.assertEqual(result.returncode, 2)
        self.assertIn("do not invoke `ziwei-reading`", result.stderr)


class CrossGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ephemeris = MeanSolarEphemeris()
        cls.bazi = build_chart(dict(CHART_BIRTH), cls.ephemeris)
        cls.ziwei = place_chart(dict(BIRTH), cls.ephemeris)

    def test_it_accepts_two_charts_for_one_person_at_one_moment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "bazi-ziwei-cross",
                written(directory, "bazi.json", self.bazi),
                written(directory, "ziwei.json", self.ziwei),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(self.bazi["checksum"], result.stdout)
            self.assertIn(self.ziwei["checksum"], result.stdout)

    def test_two_charts_for_different_moments_are_refused(self) -> None:
        """Each artifact is impeccable alone; only the pair is wrong."""

        other = build_chart(dict(CHART_BIRTH) | {"birth_time": "20:30"}, self.ephemeris)
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "bazi-ziwei-cross",
                written(directory, "bazi.json", other),
                written(directory, "ziwei.json", self.ziwei),
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("input.birth_time", result.stderr)
            self.assertIn("not one person at one moment", result.stderr)

    def test_the_sources_are_refused_in_the_order_they_are_given(self) -> None:
        """A pairing report over a broken chart would name the wrong problem."""

        broken = copy.deepcopy(self.bazi)
        del broken["pillars"]["primary"]["hour"]
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "bazi-ziwei-cross",
                written(directory, "bazi.json", add_checksum(broken)),
                written(directory, "ziwei.json", self.ziwei),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("bazi source", result.stderr)
            self.assertIn("pillars.primary.hour", result.stderr)
            self.assertIn("bazi-chart", result.stderr)
            self.assertNotIn("one person at one moment", result.stderr)

    def test_the_two_sources_cannot_be_given_the_wrong_way_round(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "bazi-ziwei-cross",
                written(directory, "ziwei.json", self.ziwei),
                written(directory, "bazi.json", self.bazi),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("chinese-metaphysics.bazi-chart", result.stderr)

    def test_a_ziwei_defect_routes_back_to_the_placer(self) -> None:
        broken = copy.deepcopy(self.ziwei)
        del broken["chart"]["primary"]["palaces"][0]
        with tempfile.TemporaryDirectory() as directory:
            result = run(
                "bazi-ziwei-cross",
                written(directory, "bazi.json", self.bazi),
                written(directory, "ziwei.json", add_checksum(broken)),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("ziwei source", result.stderr)
            self.assertIn("ziwei-chart", result.stderr)


if __name__ == "__main__":
    unittest.main()
