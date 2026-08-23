"""Hold the hoisted astronomy to describing one chart at a time.

`shared/astro/` was lifted out of the synastry skill so a natal skill can rest on
the same code. That only stays true while nothing in it knows about a second
person. The moment a two-person concept leaks back in, the next skill to import
it inherits synastry's shape — and the duplication this move avoided comes back
as coupling instead.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "astrology" / "shared"
CORE = SHARED / "astro"
sys.path.insert(0, str(SHARED))

# The astronomy proper: hoisted out of synastry, and held below to knowing
# nothing about a second person.
MODULES = ("request_schema", "astro_math", "ephemeris")
# Artifact contracts two skills must agree on byte for byte. They belong here for
# the same reason — neither skill may import the other — but they are not
# astronomy, so the single-subject checks below do not apply to them.
CONTRACTS = ("natal_envelope",)


class AstroCoreTests(unittest.TestCase):
    def test_the_package_holds_exactly_what_was_hoisted(self) -> None:
        """A new file here is a decision, not a side effect: it reaches every skill."""

        present = sorted(path.stem for path in CORE.glob("*.py"))
        self.assertEqual(present, sorted([*MODULES, *CONTRACTS, "__init__"]))

    def test_nothing_in_it_imports_back_into_a_skill(self) -> None:
        """A shared module that reaches into one skill is not shared."""

        for name in (*MODULES, *CONTRACTS):
            tree = ast.parse((CORE / f"{name}.py").read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    with self.subTest(module=name, imported=node.module):
                        self.assertNotIn("artifact", node.module)
                        self.assertNotIn("synastry", node.module)
                        self.assertNotIn("compute_", node.module)

    def test_no_module_manipulates_sys_path(self) -> None:
        """Import wiring belongs to the entry point, not to a library."""

        for name in (*MODULES, *CONTRACTS):
            source = (CORE / f"{name}.py").read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertNotIn("sys.path", source)

    def test_the_single_subject_entry_point_takes_one_subject(self) -> None:
        """This is the signature a natal skill needs to exist at all."""

        from astro.ephemeris import resolve_subject
        from astro.request_schema import Subject

        annotations = resolve_subject.__annotations__
        self.assertEqual(annotations["subject"], "Subject")
        self.assertTrue(hasattr(Subject, "__dataclass_fields__"))
        self.assertIn("birth", Subject.__dataclass_fields__)

    def test_the_geometry_layer_names_no_two_person_concept(self) -> None:
        """Aspects and dignities are geometry, not a relationship.

        `left` and `right` are deliberately not checked: they are the names of
        two longitude sets, and passing the same set twice is exactly how a natal
        chart gets its own intra-chart aspects. What must stay out is the domain
        vocabulary of comparing two people.
        """

        source = (CORE / "astro_math.py").read_text(encoding="utf-8").lower()
        for two_person in ("synastry", "overlay", "partner", "composite", "relationship"):
            with self.subTest(term=two_person):
                self.assertNotIn(two_person, source)

    def test_the_geometry_layer_works_on_one_chart(self) -> None:
        """The claim the hoist rests on, exercised rather than asserted."""

        from astro.astro_math import find_aspects

        # One chart against itself is what a natal reading needs.
        chart = {"sun": 10.0, "moon": 100.0, "mars": 190.0}
        aspects = find_aspects(chart, chart)
        self.assertTrue(aspects, "a single chart produced no intra-chart aspects")
        kinds = {aspect.kind for aspect in aspects}
        self.assertIn("opposition", kinds, "sun at 10° and mars at 190° are opposed")
        self.assertIn("square", kinds, "sun at 10° and moon at 100° are square")

    def test_it_is_vendored_into_every_skill_that_ships_it(self) -> None:
        """A skill is copied out alone; a shared module has to travel with it."""

        for skill in ("synastry", "synastry-reading", "natal-chart", "natal-reading"):
            vendored = ROOT / "plugins" / "astrology" / "skills" / skill / "shared" / "astro"
            with self.subTest(skill=skill):
                self.assertTrue(vendored.is_dir(), f"{skill} did not receive shared/astro")
                for name in (*MODULES, *CONTRACTS):
                    self.assertEqual(
                        (vendored / f"{name}.py").read_bytes(),
                        (CORE / f"{name}.py").read_bytes(),
                        f"{skill}/{name}.py drifted from the plugin copy",
                    )


if __name__ == "__main__":
    unittest.main()
