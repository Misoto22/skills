"""Unit tests for the natal derivation layer, with no ephemeris in the loop.

`compute_natal.py` is covered end to end elsewhere. This exercises the derivation
itself against fixed longitudes, so a change in how a house or a dignity is
assigned fails here — on a machine with no Swiss data files, and without waiting
for a backend to agree.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASTROLOGY = ROOT / "plugins" / "astrology"
sys.path.insert(0, str(ASTROLOGY / "shared"))
sys.path.insert(0, str(ASTROLOGY / "skills" / "natal-chart" / "scripts"))

from astro.natal_envelope import NatalEnvelopeError, add_checksum, validate_envelope
from natal_artifact import NatalArtifactError, build_artifact, render_markdown, write_artifact_pair


@dataclass(frozen=True)
class FakeSamples:
    longitude_degrees: tuple[float, ...]
    longitudinal_speed_degrees_per_day: tuple[float, ...]


@dataclass(frozen=True)
class FakeInterval:
    start_utc: datetime
    end_utc: datetime


@dataclass(frozen=True)
class FakeProvenance:
    software_version: str = "test"
    binding_version: str = "test"
    requested_backend: str = "swiss"
    actual_backend: str = "moshier"
    timezone_source: str = "iana-zoneinfo"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeLimitation:
    code: str
    message: str
    affected_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeChart:
    subject_id: str
    precision_mode: str
    interval: FakeInterval
    positions: dict[str, FakeSamples]
    houses: tuple[float, ...] | None
    angles: dict[str, float]
    provenance: FakeProvenance
    limitations: tuple[FakeLimitation, ...]


def chart(**overrides) -> FakeChart:
    # Whole-sign cusps from 0° Aries, so a body's house follows its sign directly
    # and an assertion about one is readable without a second calculation.
    base = {
        "subject_id": "subject",
        "precision_mode": "exact",
        "interval": FakeInterval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 1, tzinfo=UTC)),
        "positions": {
            "Sun": FakeSamples((125.0,), (1.0,)),  # Leo — domicile
            "Moon": FakeSamples((95.0,), (13.0,)),  # Cancer — domicile
            "Mercury": FakeSamples((29.5,), (-0.5,)),  # Aries 29°30' — retrograde, critical
            "Venus": FakeSamples((155.0,), (1.1,)),  # Virgo — fall
            "Jupiter": FakeSamples((5.0,), (0.1,)),  # Aries 5°
            "Saturn": FakeSamples((215.0,), (0.03,)),  # Scorpio
        },
        "houses": tuple(float(index * 30) for index in range(12)),
        "angles": {"ascendant": 0.0, "medium_coeli": 270.0, "descendant": 180.0, "imum_coeli": 90.0},
        "provenance": FakeProvenance(),
        "limitations": (FakeLimitation("ephemeris-fallback", "Moshier was used."),),
    }
    return FakeChart(**(base | overrides))


def build(**overrides):
    return build_artifact(
        chart(**overrides),
        display_name="Subject A",
        house_system="whole-sign",
        major_orb=8.0,
        minor_orb=3.0,
    )


class DerivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.envelope = build()
        self.by_body = {p["body"]: p for p in self.envelope["positions"]}

    def test_sign_and_house_follow_the_longitude(self) -> None:
        self.assertEqual(self.by_body["Sun"]["sign"], "Leo")
        self.assertEqual(self.by_body["Sun"]["house"], 5)
        self.assertEqual(self.by_body["Moon"]["sign"], "Can")
        self.assertEqual(self.by_body["Moon"]["house"], 4)

    def test_classical_dignities_are_recorded_and_modern_ones_are_not(self) -> None:
        self.assertEqual(self.by_body["Sun"]["dignities"], ["domicile"])
        self.assertEqual(self.by_body["Moon"]["dignities"], ["domicile"])
        self.assertEqual(self.by_body["Venus"]["dignities"], ["fall"])
        # Uranus to Aquarius is a modern assignment and deliberately absent.
        self.assertNotIn("Uranus", json.dumps(self.envelope["methodology"]))
        self.assertIn("classical", self.envelope["methodology"]["dignities"])

    def test_retrograde_comes_from_speed_not_from_a_table(self) -> None:
        self.assertTrue(self.by_body["Mercury"]["retrograde"])
        self.assertFalse(self.by_body["Sun"]["retrograde"])

    def test_a_body_in_the_last_degree_is_flagged_critical(self) -> None:
        """A reading has to know which claims move if the birth minute is off."""

        self.assertTrue(self.by_body["Mercury"]["critical_degree"])
        self.assertFalse(self.by_body["Jupiter"]["critical_degree"])

    def test_each_aspect_pair_is_recorded_once_with_no_self_aspect(self) -> None:
        seen: set[tuple[str, ...]] = set()
        for aspect in self.envelope["aspects"]:
            self.assertNotEqual(aspect["left"], aspect["right"])
            pair = (*sorted((aspect["left"], aspect["right"])), aspect["kind"])
            self.assertNotIn(pair, seen)
            seen.add(pair)
        self.assertTrue(self.envelope["aspects"])

    def test_sect_is_derived_from_the_sun_and_states_its_basis(self) -> None:
        # Sun in house 5 is below the horizon under this convention.
        self.assertIs(self.envelope["sect"]["diurnal"], False)
        self.assertIn("Sun", self.envelope["sect"]["basis"])

    def test_lots_are_absent_when_a_required_body_is_missing(self) -> None:
        """Six or none. A partial classical set reads as a complete one."""

        self.assertEqual(len(self.envelope["lots"]), 6)
        positions = dict(chart().positions)
        del positions["Jupiter"]
        self.assertEqual(build(positions=positions)["lots"], [])

    def test_limitations_survive_into_the_artifact(self) -> None:
        codes = {item["code"] for item in self.envelope["limitations"]}
        self.assertIn("ephemeris-fallback", codes)

    def test_positions_are_ordered_so_two_runs_match(self) -> None:
        bodies = [p["body"] for p in self.envelope["positions"]]
        self.assertEqual(bodies, sorted(bodies))
        self.assertEqual(build()["checksum"], self.envelope["checksum"])


class RefusalTests(unittest.TestCase):
    def test_an_inexact_chart_is_refused(self) -> None:
        for mode in ("window", "date-only"):
            with self.subTest(mode=mode), self.assertRaises(NatalArtifactError):
                build(precision_mode=mode)

    def test_a_chart_without_houses_is_refused(self) -> None:
        with self.assertRaises(NatalArtifactError):
            build(houses=None)


class EnvelopeTests(unittest.TestCase):
    def test_the_checksum_covers_the_whole_envelope(self) -> None:
        envelope = build()
        validate_envelope(envelope)
        for mutate in (
            lambda d: d["positions"][0].__setitem__("sign", "Cap"),
            lambda d: d["angles"][0].__setitem__("longitude", 123.0),
            lambda d: d["subject"].__setitem__("name", "Other"),
            lambda d: d["limitations"].clear(),
        ):
            tampered = copy.deepcopy(envelope)
            mutate(tampered)
            with self.assertRaises(NatalEnvelopeError):
                validate_envelope(tampered)

    def test_re_adding_a_checksum_is_stable(self) -> None:
        envelope = build()
        self.assertEqual(add_checksum(envelope)["checksum"], envelope["checksum"])

    def test_the_markdown_is_data_only(self) -> None:
        body = render_markdown(build())
        for interpreting in ("suggests", "tends to", "commonly read", "means that"):
            self.assertNotIn(interpreting, body, interpreting)
        self.assertIn("no interpretation", body)

    def test_the_written_pair_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path, markdown_path = write_artifact_pair(build(), Path(directory))
            validate_envelope(json.loads(json_path.read_text(encoding="utf-8")))
            self.assertIn(build()["checksum"], markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
