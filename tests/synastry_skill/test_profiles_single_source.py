"""Hold the v2 contract's profile ids and schema version to one declaration.

The request parser, the artifact schema, and the natal calculator each wrote the
same five strings. The artifact echoes the profiles its request named and the
schema then checks them, so the three copies agreed only because nobody had yet
bumped one — after which the calculator would write a request its own parser
rejected.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "astrology"
SHARED = PLUGIN / "shared"
OWNER = SHARED / "astro" / "request_schema.py"
sys.path.insert(0, str(SHARED))

import synastry_schema
from astro import request_schema

NAMES = ("SCHEMA_VERSION", "CALCULATION_PROFILE", "ASPECT_PROFILE", "DERIVED_PROFILE", "EVIDENCE_POLICY")
# A schema version written as a value: an assignment, a dataclass default, or a
# JSON key. "2.0" alone is not matched, because the ephemeris software version
# happens to share it and is a different fact.
_QUOTED_VERSION = "[\"']" + re.escape(request_schema.SCHEMA_VERSION) + "[\"']"
SCHEMA_VERSION_LITERAL = re.compile(
    r"""schema_version["']?\s*(?::\s*str\s*=|[:=])\s*""" + _QUOTED_VERSION,
    re.IGNORECASE,
)


def production_sources() -> list[Path]:
    """Every Python file the plugin ships, minus the owner and its vendored copies."""

    skills = PLUGIN / "skills"
    own = [path for path in sorted(skills.rglob("*.py")) if "shared" not in path.relative_to(skills).parts]
    return [path for path in sorted(SHARED.rglob("*.py")) if path != OWNER] + own


class ProfilesSingleSourceTests(unittest.TestCase):
    def test_the_artifact_schema_uses_the_request_schemas_declaration(self) -> None:
        for name in NAMES:
            with self.subTest(name=name):
                self.assertIs(getattr(synastry_schema, name), getattr(request_schema, name))

    def test_the_scan_reaches_every_module_that_once_held_a_copy(self) -> None:
        """A scan that silently skips the files it was written for proves nothing."""

        scanned = {path.relative_to(PLUGIN).as_posix() for path in production_sources()}
        for expected in (
            "shared/synastry_schema.py",
            "skills/natal-chart/scripts/compute_natal.py",
            "skills/synastry-reading/scripts/validate_synastry.py",
            "skills/synastry/scripts/artifact.py",
        ):
            with self.subTest(file=expected):
                self.assertIn(expected, scanned)

    def test_no_other_module_writes_a_profile_id_as_a_literal(self) -> None:
        profiles = [getattr(request_schema, name) for name in NAMES if name != "SCHEMA_VERSION"]
        for path in production_sources():
            source = path.read_text(encoding="utf-8")
            for profile in profiles:
                with self.subTest(file=str(path.relative_to(PLUGIN)), profile=profile):
                    self.assertNotRegex(
                        source,
                        rf"""["']{re.escape(profile)}["']""",
                        f"import {profile!r} from astro.request_schema instead",
                    )

    def test_no_other_module_writes_the_schema_version_as_a_literal(self) -> None:
        for path in production_sources():
            with self.subTest(file=str(path.relative_to(PLUGIN))):
                self.assertNotRegex(path.read_text(encoding="utf-8"), SCHEMA_VERSION_LITERAL)

    def test_the_pattern_catches_each_shape_a_copy_took(self) -> None:
        """The three shapes the removed copies were written in."""

        for shape in (
            'SCHEMA_VERSION = "2.0"',
            '"schema_version": "2.0",',
            'schema_version: str = "2.0"',
        ):
            with self.subTest(shape=shape):
                self.assertRegex(shape, SCHEMA_VERSION_LITERAL)
        self.assertNotRegex('SOFTWARE_VERSION = "2.0"', SCHEMA_VERSION_LITERAL)


if __name__ == "__main__":
    unittest.main()
