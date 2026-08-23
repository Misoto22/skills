"""End-to-end tests for the natal calculator and the gate its reading skill runs."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASTROLOGY = ROOT / "plugins" / "astrology"
COMPUTE = ASTROLOGY / "skills" / "natal-chart" / "scripts" / "compute_natal.py"
VALIDATE = ASTROLOGY / "skills" / "natal-reading" / "scripts" / "validate_natal.py"
sys.path.insert(0, str(ASTROLOGY / "shared"))

REQUEST = {
    "name": "Subject A",
    "birth": {
        "date": "1988-04-11",
        "time_mode": "exact",
        "time": "09:15",
        "time_accuracy_minutes": 0,
        "timezone": "Asia/Shanghai",
        "latitude": 31.23,
        "longitude": 121.47,
    },
    # Moshier is the built-in analytical backend: no data files, and the
    # artifact records the fallback so a reading can report which produced it.
    "options": {"ephemeris_policy": "allow-moshier"},
}


def swiss_binding_available() -> bool:
    try:
        import swisseph  # noqa: F401
    except ImportError:
        return False
    return True


def run(script: Path, *arguments: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )


@unittest.skipUnless(swiss_binding_available(), "pyswisseph is not installed")
class ComputeNatalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        result = run(COMPUTE, "--json", json.dumps(REQUEST), "--out", cls._directory.name)
        if result.returncode != 0:
            raise AssertionError(f"the calculator refused its own example:\n{result.stderr}")
        cls.paths = [Path(line) for line in result.stdout.strip().splitlines()]
        cls.envelope = json.loads(cls.paths[0].read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_it_writes_a_verifiable_pair(self) -> None:
        from astro.natal_envelope import validate_envelope

        self.assertEqual(len(self.paths), 2)
        self.assertTrue(all(path.is_file() for path in self.paths))
        validate_envelope(self.envelope)
        self.assertEqual(self.envelope["schema"], "astrology.natal-chart")
        self.assertIn(self.envelope["checksum"], self.paths[1].read_text(encoding="utf-8"))

    def test_a_natal_chart_has_houses_angles_and_sect(self) -> None:
        """The three things an inexact time cannot produce, which is why it is refused."""

        self.assertEqual(len(self.envelope["houses"]["cusps"]), 12)
        angles = {angle["name"] for angle in self.envelope["angles"]}
        self.assertIn("ascendant", angles)
        self.assertIn("medium_coeli", angles)
        self.assertIn("diurnal", self.envelope["sect"])
        self.assertTrue(self.envelope["sect"]["basis"])

    def test_every_position_carries_what_a_reading_weights_by(self) -> None:
        self.assertTrue(self.envelope["positions"])
        for position in self.envelope["positions"]:
            with self.subTest(body=position.get("body")):
                for field in ("body", "sign", "house", "retrograde", "dignities", "critical_degree"):
                    self.assertIn(field, position)
                self.assertIn(position["house"], range(1, 13))

    def test_each_aspect_pair_appears_once_and_none_is_self_aspecting(self) -> None:
        """A chart compared with itself yields every pair twice plus self-conjunctions."""

        seen: set[tuple[str, ...]] = set()
        for aspect in self.envelope["aspects"]:
            self.assertNotEqual(aspect["left"], aspect["right"])
            pair = (*sorted((aspect["left"], aspect["right"])), aspect["kind"])
            self.assertNotIn(pair, seen)
            seen.add(pair)

    def test_lots_are_complete_or_absent_never_partial(self) -> None:
        lots = self.envelope["lots"]
        self.assertIsInstance(lots, list)
        if lots:
            self.assertEqual(len(lots), 6, "the classical set is six; a partial set is misleading")

    def test_unavailable_bodies_are_recorded_rather_than_dropped(self) -> None:
        """A shorter table that looks complete is the failure this prevents."""

        codes = {item["code"] for item in self.envelope["limitations"]}
        self.assertIn("ephemeris-fallback", codes, "the Moshier fallback must be recorded")
        for item in self.envelope["limitations"]:
            self.assertTrue(item["message"].strip())

    def test_an_inexact_time_is_refused_rather_than_filled_in(self) -> None:
        for mode, birth in (
            ("window", {"time_mode": "window", "time_window": {"start": "08:00", "end": "11:00"}}),
            ("date-only", {"time_mode": "date-only"}),
        ):
            request = copy.deepcopy(REQUEST)
            request["birth"] = {
                "date": "1988-04-11",
                "timezone": "Asia/Shanghai",
                **birth,
            }
            with tempfile.TemporaryDirectory() as directory, self.subTest(mode=mode):
                result = run(COMPUTE, "--json", json.dumps(request), "--out", directory)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(list(Path(directory).iterdir()), [], "a refused request wrote a file")

    def test_a_missing_name_is_refused(self) -> None:
        request = copy.deepcopy(REQUEST)
        del request["name"]
        with tempfile.TemporaryDirectory() as directory:
            result = run(COMPUTE, "--json", json.dumps(request), "--out", directory)
            self.assertEqual(result.returncode, 2)
            self.assertIn("name", result.stderr)

    def test_rerunning_the_same_request_reuses_the_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = run(COMPUTE, "--json", json.dumps(REQUEST), "--out", directory)
            second = run(COMPUTE, "--json", json.dumps(REQUEST), "--out", directory)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)


@unittest.skipUnless(swiss_binding_available(), "pyswisseph is not installed")
class ValidateNatalTests(unittest.TestCase):
    """The seam: what the calculator emits is what the reading gate accepts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        result = run(COMPUTE, "--json", json.dumps(REQUEST), "--out", cls._directory.name)
        cls.artifact = Path(result.stdout.strip().splitlines()[0])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_the_gate_accepts_a_real_artifact(self) -> None:
        result = run(VALIDATE, str(self.artifact))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_ledger_is_keyed_by_the_ids_a_reading_cites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "ledger.json"
            result = run(VALIDATE, str(self.artifact), "--out", str(ledger_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            keys = ledger["evidence"].keys()
            self.assertTrue(any(key.startswith("[B-") for key in keys), "no body evidence")
            self.assertTrue(any(key.startswith("[A-") for key in keys), "no angle evidence")
            self.assertTrue(any(key.startswith("[X-") for key in keys), "no aspect evidence")
            self.assertIn("[S-sect]", keys)

    def test_every_kind_of_tampering_is_refused(self) -> None:
        original = json.loads(self.artifact.read_text(encoding="utf-8"))
        mutations = {
            "a placement's sign": lambda d: d["positions"][0].__setitem__("sign", "Leo"),
            "a placement's house": lambda d: d["positions"][0].__setitem__("house", 7),
            "an aspect orb": lambda d: d["aspects"][0].__setitem__("orb", 9.9),
            "the subject's name": lambda d: d["subject"].__setitem__("name", "Someone Else"),
            "the sect": lambda d: d["sect"].__setitem__("diurnal", not d["sect"]["diurnal"]),
        }
        for description, mutate in mutations.items():
            tampered = copy.deepcopy(original)
            mutate(tampered)
            with self.subTest(tampered=description):
                result = run(VALIDATE, "-", stdin=json.dumps(tampered))
                self.assertEqual(result.returncode, 2, f"{description} was accepted")
                self.assertIn("checksum", result.stderr)

    def test_a_structural_defect_is_named_before_the_checksum(self) -> None:
        """A missing house is more useful to report than a hash that no longer matches."""

        broken = json.loads(self.artifact.read_text(encoding="utf-8"))
        del broken["positions"][0]["house"]
        result = run(VALIDATE, "-", stdin=json.dumps(broken))
        self.assertEqual(result.returncode, 2)
        self.assertIn("house", result.stderr)

    def test_a_self_aspect_is_refused(self) -> None:
        broken = json.loads(self.artifact.read_text(encoding="utf-8"))
        broken["aspects"].append({"left": "Sun", "right": "Sun", "kind": "conjunction", "orb": 0.0})
        result = run(VALIDATE, "-", stdin=json.dumps(broken))
        self.assertEqual(result.returncode, 2)
        self.assertIn("aspects itself", result.stderr)


if __name__ == "__main__":
    unittest.main()
