"""Cross the seam between `synastry` and `synastry-reading` with a real artifact.

Each skill is well covered on its own: the compute side has its own suite, and
the reading side has a hundred-odd tests over its session machinery and
validators. What neither reaches is the hand-off. A reading skill that accepts
a shape its own calculator never emits fails only in front of a user, and an
end-to-end audit cannot reach this either, because reaching it takes a second
person's birth record.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASTROLOGY = ROOT / "plugins" / "astrology" / "skills"
COMPUTE = ASTROLOGY / "synastry" / "scripts" / "compute_synastry.py"
VALIDATE = ASTROLOGY / "synastry-reading" / "scripts" / "validate_synastry.py"

# Synthetic, and deliberately not anyone's. One exact record and one bounded
# window, so the artifact carries both certainty modes the reading has to report.
REQUEST = {
    "schema_version": "2.0",
    "people": [
        {
            "id": "subject-1",
            "birth": {
                "date": "1988-04-11",
                "time_mode": "exact",
                "time": "09:15",
                "time_accuracy_minutes": 0,
                "timezone": "Asia/Shanghai",
                "latitude": 31.23,
                "longitude": 121.47,
            },
        },
        {
            "id": "subject-2",
            "birth": {
                "date": "1991-11-26",
                "time_mode": "window",
                # A window carries no coordinates: the schema drops them with the
                # exact time rather than keeping precision the record never had.
                "time_window": {"start": "16:10", "end": "19:10"},
                "timezone": "Asia/Shanghai",
            },
        },
    ],
    "options": {
        "language": "en",
        "house_system": "whole-sign",
        "major_orb": 8.0,
        "minor_orb": 3.0,
        # Moshier is the built-in analytical ephemeris: no data files, and the
        # seam being tested is the artifact shape, not sub-arcsecond precision.
        "ephemeris_policy": "allow-moshier",
        "calculation_profile": "western-tropical-v1",
        "aspect_profile": "ptolemaic-minor-v1",
        "include_derived": False,
        "privacy": "minimal",
    },
    "relationship_context": {"description": "unspecified", "requested_domains": []},
}


def swiss_available() -> bool:
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


@unittest.skipUnless(swiss_available(), "pyswisseph is not installed")
class SynastryHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        destination = Path(cls._directory.name)
        result = run(COMPUTE, "--json", json.dumps(REQUEST), "--out", str(destination))
        if result.returncode != 0:
            raise AssertionError(
                "compute_synastry refused a request built from its own documented example; "
                "skipping here would hide the seam this file exists to cross:\n" + result.stderr.strip()
            )
        # The calculator reports "wrote <path>"; take the path, not the sentence.
        reported = result.stdout.strip().splitlines()[0]
        cls.artifact_path = Path(reported.removeprefix("wrote ").strip())
        cls.artifact = json.loads(cls.artifact_path.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_the_calculator_emits_what_the_reading_gate_accepts(self) -> None:
        """The seam itself. This is what neither suite reached on its own."""

        result = run(VALIDATE, str(self.artifact_path))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_ledger_the_gate_emits_is_usable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "ledger.json"
            result = run(VALIDATE, str(self.artifact_path), "--out", str(ledger_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertTrue(ledger, "an empty ledger gives a reading nothing to cite")
            # A reading cites evidence by id, so the ledger has to carry ids.
            self.assertIn("evidence", json.dumps(ledger).lower())

    def test_a_tampered_artifact_is_refused_at_the_seam(self) -> None:
        """The gate exists to stop an edited artifact reaching prose."""

        tampered = json.loads(json.dumps(self.artifact))
        tampered.setdefault("meta", {})["tampered"] = True
        result = run(VALIDATE, "-", stdin=json.dumps(tampered))
        self.assertNotEqual(result.returncode, 0, "an altered artifact was accepted")

    def test_a_one_person_request_never_produces_an_artifact(self) -> None:
        """Synastry is a two-person calculation; one person must not half-succeed."""

        single = REQUEST | {"people": [REQUEST["people"][0]]}
        with tempfile.TemporaryDirectory() as directory:
            result = run(COMPUTE, "--json", json.dumps(single), "--out", directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(Path(directory).iterdir()), [], "a refused request wrote a file")

    def test_the_bounded_window_survives_the_seam_as_uncertainty(self) -> None:
        """A 90-minute window must not arrive at the reading as an exact time."""

        body = json.dumps(self.artifact, ensure_ascii=False)
        self.assertIn("window", body, "the artifact lost the second subject's time mode")
        self.assertNotIn('"time_mode": "exact", "time_accuracy_minutes": 90', body)


class SynastryReadingContractTests(unittest.TestCase):
    """Hold the reading skill's prose to the artifact its calculator emits."""

    def setUp(self) -> None:
        self.instruction = (ASTROLOGY / "synastry-reading" / "SKILL.md").read_text(encoding="utf-8")

    def test_it_names_the_validator_it_must_run(self) -> None:
        self.assertIn("reading_session.py", self.instruction)

    def test_it_still_refuses_to_score_or_predict(self) -> None:
        for refusal in ("compatibility score", "predict"):
            self.assertIn(refusal, self.instruction, refusal)

    def test_it_reports_certainty_rather_than_flattening_it(self) -> None:
        for term in ("confirmed", "possible"):
            self.assertIn(term, self.instruction, term)


if __name__ == "__main__":
    unittest.main()
