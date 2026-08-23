"""Exercise what `bazi-compatibility-reading` receives, not just what produces it.

The compute side has its own tests. What had none was the hand-off: the reading
skill's source gate lists fields it will stop on, and nothing checked that a
real artifact actually carries them. An end-to-end audit could not reach this
either, because reaching it needs a second person's birth record — so the gap
survived every check that existed.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
SKILL = ROOT / "plugins" / "chinese-metaphysics" / "skills" / "bazi-compatibility-reading"
sys.path.insert(0, str(SHARED))

from bazi.artifacts import ArtifactError, add_checksum, validate_envelope, write_artifact_pair
from bazi.compatibility import compare_charts
from bazi.engine import build_chart
from bazi.ephemeris import EphemerisUnavailable, SwissEphemeris

# Synthetic, and deliberately not anyone's: two records chosen only to sit in
# different months and hours so the comparison has something to find.
LEFT = {
    "name": "Subject A",
    "birth_place": "Shanghai, China",
    "birth_date": "1988-04-11",
    "birth_time": "09:15",
    "calendar": "gregorian",
    "timezone": "Asia/Shanghai",
    "latitude": 31.23,
    "longitude": 121.47,
}
RIGHT = LEFT | {
    "name": "Subject B",
    "birth_date": "1991-11-26",
    "birth_time": "17:40",
}


def swiss_available() -> bool:
    try:
        SwissEphemeris()
    except EphemerisUnavailable:
        return False
    return True


@unittest.skipUnless(swiss_available(), "pyswisseph is not installed")
class CompatibilityHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = SwissEphemeris()
        cls.left = build_chart(copy.deepcopy(LEFT), ephemeris)
        cls.right = build_chart(copy.deepcopy(RIGHT), ephemeris)
        cls.comparison = compare_charts(cls.left, cls.right, None)

    def test_the_artifact_the_reading_skill_accepts_actually_validates(self) -> None:
        validated = validate_envelope(self.comparison)
        self.assertEqual(validated["schema"], "chinese-metaphysics.bazi-compatibility")
        self.assertEqual(validated["schema_version"], 1)

    def test_it_carries_every_field_the_source_gate_names(self) -> None:
        """The gate lists what it stops on. A field it names must exist to be checked."""

        envelope = self.comparison
        self.assertEqual(
            sorted(envelope["people"]),
            ["left", "right"],
            "the gate requires two named people",
        )
        for side in ("left", "right"):
            person = envelope["people"][side]
            with self.subTest(side=side):
                self.assertTrue(str(person.get("name", "")).strip())
                self.assertTrue(
                    str(person.get("chart_checksum", "")).strip(), "the gate requires chart checksums"
                )

        self.assertIn("dimensions", envelope)
        self.assertEqual(len(envelope["dimensions"]), 5, "the gate names all five dimensions")
        weights = 0.0
        for dimension in envelope["dimensions"]:
            with self.subTest(dimension=dimension.get("name")):
                for field in ("id", "name", "weight", "score", "ledger"):
                    self.assertIn(field, dimension)
                self.assertTrue(dimension["ledger"], "a dimension with no ledger cannot be cited")
                weights += float(dimension["weight"])
        self.assertAlmostEqual(weights, 100.0, places=6, msg="weights must account for the whole score")

        self.assertIn("general", envelope["scores"])
        # The gate names an optional contextual profile and score. Optional means
        # the keys exist and may be null, not that they may be absent — a reading
        # that has to ask whether a key exists cannot report it was not selected.
        for optional in ("contextual", "contextual_profile"):
            self.assertIn(optional, envelope["scores"], optional)

        self.assertEqual(envelope["model_version"], "bazi-compatibility-v1")
        self.assertIn("level", envelope["confidence"])
        self.assertIn("sensitivity", envelope)
        self.assertIn("variants", envelope["sensitivity"])
        self.assertIn("not probabilities", envelope["score_semantics"])

    def test_a_tampered_artifact_is_refused_rather_than_read(self) -> None:
        """The gate's whole job. A changed dimension must not survive to prose."""

        tampered = copy.deepcopy(self.comparison)
        tampered["dimensions"][0]["score"] = 99.0
        with self.assertRaises(ArtifactError):
            validate_envelope(tampered)

        renamed = copy.deepcopy(self.comparison)
        renamed["people"]["left"]["name"] = "Someone Else"
        with self.assertRaises(ArtifactError):
            validate_envelope(renamed)

    def test_an_unsupported_version_is_refused(self) -> None:
        future = add_checksum(copy.deepcopy(self.comparison) | {"schema_version": 2})
        with self.assertRaises(ArtifactError):
            validate_envelope(future)

    def test_the_pair_it_writes_is_what_the_reading_skill_is_pointed_at(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path, markdown_path = write_artifact_pair(
                self.comparison, Path(directory), kind="compatibility"
            )
            self.assertTrue(json_path.is_file() and markdown_path.is_file())
            reloaded = json.loads(json_path.read_text(encoding="utf-8"))
            validate_envelope(reloaded)
            self.assertIn(self.comparison["checksum"], markdown_path.read_text(encoding="utf-8"))
            # Data only: the reading skill is what interprets, and a Markdown that
            # already interpreted would make the separation meaningless.
            body = markdown_path.read_text(encoding="utf-8")
            for interpreting in ("suggests", "tends to", "commonly read", "适合", "倾向"):
                self.assertNotIn(interpreting, body, interpreting)
            self.assertIn("not probability", body.lower())

    def test_both_charts_stay_separable_inside_the_comparison(self) -> None:
        """A reading has to attribute evidence to one side or the other."""

        envelope = self.comparison
        left_checksum = envelope["people"]["left"]["chart_checksum"]
        right_checksum = envelope["people"]["right"]["chart_checksum"]
        self.assertNotEqual(left_checksum, right_checksum)
        self.assertEqual(left_checksum, self.left["checksum"])
        self.assertEqual(right_checksum, self.right["checksum"])


class CompatibilityReadingContractTests(unittest.TestCase):
    """The gate is prose. These hold the prose to naming what the artifact has."""

    def setUp(self) -> None:
        self.instruction = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    def test_the_gate_names_the_schema_it_accepts(self) -> None:
        self.assertIn("chinese-metaphysics.bazi-compatibility", self.instruction)
        self.assertIn("schema version 1", self.instruction)

    def test_the_gate_requires_a_checksum_and_refuses_to_fake_one(self) -> None:
        self.assertIn("pasted-complete", self.instruction)
        self.assertIn("do not claim checksum validation when none exists", self.instruction)

    def test_it_still_separates_the_reader_report_from_the_evidence(self) -> None:
        self.assertIn("bazi_compatibility_reading_<name-a>_<name-b>.md", self.instruction)
        self.assertIn("bazi_compatibility_evidence_<name-a>_<name-b>.md", self.instruction)


if __name__ == "__main__":
    unittest.main()
