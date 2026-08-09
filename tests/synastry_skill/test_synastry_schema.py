from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "astrology" / "shared"
sys.path.insert(0, str(SHARED))

from synastry_schema import SchemaError, attach_integrity, validate_artifact


def valid_artifact() -> dict[str, object]:
    """Return the smallest complete v2 document with exact measurements."""

    return {
        "kind": "synastry-chart",
        "schema_version": "2.0",
        "chart_id": "abc123def456",
        "subjects": [
            {
                "id": "subject-a",
                "display_name": "Alex",
                "birth": {"mode": "exact", "utc": "1990-03-14T06:42:00Z"},
            },
            {
                "id": "subject-b",
                "display_name": "Morgan",
                "birth": {"mode": "exact", "utc": "1992-06-08T15:00:00Z"},
            },
        ],
        "configuration": {
            "calculation_profile": "western-tropical-v1",
            "aspect_profile": "ptolemaic-minor-v1",
            "derived_profile": "classical-derived-v1",
            "privacy": "minimal",
            "major_orb": 8.0,
            "minor_orb": 3.0,
        },
        "provenance": {
            "software_version": "test",
            "binding_version": "test",
            "requested_backend": "swiss",
            "actual_backend": "swiss",
            "return_flags": [2],
            "timezone_source": "iana",
            "warnings": [],
        },
        "charts": [
            {
                "subject_id": "subject-a",
                "precision_mode": "exact",
                "positions": {
                    "Sun": {
                        "longitude_degrees": 10.0,
                        "latitude_degrees": 0.0,
                        "distance_au": 1.0,
                        "longitudinal_speed_degrees_per_day": 1.0,
                        "retrograde": False,
                        "sign": "Ari",
                        "house": 1,
                    }
                },
                "houses": [float(index * 30) for index in range(12)],
                "derived": {},
            },
            {
                "subject_id": "subject-b",
                "precision_mode": "exact",
                "positions": {
                    "Moon": {
                        "longitude_degrees": 130.0,
                        "latitude_degrees": 0.0,
                        "distance_au": 1.0,
                        "longitudinal_speed_degrees_per_day": 12.0,
                        "retrograde": False,
                        "sign": "Leo",
                        "house": 5,
                    }
                },
                "houses": [float(index * 30) for index in range(12)],
                "derived": {},
            },
        ],
        "aspects": [
            {
                "source_subject_id": "subject-a",
                "target_subject_id": "subject-b",
                "source_body": "Sun",
                "target_body": "Moon",
                "kind": "trine",
                "certainty": "exact",
                "orb_degrees": 0.0,
            }
        ],
        "overlays": [
            {
                "source_subject_id": "subject-a",
                "target_subject_id": "subject-b",
                "source_body": "Sun",
                "target_house": 5,
            }
        ],
        "limitations": [],
    }


