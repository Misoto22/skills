"""Hold the astrology vocabularies — aspects, signs, house systems — to one owner each.

The artifact schema, the synastry calculator, the reading validator and the
ephemeris each wrote their own copy of these lists. They agreed, so every check
passed; a twelfth aspect added to the geometry would have been computed, written,
and then rejected by the schema that validates the same artifact.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "astrology"
SHARED = PLUGIN / "shared"
SKILLS = PLUGIN / "skills"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(SKILLS / "synastry-reading" / "scripts"))

import synastry_schema
import validate_reading
from astro import astro_math, ephemeris, houses, request_schema

# A literal that only a copy of the vocabulary would write, and the one module
# allowed to write it.
OWNED_LITERALS = (
    (re.compile(r"""["']sesquiquadrate["']"""), SHARED / "astro" / "astro_math.py"),
    (re.compile(r"""["']biquintile["']"""), SHARED / "astro" / "astro_math.py"),
    (re.compile(r"""["']Ari["'],\s*["']Tau["']"""), SHARED / "astro" / "astro_math.py"),
    (re.compile(r"""["']regiomontanus["']"""), SHARED / "astro" / "houses.py"),
    (re.compile(r"""["']campanus["']"""), SHARED / "astro" / "houses.py"),
)


def production_sources() -> list[Path]:
    """Every Python file the plugin ships, minus the vendored copies of shared/."""

    own = [path for path in sorted(SKILLS.rglob("*.py")) if "shared" not in path.relative_to(SKILLS).parts]
    return sorted(SHARED.rglob("*.py")) + own


class VocabularyIdentityTests(unittest.TestCase):
    def test_the_schema_accepts_exactly_the_aspects_the_geometry_finds(self) -> None:
        self.assertEqual(astro_math.ASPECT_NAMES, {kind.name for kind in astro_math.ASPECT_KINDS})
        self.assertEqual(
            astro_math.MAJOR_ASPECT_NAMES,
            {kind.name for kind in astro_math.ASPECT_KINDS if kind.major},
        )
        self.assertIs(synastry_schema.ASPECT_NAMES, astro_math.ASPECT_NAMES)
        self.assertIs(synastry_schema.MAJOR_ASPECT_NAMES, astro_math.MAJOR_ASPECT_NAMES)

    def test_the_reading_validator_knows_the_same_aspects(self) -> None:
        self.assertIs(validate_reading.ASPECT_NAMES, astro_math.ASPECT_NAMES)

    def test_signs_are_the_geometry_layers_tuple(self) -> None:
        self.assertIs(synastry_schema.SIGNS, astro_math.SIGNS)
        self.assertEqual(synastry_schema._SIGN_SET, set(astro_math.SIGNS))

    def test_house_systems_are_one_table(self) -> None:
        self.assertIs(ephemeris.HOUSE_SYSTEMS, houses.HOUSE_SYSTEMS)
        self.assertEqual(houses.HOUSE_SYSTEM_NAMES, set(houses.HOUSE_SYSTEMS))
        self.assertIs(synastry_schema.HOUSE_SYSTEM_NAMES, houses.HOUSE_SYSTEM_NAMES)
        self.assertIs(request_schema.HOUSE_SYSTEM_NAMES, houses.HOUSE_SYSTEM_NAMES)


class NoCopiesTests(unittest.TestCase):
    def test_no_module_but_the_owner_writes_a_vocabulary(self) -> None:
        for pattern, owner in OWNED_LITERALS:
            for path in production_sources():
                if path == owner:
                    continue
                with self.subTest(file=str(path.relative_to(PLUGIN)), literal=pattern.pattern):
                    self.assertNotRegex(path.read_text(encoding="utf-8"), pattern)

    def test_each_owner_still_writes_its_vocabulary(self) -> None:
        """A pattern that matches nowhere guards nothing."""

        for pattern, owner in OWNED_LITERALS:
            with self.subTest(owner=owner.name, literal=pattern.pattern):
                self.assertRegex(owner.read_text(encoding="utf-8"), pattern)


class CopiedOutSkillTests(unittest.TestCase):
    def test_the_reading_validator_imports_from_a_lone_skill_copy(self) -> None:
        """An installer copies the skill directory and nothing beside it."""

        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "synastry-reading"
            shutil.copytree(
                SKILLS / "synastry-reading",
                skill,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            result = subprocess.run(
                [sys.executable, "-E", "-s", str(skill / "scripts" / "validate_reading.py"), "--help"],
                capture_output=True,
                text=True,
                check=False,
                cwd=directory,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
