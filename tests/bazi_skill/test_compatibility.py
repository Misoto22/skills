from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from bazi.artifacts import add_checksum
from bazi.compatibility import CompatibilityError, compare_charts
from bazi.engine import build_chart

from bazi_skill.ephemeris_double import MeanSolarEphemeris


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


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        cls.left = build_chart(birth("Left", "1990-03-14"), ephemeris)
        cls.right = build_chart(birth("Right", "1992-06-08"), ephemeris)
        cls.boundary = build_chart(birth("Boundary", "1991-07-12", "23:30"), ephemeris)

    def test_general_scores_are_symmetric_and_directional_owners_reverse(self) -> None:
        forward = compare_charts(self.left, self.right, None)
        reverse = compare_charts(self.right, self.left, None)

        self.assertEqual(forward["scores"]["general"], reverse["scores"]["general"])
        self.assertEqual(
            [item["score"] for item in forward["dimensions"]],
            [item["score"] for item in reverse["dimensions"]],
        )
        support_forward = next(
            item for item in forward["dimensions"] if item["id"] == "directional_day_master_support"
        )
        support_reverse = next(
            item for item in reverse["dimensions"] if item["id"] == "directional_day_master_support"
        )
        self.assertEqual(
            [item["owner"] for item in support_forward["ledger"]],
            list(reversed([item["owner"] for item in support_reverse["ledger"]])),
        )

    def test_general_arithmetic_is_reproducible(self) -> None:
        result = compare_charts(self.left, self.right, None)
        expected = sum(item["score"] * item["weight"] / 100.0 for item in result["dimensions"])

        self.assertAlmostEqual(result["scores"]["general"], expected, places=2)
        self.assertEqual([item["weight"] for item in result["dimensions"]], [25, 20, 20, 20, 15])

    def test_relationship_profile_changes_only_the_contextual_index(self) -> None:
        general = compare_charts(self.left, self.right, None)
        romance = compare_charts(self.left, self.right, "romance")
        work = compare_charts(self.left, self.right, "work")

        self.assertEqual(general["scores"]["general"], romance["scores"]["general"])
        self.assertEqual(romance["scores"]["general"], work["scores"]["general"])
        self.assertEqual(general["dimensions"], romance["dimensions"])
        self.assertNotEqual(romance["scores"]["contextual"], work["scores"]["contextual"])

    def test_unknown_relationship_type_fails(self) -> None:
        with self.assertRaisesRegex(CompatibilityError, "relationship_type"):
            compare_charts(self.left, self.right, "soulmate")

    def test_alternate_charts_produce_a_sensitivity_range(self) -> None:
        result = compare_charts(self.left, self.boundary, None)

        self.assertGreaterEqual(len(result["sensitivity"]["variants"]), 2)
        self.assertLessEqual(result["sensitivity"]["minimum"], result["scores"]["general"])
        self.assertGreaterEqual(result["sensitivity"]["maximum"], result["scores"]["general"])

    def test_shen_sha_never_changes_a_dimension(self) -> None:
        modified = copy.deepcopy(self.right)
        modified["facts"]["primary"]["shen_sha"].append({"name": "Synthetic", "evidence_level": "secondary"})
        modified = add_checksum(modified)

        baseline = compare_charts(self.left, self.right, None)
        with_shen_sha = compare_charts(self.left, modified, None)
        self.assertEqual(
            [item["score"] for item in baseline["dimensions"]],
            [item["score"] for item in with_shen_sha["dimensions"]],
        )


if __name__ == "__main__":
    unittest.main()
