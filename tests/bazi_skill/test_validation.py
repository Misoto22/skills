"""The gate the reading skills used to ask a model to perform by reading JSON.

Every case here is an artifact that passes `validate_envelope` and must still be
refused. That is the whole point: a checksum proves a file was not edited after
it was hashed, and says nothing about whether it was ever complete. The SKILL.md
prose named these defects for four releases with nothing able to detect one.
"""

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
from bazi.validation import (
    CHART,
    COMPATIBILITY,
    ZIWEI,
    ArtifactDefect,
    defects,
    validate,
)

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


class ChartValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        cls.chart = build_chart(birth("Subject A", "1990-03-14"), ephemeris)
        cls.late = build_chart(birth("Subject C", "1991-07-12", "23:30"), ephemeris)

    def test_the_gate_accepts_what_the_calculator_actually_emits(self) -> None:
        """The seam. A rule the calculator's own output fails is a rule that is wrong."""

        self.assertEqual(defects(self.chart, CHART), [])
        self.assertEqual(defects(self.late, CHART), [])
        self.assertEqual(validate(self.chart, CHART)["checksum"], self.chart["checksum"])

    def test_a_missing_hour_pillar_is_named(self) -> None:
        """The defect the reading skills promised to catch and could not."""

        broken = copy.deepcopy(self.chart)
        del broken["pillars"]["primary"]["hour"]
        problems = defects(add_checksum(broken), CHART)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("pillars.primary.hour", problems[0])

    def test_an_emptied_score_ledger_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        broken["scores"]["primary"]["ledger"] = []

        self.assertIn("scores.primary.ledger", "; ".join(defects(add_checksum(broken), CHART)))

    def test_a_dropped_element_is_named_even_when_it_held_nothing(self) -> None:
        """The element a chart has none of is most of what a reader came to hear.

        Its share rounds to zero, so dropping it leaves the total at 100 and a sum
        check sees nothing. Only counting the elements catches it.
        """

        broken = copy.deepcopy(self.chart)
        empty = min(broken["scores"]["primary"]["adjusted_distribution"].items(), key=lambda item: item[1])
        self.assertEqual(empty[1], 0.0, "this chart no longer has an empty element to drop")
        del broken["scores"]["primary"]["adjusted_distribution"][empty[0]]
        problems = "; ".join(defects(add_checksum(broken), CHART))

        self.assertIn("five elements are always scored", problems)
        self.assertIn("score different elements", problems)

    def test_a_distribution_that_no_longer_sums_to_a_hundred_is_named(self) -> None:
        broken = copy.deepcopy(self.chart)
        distribution = broken["scores"]["primary"]["adjusted_distribution"]
        distribution["木"] = distribution["木"] + 10.0

        self.assertIn("not 100", "; ".join(defects(add_checksum(broken), CHART)))

    def test_a_declared_alternate_that_is_absent_is_named_per_block(self) -> None:
        broken = copy.deepcopy(self.late)
        broken["scores"]["alternate"] = None
        problems = defects(add_checksum(broken), CHART)

        self.assertIn("scores.alternate", "; ".join(problems))

    def test_an_undeclared_alternate_that_is_present_is_named(self) -> None:
        """The reverse case, which a reading would silently never mention."""

        broken = copy.deepcopy(self.chart)
        broken["pillars"]["alternate"] = copy.deepcopy(self.chart["pillars"]["primary"])
        problems = defects(add_checksum(broken), CHART)

        self.assertIn("pillars.alternate", "; ".join(problems))

    def test_one_run_reports_every_independent_defect(self) -> None:
        """A person repairing a source sees all of it, not the first thing that tripped."""

        broken = copy.deepcopy(self.chart)
        del broken["pillars"]["primary"]["hour"]
        broken["scores"]["primary"]["ledger"] = []
        broken["input"]["name"] = "  "
        problems = "; ".join(defects(add_checksum(broken), CHART))

        self.assertIn("input.name", problems)
        self.assertIn("pillars.primary.hour", problems)
        self.assertIn("scores.primary.ledger", problems)

    def test_an_absent_sensitivity_flag_is_named(self) -> None:
        """Silence about the boundary is indistinguishable from a confident no."""

        broken = copy.deepcopy(self.chart)
        del broken["sensitivity"]

        self.assertIn(
            "sensitivity.alternate_day_boundary",
            "; ".join(defects(add_checksum(broken), CHART)),
        )

    def test_a_structural_defect_is_named_before_the_checksum(self) -> None:
        """An edited artifact fails both ways; only one of them says what to fix."""

        broken = copy.deepcopy(self.chart)
        del broken["pillars"]["primary"]["hour"]

        with self.assertRaises(ArtifactDefect) as raised:
            validate(broken, CHART)
        self.assertIn("pillars.primary.hour", str(raised.exception))
        self.assertNotIn("checksum", str(raised.exception))

    def test_a_shape_sound_artifact_still_fails_on_a_tampered_value(self) -> None:
        tampered = copy.deepcopy(self.chart)
        tampered["scores"]["primary"]["day_master_strength"]["score"] = 99.0

        self.assertEqual(defects(tampered, CHART), [])
        with self.assertRaisesRegex(ArtifactDefect, "checksum"):
            validate(tampered, CHART)

    def test_the_wrong_kind_of_artifact_is_refused_without_a_pile_of_noise(self) -> None:
        """Twelve defects about a 命盘 nobody supplied would bury the one that matters."""

        problems = defects(self.chart, ZIWEI)

        self.assertEqual(len(problems), 1)
        self.assertIn("chinese-metaphysics.ziwei-chart", problems[0])

    def test_an_unsupported_version_stops_before_the_shape_checks(self) -> None:
        future = add_checksum(copy.deepcopy(self.chart) | {"schema_version": 2})
        problems = defects(future, CHART)

        self.assertEqual(len(problems), 1)
        self.assertIn("schema_version", problems[0])

    def test_an_unknown_kind_is_a_programming_error_not_a_defect_list(self) -> None:
        with self.assertRaisesRegex(ArtifactDefect, "unsupported artifact kind"):
            defects(self.chart, "horoscope")


class CompatibilityValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        cls.left = build_chart(birth("Subject A", "1990-03-14"), ephemeris)
        cls.right = build_chart(birth("Subject B", "1992-06-08"), ephemeris)
        cls.general = compare_charts(cls.left, cls.right, None)
        cls.marriage = compare_charts(cls.left, cls.right, "marriage")

    def test_the_gate_accepts_what_the_calculator_actually_emits(self) -> None:
        self.assertEqual(defects(self.general, COMPATIBILITY), [])
        self.assertEqual(defects(self.marriage, COMPATIBILITY), [])

    def test_weights_that_no_longer_sum_to_a_hundred_are_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["dimensions"][0]["weight"] = 40
        broken["methodology"]["general_weights"]["element_complementarity"] = 40
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("weights sum to", problems)

    def test_a_weight_disagreeing_with_the_declared_model_is_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["dimensions"][0]["weight"] = 30
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("methodology declares", problems)

    def test_a_general_score_its_own_dimensions_do_not_produce_is_named(self) -> None:
        """The arithmetic a reader cannot check and a report is entirely built on."""

        broken = copy.deepcopy(self.general)
        broken["scores"]["general"] = round(broken["scores"]["general"] + 12.0, 2)
        broken["sensitivity"]["maximum"] = broken["scores"]["general"]
        broken["sensitivity"]["spread"] = round(
            broken["sensitivity"]["maximum"] - broken["sensitivity"]["minimum"], 2
        )
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("scores.general", problems)
        self.assertIn("is not what its own dimensions produce", problems)

    def test_a_dimension_with_no_ledger_is_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["dimensions"][2]["ledger"] = []

        self.assertIn("cannot be cited", "; ".join(defects(add_checksum(broken), COMPATIBILITY)))

    def test_a_missing_dimension_is_named_rather_than_silently_reweighted(self) -> None:
        broken = copy.deepcopy(self.general)
        del broken["dimensions"][4]
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("structural_stability", problems)

    def test_a_contextual_score_without_its_profile_cannot_be_audited(self) -> None:
        broken = copy.deepcopy(self.marriage)
        broken["scores"]["contextual_profile"] = None

        self.assertIn("contextual_profile", "; ".join(defects(add_checksum(broken), COMPATIBILITY)))

    def test_a_contextual_score_with_no_stated_context_is_named(self) -> None:
        """A reading would have to invent the lens the number answers."""

        broken = copy.deepcopy(self.general)
        broken["scores"]["contextual"] = 71.5
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("relationship_type", problems)

    def test_a_contextual_score_its_own_profile_does_not_produce_is_named(self) -> None:
        broken = copy.deepcopy(self.marriage)
        broken["scores"]["contextual"] = round(broken["scores"]["contextual"] + 9.0, 2)
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("is not what its own profile produces", problems)

    def test_a_displayed_score_outside_its_own_sensitivity_range_is_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["sensitivity"]["minimum"] = round(broken["scores"]["general"] + 5.0, 2)
        broken["sensitivity"]["maximum"] = round(broken["scores"]["general"] + 8.0, 2)
        broken["sensitivity"]["spread"] = 3.0
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("outside its own range", problems)

    def test_a_spread_that_is_not_the_range_it_reports_is_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["sensitivity"]["spread"] = 14.0

        self.assertIn("sensitivity.spread", "; ".join(defects(add_checksum(broken), COMPATIBILITY)))

    def test_a_comparison_of_one_person_with_themselves_is_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["people"]["right"]["chart_checksum"] = broken["people"]["left"]["chart_checksum"]
        problems = "; ".join(defects(add_checksum(broken), COMPATIBILITY))

        self.assertIn("compares someone with themselves", problems)

    def test_a_person_without_a_chart_checksum_is_named(self) -> None:
        broken = copy.deepcopy(self.general)
        broken["people"]["left"]["chart_checksum"] = ""

        self.assertIn("chart_checksum", "; ".join(defects(add_checksum(broken), COMPATIBILITY)))


class SharedShapeGateTests(unittest.TestCase):
    """The calculator and the reading gate ask one module, so they cannot drift."""

    @classmethod
    def setUpClass(cls) -> None:
        ephemeris = MeanSolarEphemeris()
        cls.left = build_chart(birth("Subject A", "1990-03-14"), ephemeris)
        cls.right = build_chart(birth("Subject B", "1992-06-08"), ephemeris)

    def test_the_comparison_refuses_the_chart_the_reading_gate_refuses(self) -> None:
        incomplete = copy.deepcopy(self.right)
        del incomplete["pillars"]["primary"]["hour"]
        incomplete = add_checksum(incomplete)

        self.assertIn("pillars.primary.hour", "; ".join(defects(incomplete, CHART)))
        with self.assertRaisesRegex(CompatibilityError, "pillars.primary.hour"):
            compare_charts(self.left, incomplete, None)

    def test_a_complete_pair_still_compares(self) -> None:
        result = compare_charts(self.left, self.right, None)

        self.assertEqual(defects(result, COMPATIBILITY), [])


if __name__ == "__main__":
    unittest.main()