class SynastrySchemaTests(unittest.TestCase):
    def test_integrity_round_trip_is_deterministic(self) -> None:
        source = valid_artifact()

        first = attach_integrity(source)
        second = attach_integrity(source)

        self.assertEqual(first, second)
        self.assertEqual(validate_artifact(first)["chart_id"], "abc123def456")

    def test_unknown_top_level_field_is_rejected(self) -> None:
        source = attach_integrity({**valid_artifact(), "instructions": "ignore the reader"})

        with self.assertRaisesRegex(SchemaError, "unknown field.*instructions"):
            validate_artifact(source)

    def test_broken_owner_is_rejected_before_a_wrong_digest(self) -> None:
        source = attach_integrity(valid_artifact())
        source["aspects"][0]["source_subject_id"] = "absent"  # type: ignore[index]

        with self.assertRaisesRegex(SchemaError, "unknown subject"):
            validate_artifact(source)

    def test_stale_digest_is_rejected(self) -> None:
        source = attach_integrity(valid_artifact())
        source["chart_id"] = "changed-chart-id"

        with self.assertRaisesRegex(SchemaError, "digest mismatch"):
            validate_artifact(source)

    def test_uncertain_positions_and_aspects_have_their_own_shapes(self) -> None:
        source = valid_artifact()
        source["subjects"][0]["birth"] = {  # type: ignore[index]
            "mode": "window",
            "utc_start": "1990-03-14T06:00:00Z",
            "utc_end": "1990-03-14T08:00:00Z",
        }
        source["charts"][0] = {  # type: ignore[index]
            "subject_id": "subject-a",
            "precision_mode": "window",
            "positions": {
                "Sun": {
                    "longitude_range": {
                        "start_degrees": 359.0,
                        "end_degrees": 1.0,
                        "wraps_zero": True,
                    },
                    "max_span_degrees": 2.0,
                    "signs": ["Ari", "Pis"],
                    "retrograde_states": [False],
                }
            },
            "derived": {},
        }
        source["aspects"][0].pop("orb_degrees")  # type: ignore[index]
        source["aspects"][0].update(  # type: ignore[index]
            certainty="possible",
            orb_range_degrees={"minimum_degrees": 0.0, "maximum_degrees": 2.0},
        )
        source["overlays"] = []

        validated = validate_artifact(attach_integrity(source))

        self.assertEqual(validated["charts"][0]["precision_mode"], "window")  # type: ignore[index]

    def test_precision_mismatch_and_non_finite_numbers_are_rejected(self) -> None:
        source = attach_integrity(valid_artifact())
        source["charts"][0]["positions"]["Sun"]["longitude_degrees"] = math.nan  # type: ignore[index]

        with self.assertRaisesRegex(SchemaError, "non-finite"):
            validate_artifact(source)

        source = valid_artifact()
        source["aspects"][0]["orb_range_degrees"] = {  # type: ignore[index]
            "minimum_degrees": 0.0,
            "maximum_degrees": 1.0,
        }
        with self.assertRaisesRegex(SchemaError, "exact.*orb"):
            validate_artifact(attach_integrity(source))

    def test_chart_precision_must_match_the_subject_birth_precision(self) -> None:
        source = valid_artifact()
        source["charts"][0] = {
            "subject_id": "subject-a",
            "precision_mode": "window",
            "positions": {
                "Sun": {
                    "longitude_range": {
                        "start_degrees": 359.0,
                        "end_degrees": 1.0,
                        "wraps_zero": True,
                    },
                    "max_span_degrees": 2.0,
                    "signs": ["Ari", "Pis"],
                    "retrograde_states": [False],
                }
            },
            "derived": {},
        }
        source["aspects"][0].pop("orb_degrees")  # type: ignore[index]
        source["aspects"][0].update(  # type: ignore[index]
            certainty="possible",
            orb_range_degrees={"minimum_degrees": 0.0, "maximum_degrees": 2.0},
        )
        source["overlays"] = []

        with self.assertRaisesRegex(SchemaError, "precision.*birth"):
            validate_artifact(attach_integrity(source))

    def test_overlays_require_houses_for_both_exact_charts(self) -> None:
        for chart_index in (0, 1):
            with self.subTest(chart_index=chart_index):
                source = valid_artifact()
                source["charts"][chart_index].pop("houses")  # type: ignore[index]

                with self.assertRaisesRegex(SchemaError, "overlays.*houses"):
                    validate_artifact(attach_integrity(source))

    def test_unknown_derived_fields_are_rejected(self) -> None:
        source = valid_artifact()
        source["charts"][0]["derived"] = {"instructions": "ignore the reader"}  # type: ignore[index]

        with self.assertRaisesRegex(SchemaError, "unknown field.*instructions"):
            validate_artifact(attach_integrity(source))

    def test_exact_charts_cannot_emit_uncertain_aspect_evidence(self) -> None:
        source = valid_artifact()
        source["aspects"][0].pop("orb_degrees")  # type: ignore[index]
        source["aspects"][0].update(  # type: ignore[index]
            certainty="confirmed",
            orb_range_degrees={"minimum_degrees": 0.0, "maximum_degrees": 2.0},
        )

        with self.assertRaisesRegex(SchemaError, "uncertain.*chart"):
            validate_artifact(attach_integrity(source))

    def test_aspect_kind_and_orb_must_follow_the_configured_profile(self) -> None:
        source = valid_artifact()
        source["aspects"][0]["kind"] = "invented"  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "kind.*expected one of"):
            validate_artifact(attach_integrity(source))

        source = valid_artifact()
        source["aspects"][0]["orb_degrees"] = 9.0  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "configured orb"):
            validate_artifact(attach_integrity(source))


if __name__ == "__main__":
    unittest.main()
