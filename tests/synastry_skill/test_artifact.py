from __future__ import annotations

import copy
import json
import stat
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

from artifact import build_artifact, chart_id, output_name, write_artifact  # type: ignore[import-not-found]
from astro.ephemeris import (  # type: ignore[import-not-found]
    BackendProvenance,
    Limitation,
    PositionSamples,
    ResolvedChart,
)
from astro.request_schema import (  # type: ignore[import-not-found]
    SynastryRequest,
    parse_request,
    resolve_interval,
)
from synastry_schema import (  # type: ignore[import-not-found]
    SchemaError,
    attach_integrity,
    canonical_json,
    validate_artifact,
)

from tests.synastry_skill.test_request_schema import exact_request, mixed_precision_request


def request(*, privacy: str = "minimal", include_derived: bool = False) -> SynastryRequest:
    payload = exact_request()
    options = payload["options"]
    assert isinstance(options, dict)
    options.update(privacy=privacy, include_derived=include_derived)
    return parse_request(payload)


def position(
    longitude: float, *, speed: float = 1.0, samples: tuple[float, ...] | None = None
) -> PositionSamples:
    longitudes = samples or (longitude,)
    return PositionSamples(
        longitude_degrees=longitudes,
        latitude_degrees=tuple(0.0 for _ in longitudes),
        distance_au=tuple(1.0 for _ in longitudes),
        longitudinal_speed_degrees_per_day=tuple(speed for _ in longitudes),
    )


def provenance(*, fallback: bool = False) -> BackendProvenance:
    warning = "Moshier calculations were used because Swiss Ephemeris data was unavailable."
    return BackendProvenance(
        software_version="2.0",
        binding_version="2.10.03",
        requested_backend="swiss",
        actual_backend="moshier" if fallback else "swiss",
        return_flags=(260,),
        timezone_source="iana-zoneinfo",
        warnings=(warning,) if fallback else (),
        data_path="/opt/ephe",
    )


def exact_charts(*, include_limitation: bool = False) -> tuple[ResolvedChart, ResolvedChart]:
    parsed = request()
    first_interval = resolve_interval(parsed.people[0].birth)
    second_interval = resolve_interval(parsed.people[1].birth)
    first_interval = replace(first_interval, julian_start=2447964.779, julian_end=2447964.779)
    second_interval = replace(second_interval, julian_start=2448782.302, julian_end=2448782.302)
    limitation = (
        Limitation(
            code="optional-ephemeris-data-missing",
            message="Optional ephemeris data was unavailable for: Chiron.",
            affected_fields=("positions.Chiron",),
        ),
    )
    return (
        ResolvedChart(
            subject_id="a",
            precision_mode="exact",
            interval=first_interval,
            positions={
                "Sun": position(10.0),
                "Moon": position(100.0, speed=-1.0),
                "Venus": position(40.0),
                "Jupiter": position(70.0),
                "Saturn": position(190.0),
            },
            houses=tuple(float(index * 30) for index in range(12)),
            angles={"ascendant": 5.0, "medium_coeli": 275.0},
            provenance=provenance(),
            limitations=limitation if include_limitation else (),
        ),
        ResolvedChart(
            subject_id="b",
            precision_mode="exact",
            interval=second_interval,
            positions={
                "Sun": position(130.0),
                "Moon": position(220.0),
                "Venus": position(160.0),
                "Jupiter": position(200.0),
                "Saturn": position(310.0),
            },
            houses=tuple(float(index * 30) for index in range(12)),
            angles={"ascendant": 95.0, "medium_coeli": 5.0},
            provenance=provenance(),
            limitations=(),
        ),
    )


def valid_artifact() -> dict[str, object]:
    return build_artifact(request(), exact_charts())


