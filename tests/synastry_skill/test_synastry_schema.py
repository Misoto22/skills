from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "astrology" / "shared"
sys.path.insert(0, str(SHARED))

from synastry_schema import (
    ASPECT_PROFILE,
    CALCULATION_PROFILE,
    DERIVED_PROFILE,
    EVIDENCE_POLICY,
    KIND,
    SCHEMA_VERSION,
    SchemaError,
    attach_integrity,
    canonical_json,
    payload_digest,
    validate_artifact,
)


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
                "birth": {
                    "mode": "exact",
                    "utc": "1990-03-14T06:42:00Z",
                    "latitude": 48.86,
                    "longitude": 2.35,
                },
            },
            {
                "id": "subject-b",
                "display_name": "Morgan",
                "birth": {
                    "mode": "exact",
                    "utc": "1992-06-08T15:00:00Z",
                    "latitude": 34.05,
                    "longitude": -118.24,
                },
            },
        ],
        "configuration": {
            "calculation_profile": "western-tropical-v1",
            "aspect_profile": "ptolemaic-minor-v1",
            "derived_profile": "classical-derived-v1",
            "privacy": "minimal",
            "major_orb": 8.0,
            "minor_orb": 3.0,
            "include_derived": True,
            "house_system": "whole-sign",
            "ephemeris_policy": "swiss-only",
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


def uncertain_artifact(
    *, mode: str = "window", certainty: str = "possible", minimum_orb: float = 2.0, maximum_orb: float = 10.0
) -> dict[str, object]:
    source = valid_artifact()
    source["subjects"][0]["birth"] = {  # type: ignore[index]
        "mode": mode,
        "utc_start": "1990-03-14T06:00:00Z",
        "utc_end": "1990-03-14T08:00:00Z",
    }
    source["charts"][0] = {  # type: ignore[index]
        "subject_id": "subject-a",
        "precision_mode": mode,
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
        certainty=certainty,
        orb_range_degrees={
            "minimum_degrees": minimum_orb,
            "maximum_degrees": maximum_orb,
        },
    )
    source["overlays"] = []
    return source


class SynastrySchemaTests(unittest.TestCase):
    def test_exported_constants_and_known_integrity_vectors(self) -> None:
        self.assertEqual(KIND, "synastry-chart")
        self.assertEqual(SCHEMA_VERSION, "2.0")
        self.assertEqual(CALCULATION_PROFILE, "western-tropical-v1")
        self.assertEqual(ASPECT_PROFILE, "ptolemaic-minor-v1")
        self.assertEqual(DERIVED_PROFILE, "classical-derived-v1")
        self.assertEqual(EVIDENCE_POLICY, "editorial-v1")
        self.assertEqual(canonical_json({"b": 1, "a": "é"}), b'{"a":"\xc3\xa9","b":1}')
        self.assertEqual(
            payload_digest({"a": 1, "integrity": {"algorithm": "ignored", "digest": "ignored"}}),
            "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862",
        )
        self.assertEqual(payload_digest({"a": 1}), payload_digest({"a": 1, "integrity": "excluded"}))

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
        source = uncertain_artifact()

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
        source = uncertain_artifact()
        source["subjects"][0]["birth"] = valid_artifact()["subjects"][0]["birth"]  # type: ignore[index]

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

    def test_uncertain_charts_cannot_emit_sect_or_lots(self) -> None:
        for field, value in (("sect", "diurnal"), ("lots", {"Lot_of_Fortune": 10.0})):
            with self.subTest(field=field):
                source = uncertain_artifact()
                source["charts"][0]["derived"] = {field: value}  # type: ignore[index]
                with self.assertRaisesRegex(SchemaError, f"uncertain.*{field}"):
                    validate_artifact(attach_integrity(source))

    def test_derived_content_matches_the_declared_configuration(self) -> None:
        source = valid_artifact()
        source["charts"][0]["derived"] = {  # type: ignore[index]
            "sect": "diurnal",
            "lots": {"Lot_of_Fortune": 10.0},
        }
        self.assertEqual(validate_artifact(attach_integrity(source))["kind"], KIND)

        source = valid_artifact()
        source["configuration"]["derived_profile"] = None  # type: ignore[index]
        source["charts"][0]["derived"] = {"sect": "diurnal"}  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "derived_profile"):
            validate_artifact(attach_integrity(source))

        source = valid_artifact()
        source["configuration"].update(include_derived=False, derived_profile=None)  # type: ignore[union-attr]
        source["charts"][0]["derived"] = {"sect": "diurnal"}  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "include_derived"):
            validate_artifact(attach_integrity(source))

        source = valid_artifact()
        source["configuration"]["include_derived"] = False  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "derived_profile"):
            validate_artifact(attach_integrity(source))

    def test_possible_and_confirmed_orb_ranges_have_distinct_semantics(self) -> None:
        validated = validate_artifact(attach_integrity(uncertain_artifact()))
        self.assertEqual(validated["aspects"][0]["certainty"], "possible")  # type: ignore[index]

        source = uncertain_artifact(certainty="confirmed")
        with self.assertRaisesRegex(SchemaError, "confirmed.*maximum"):
            validate_artifact(attach_integrity(source))

        source = uncertain_artifact(minimum_orb=9.0)
        with self.assertRaisesRegex(SchemaError, "possible.*minimum"):
            validate_artifact(attach_integrity(source))

    def test_backend_policy_and_provenance_must_agree(self) -> None:
        source = valid_artifact()
        source["provenance"]["actual_backend"] = "moshier"  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "swiss-only.*moshier"):
            validate_artifact(attach_integrity(source))

        source["configuration"]["ephemeris_policy"] = "allow-moshier"  # type: ignore[index]
        self.assertEqual(validate_artifact(attach_integrity(source))["kind"], KIND)

        for container, field in (
            ("configuration", "ephemeris_policy"),
            ("provenance", "actual_backend"),
            ("provenance", "requested_backend"),
        ):
            with self.subTest(container=container):
                source = valid_artifact()
                source[container][field] = "invented"  # type: ignore[index]
                with self.assertRaisesRegex(SchemaError, "expected one of"):
                    validate_artifact(attach_integrity(source))

    def test_minimal_privacy_rejects_archival_and_local_birth_metadata(self) -> None:
        for field, value in (
            ("place_label", "Paris"),
            ("location_source", "user supplied"),
            ("date", "1990-03-14"),
            ("time", "07:42"),
            ("timezone", "Europe/Paris"),
        ):
            with self.subTest(field=field):
                source = valid_artifact()
                source["subjects"][0]["birth"][field] = value  # type: ignore[index]
                with self.assertRaisesRegex(SchemaError, f"minimal.*{field}"):
                    validate_artifact(attach_integrity(source))

    def test_full_privacy_accepts_mode_appropriate_archival_metadata(self) -> None:
        source = valid_artifact()
        source["configuration"]["privacy"] = "full"  # type: ignore[index]
        source["subjects"][0]["birth"].update(  # type: ignore[index]
            date="1990-03-14",
            time="07:42",
            timezone="Europe/Paris",
            place_label="Paris",
            location_source="user supplied",
        )

        self.assertEqual(validate_artifact(attach_integrity(source))["kind"], KIND)

    def test_house_data_requires_supported_system_and_calculation_location(self) -> None:
        source = valid_artifact()
        source["configuration"]["house_system"] = "invented"  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "house_system.*expected one of"):
            validate_artifact(attach_integrity(source))

        source = valid_artifact()
        source["subjects"][0]["birth"].pop("latitude")  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "houses.*latitude.*longitude"):
            validate_artifact(attach_integrity(source))

        source = valid_artifact()
        del source["configuration"]["house_system"]  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "house_system.*required"):
            validate_artifact(attach_integrity(source))

    def test_every_house_feature_requires_a_calculation_location(self) -> None:
        for feature in ("houses", "angles", "position house"):
            with self.subTest(feature=feature):
                source = valid_artifact()
                source["overlays"] = []
                source["charts"][0].pop("houses")  # type: ignore[index]
                source["charts"][0]["positions"]["Sun"].pop("house")  # type: ignore[index]
                if feature == "houses":
                    source["charts"][0]["houses"] = [  # type: ignore[index]
                        float(index * 30) for index in range(12)
                    ]
                elif feature == "angles":
                    source["charts"][0]["angles"] = {"ascendant": 10.0}  # type: ignore[index]
                else:
                    source["charts"][0]["positions"]["Sun"]["house"] = 1  # type: ignore[index]
                source["subjects"][0]["birth"].pop("longitude")  # type: ignore[index]

                with self.assertRaisesRegex(SchemaError, "houses.*latitude.*longitude"):
                    validate_artifact(attach_integrity(source))

    def test_date_only_birth_has_a_closed_ordered_utc_interval(self) -> None:
        source = uncertain_artifact(mode="date-only")
        self.assertEqual(
            validate_artifact(attach_integrity(source))["charts"][0]["precision_mode"], "date-only"
        )  # type: ignore[index]

        for field, value in (
            ("utc", "1990-03-14T07:00:00Z"),
            ("time", "07:00"),
            ("time_window", {"start": "06:00", "end": "08:00"}),
        ):
            with self.subTest(field=field):
                source = uncertain_artifact(mode="date-only")
                source["subjects"][0]["birth"][field] = value  # type: ignore[index]
                with self.assertRaisesRegex(SchemaError, f"date-only.*{field}"):
                    validate_artifact(attach_integrity(source))

        source = uncertain_artifact(mode="date-only")
        birth = source["subjects"][0]["birth"]  # type: ignore[index]
        birth["utc_start"], birth["utc_end"] = birth["utc_end"], birth["utc_start"]
        with self.assertRaisesRegex(SchemaError, "ordered.*non-empty"):
            validate_artifact(attach_integrity(source))

    def test_each_time_mode_requires_normalized_noncontradictory_timestamps(self) -> None:
        for timestamp in ("not-a-time", "1990-03-14T07:00:00+01:00"):
            with self.subTest(timestamp=timestamp):
                source = valid_artifact()
                source["subjects"][0]["birth"]["utc"] = timestamp  # type: ignore[index]
                with self.assertRaisesRegex(SchemaError, "normalized UTC timestamp"):
                    validate_artifact(attach_integrity(source))

        source = valid_artifact()
        source["subjects"][0]["birth"]["utc_start"] = "1990-03-14T06:00:00Z"  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "exact.*utc_start"):
            validate_artifact(attach_integrity(source))

        source = uncertain_artifact()
        del source["subjects"][0]["birth"]["utc_end"]  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "window.*utc_start and utc_end"):
            validate_artifact(attach_integrity(source))

    def test_sign_labels_match_exact_and_wrapped_uncertain_longitudes(self) -> None:
        source = valid_artifact()
        source["charts"][0]["positions"]["Sun"].update(  # type: ignore[index]
            longitude_degrees=30.0,
            sign="Tau",
        )
        self.assertEqual(validate_artifact(attach_integrity(source))["kind"], KIND)

        source = valid_artifact()
        source["charts"][0]["positions"]["Sun"]["sign"] = "Tau"  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "sign.*longitude"):
            validate_artifact(attach_integrity(source))

        source = uncertain_artifact()
        source["charts"][0]["positions"]["Sun"]["signs"] = ["Ari"]  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "signs.*longitude_range"):
            validate_artifact(attach_integrity(source))

        source = uncertain_artifact()
        source["charts"][0]["positions"]["Sun"]["longitude_range"]["wraps_zero"] = False  # type: ignore[index]
        with self.assertRaisesRegex(SchemaError, "wraps_zero.*contradicts"):
            validate_artifact(attach_integrity(source))


if __name__ == "__main__":
    unittest.main()
