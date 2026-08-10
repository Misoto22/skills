from __future__ import annotations

import importlib.metadata
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins" / "astrology" / "skills" / "synastry" / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import swisseph as swe
except ImportError as error:  # pragma: no cover - the failure is the intended dependency guard
    raise AssertionError(
        "ephemeris integration tests require the pinned synastry requirements on Python 3.11-3.13"
    ) from error

from ephemeris import EphemerisError, resolve_subject, set_ephemeris_path

from .test_ephemeris import exact_subject, moshier_options, swiss_options


class RealBindingTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_ephemeris_path(None, swe_module=swe)

    def test_pinned_runtime_versions_are_installed(self) -> None:
        self.assertEqual(importlib.metadata.version("pyswisseph"), "2.10.3.2")
        self.assertEqual(importlib.metadata.version("tzdata"), "2026.3")

    def test_empty_data_path_has_deterministic_moshier_sun_and_moon(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            set_ephemeris_path(directory, swe_module=swe)

            chart = resolve_subject(exact_subject(), moshier_options(), swe_module=swe)

        self.assertEqual(chart.provenance.actual_backend, "moshier")
        self.assertEqual(chart.provenance.data_path, directory)
        self.assertAlmostEqual(
            chart.positions["Sun"].longitude_degrees[0],
            353.423362902435,
            delta=1e-6,
        )
        self.assertAlmostEqual(
            chart.positions["Moon"].longitude_degrees[0],
            205.14037573842518,
            delta=1e-6,
        )
        self.assertIn("ephemeris-fallback", {item.code for item in chart.limitations})

    def test_empty_data_path_is_rejected_by_strict_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            set_ephemeris_path(directory, swe_module=swe)

            with self.assertRaisesRegex(EphemerisError, "requested Swiss.*used Moshier"):
                resolve_subject(exact_subject(), swiss_options(), swe_module=swe)


if __name__ == "__main__":
    unittest.main()