class ArtifactConstructionTests(unittest.TestCase):
    def test_chart_id_and_filename_are_stable_and_distinguish_birth_inputs(self) -> None:
        first = request()
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        birth = people[0]["birth"]
        assert isinstance(birth, dict)
        birth["time"] = "07:43"
        second = parse_request(payload)

        self.assertEqual(chart_id(first), chart_id(first))
        self.assertNotEqual(chart_id(first), chart_id(second))
        self.assertRegex(output_name(first), r"synastry_Alex_Morgan_[0-9a-f]{12}\.json\Z")

    def test_identical_display_names_with_distinct_ids_do_not_collide(self) -> None:
        first_payload = exact_request()
        second_payload = copy.deepcopy(first_payload)
        for payload in (first_payload, second_payload):
            people = payload["people"]
            assert isinstance(people, list)
            people[0]["display_name"] = "Same"
            people[1]["display_name"] = "Same"
        second_people = second_payload["people"]
        assert isinstance(second_people, list)
        second_people[1]["id"] = "other-id"
        first = parse_request(first_payload)
        second = parse_request(second_payload)

        self.assertNotEqual(chart_id(first), chart_id(second))
        self.assertNotEqual(output_name(first), output_name(second))

    def test_minimal_privacy_omits_original_birth_metadata(self) -> None:
        artifact = build_artifact(request(), exact_charts())
        serialized = canonical_json(artifact).decode()

        for absent in ("residence", "place_label", "location_source", "pronouns"):
            self.assertNotIn(absent, serialized)

    def test_full_privacy_preserves_explicit_archival_provenance(self) -> None:
        artifact = build_artifact(request(privacy="full"), exact_charts())
        subject = artifact["subjects"][0]

        self.assertEqual(subject["birth"]["place_label"], "Paris")
        self.assertEqual(subject["birth"]["location_source"], "user supplied")

    def test_complete_artifact_has_integrity_measurements_aspects_overlays_and_limitations(self) -> None:
        artifact = build_artifact(request(include_derived=True), exact_charts(include_limitation=True))

        self.assertEqual(validate_artifact(artifact), artifact)
        self.assertEqual(artifact["integrity"]["algorithm"], "sha256")
        self.assertEqual(artifact["charts"][0]["positions"]["Sun"]["house"], 1)
        self.assertIn("sect", artifact["charts"][0]["derived"])
        self.assertTrue(artifact["aspects"])
        self.assertTrue(all(item["certainty"] == "exact" for item in artifact["aspects"]))
        self.assertTrue(artifact["overlays"])
        self.assertIn(
            "optional-ephemeris-data-missing",
            {item["code"] for item in artifact["limitations"]},
        )

    def test_resolved_precision_and_utc_interval_must_match_the_request(self) -> None:
        parsed = request()
        first, second = exact_charts()
        shifted_interval = replace(
            first.interval,
            start_utc=first.interval.start_utc + timedelta(minutes=1),
            end_utc=first.interval.end_utc + timedelta(minutes=1),
        )

        with self.assertRaisesRegex(SchemaError, "UTC interval"):
            build_artifact(parsed, (replace(first, interval=shifted_interval), second))
        with self.assertRaisesRegex(SchemaError, "precision"):
            build_artifact(parsed, (replace(first, precision_mode="window"), second))

    def test_uncertain_chart_uses_ranges_and_suppresses_exact_only_overlays(self) -> None:
        parsed = parse_request(mixed_precision_request())
        exact_first, _ = exact_charts()
        interval = resolve_interval(parsed.people[1].birth)
        interval = replace(interval, julian_start=2448782.0, julian_end=2448783.0)
        uncertain = ResolvedChart(
            subject_id="b",
            precision_mode="date-only",
            interval=interval,
            positions={
                "Sun": position(359.0, samples=(359.0, 1.0)),
                "Moon": position(100.0, samples=(100.0, 101.0)),
                "Mercury": PositionSamples(
                    longitude_degrees=(20.0, 21.0),
                    latitude_degrees=(0.0, 0.0),
                    distance_au=(1.0, 1.0),
                    longitudinal_speed_degrees_per_day=(-0.1, 0.1),
                ),
            },
            houses=None,
            angles={},
            provenance=provenance(),
            limitations=(),
        )

        artifact = build_artifact(parsed, (exact_first, uncertain))

        self.assertEqual(validate_artifact(artifact), artifact)
        uncertain_position = artifact["charts"][1]["positions"]["Sun"]
        self.assertEqual(uncertain_position["signs"], ["Ari", "Pis"])
        self.assertEqual(artifact["overlays"], [])
        self.assertTrue(all(item["certainty"] in {"confirmed", "possible"} for item in artifact["aspects"]))
        affected = {
            field for limitation in artifact["limitations"] for field in limitation["affected_fields"]
        }
        self.assertIn("charts.b.positions.Moon", affected)
        self.assertIn("charts.b.positions.Sun.signs", affected)
        self.assertIn("charts.b.positions.Mercury.retrograde_states", affected)


class SafeWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_existing_output_is_not_overwritten_without_explicit_flag(self) -> None:
        document = valid_artifact()
        written = write_artifact(document, self.directory)
        original = written.read_bytes()
        changed = copy.deepcopy(document)
        changed["limitations"] = [{"code": "changed", "message": "Changed.", "affected_fields": ["charts"]}]
        changed = attach_integrity(changed)

        with self.assertRaisesRegex(FileExistsError, "--overwrite"):
            write_artifact(changed, self.directory)

        self.assertEqual(written.read_bytes(), original)

    def test_write_is_canonical_user_only_and_integrity_round_trips(self) -> None:
        document = valid_artifact()

        written = write_artifact(document, self.directory)

        self.assertEqual(stat.S_IMODE(written.stat().st_mode), 0o600)
        self.assertEqual(written.read_bytes(), canonical_json(document) + b"\n")
        self.assertEqual(validate_artifact(json.loads(written.read_bytes())), document)

    def test_write_stays_atomic_when_descriptor_chmod_is_not_supported(self) -> None:
        document = valid_artifact()

        with patch("artifact.os.fchmod", None):
            written = write_artifact(document, self.directory)

        self.assertEqual(written.read_bytes(), canonical_json(document) + b"\n")

    def test_explicit_overwrite_atomically_replaces_the_complete_document(self) -> None:
        document = valid_artifact()
        written = write_artifact(document, self.directory)
        changed = copy.deepcopy(document)
        changed["limitations"] = [{"code": "changed", "message": "Changed.", "affected_fields": ["charts"]}]
        changed = attach_integrity(changed)

        replaced = write_artifact(changed, self.directory, overwrite=True)

        self.assertEqual(replaced, written)
        self.assertEqual(replaced.read_bytes(), canonical_json(changed) + b"\n")
        self.assertEqual(stat.S_IMODE(replaced.stat().st_mode), 0o600)

    def test_failed_atomic_overwrite_preserves_original_and_cleans_temporary_file(self) -> None:
        document = valid_artifact()
        written = write_artifact(document, self.directory)
        original = written.read_bytes()

        with (
            patch("artifact.os.replace", side_effect=OSError("simulated replace failure")),
            self.assertRaisesRegex(OSError, "simulated replace failure"),
        ):
            write_artifact(document, self.directory, overwrite=True)

        self.assertEqual(written.read_bytes(), original)
        self.assertEqual(list(self.directory.iterdir()), [written])

    def test_control_characters_and_noncanonical_chart_ids_cannot_steer_a_path(self) -> None:
        for field, value in (("display_name", "bad\nname"), ("chart_id", "../escape")):
            with self.subTest(field=field):
                document = valid_artifact()
                if field == "display_name":
                    document["subjects"][0][field] = value
                else:
                    document[field] = value
                document = attach_integrity(document)

                with self.assertRaisesRegex(ValueError, "safe filename|chart_id"):
                    write_artifact(document, self.directory)

        self.assertEqual(list(self.directory.iterdir()), [])

    def test_non_ascii_labels_fit_the_filesystem_component_byte_limit(self) -> None:
        payload = exact_request()
        people = payload["people"]
        assert isinstance(people, list)
        people[0]["display_name"] = "界" * 120
        people[1]["display_name"] = "語" * 120
        parsed = parse_request(payload)
        document = build_artifact(parsed, exact_charts())

        written = write_artifact(document, self.directory)

        self.assertLessEqual(len(written.name.encode("utf-8")), 255)
        self.assertEqual(written.name, output_name(parsed))
        self.assertEqual(validate_artifact(json.loads(written.read_bytes())), document)


if __name__ == "__main__":
    unittest.main()
