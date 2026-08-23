"""Hold the mechanical-validator registry to actually dispatching on the skill.

The registry existed and was half-connected: one path read the entry, two others
reached module-level constants pinned to `MECHANICAL_VALIDATORS["synastry-reading"]`.
A second skill registered against that shape would have had synastry's validators
run over its artifact and received a wrong answer rather than an error — the
worst failure a registry can produce, because the guard it offers passes first.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run-evals.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("eval_harness_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_under_test"] = module
    spec.loader.exec_module(module)
    return module


HARNESS = load_harness()


class RegistryIsTheOnlySourceTests(unittest.TestCase):
    def test_no_module_level_constant_pins_one_skill(self) -> None:
        """A default argument naming one skill is how the wrong validator runs quietly."""

        source = SCRIPT.read_text(encoding="utf-8")
        for pinned in ("READING_VALIDATOR", "SOURCE_VALIDATOR", "SYNASTRY_SCHEMA"):
            with self.subTest(constant=pinned):
                self.assertNotIn(pinned, source)
        self.assertNotIn('MECHANICAL_VALIDATORS["synastry-reading"]', source)

    def test_every_registered_skill_declares_all_three_validators(self) -> None:
        for skill, entry in HARNESS.MECHANICAL_VALIDATORS.items():
            with self.subTest(skill=skill):
                self.assertEqual(sorted(entry), ["reading", "schema", "source"])
                for role, path in entry.items():
                    self.assertTrue(path.is_file(), f"{skill}.{role} points at {path}, which is absent")

    def test_an_unregistered_skill_fails_naming_itself(self) -> None:
        with self.assertRaises(KeyError) as caught:
            HARNESS.mechanical_validators("not-registered")
        self.assertIn("not-registered", caught.exception.args[0])

    def test_the_accessor_returns_the_entry_for_the_skill_asked_for(self) -> None:
        """The whole point. A second entry must not resolve to the first one's files."""

        other = {role: Path(f"/nowhere/{role}.py") for role in ("reading", "source", "schema")}
        original = dict(HARNESS.MECHANICAL_VALIDATORS)
        HARNESS.MECHANICAL_VALIDATORS["fake-reading"] = other
        try:
            self.assertEqual(HARNESS.mechanical_validators("fake-reading"), other)
            self.assertEqual(
                HARNESS.mechanical_validators("synastry-reading"),
                original["synastry-reading"],
            )
            self.assertNotEqual(
                HARNESS.mechanical_validators("fake-reading"),
                HARNESS.mechanical_validators("synastry-reading"),
            )
        finally:
            HARNESS.MECHANICAL_VALIDATORS.clear()
            HARNESS.MECHANICAL_VALIDATORS.update(original)


class DispatchTakesTheSkillTests(unittest.TestCase):
    """Both of these dropped the skill their caller already held."""

    def test_the_schema_loader_takes_a_skill(self) -> None:
        self.assertIn("skill", HARNESS._schema_module.__wrapped__.__code__.co_varnames[:1])

    def test_the_ledger_builder_takes_a_skill(self) -> None:
        self.assertEqual(HARNESS._validated_ledger.__code__.co_varnames[0], "skill")

    def test_the_reading_validator_has_no_default(self) -> None:
        """A default here is a module-level constant wearing a parameter name."""

        import inspect

        signature = inspect.signature(HARNESS._validator_problems)
        parameter = signature.parameters["reading_validator"]
        self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_an_unregistered_skill_is_reported_rather_than_silently_skipped(self) -> None:
        problems = HARNESS._mechanical_failures("not-registered", {"fixture": "anything.json"}, "draft")
        self.assertTrue(problems)
        self.assertIn("not-registered", problems[0])
        self.assertIn("without ever being checked", problems[0])

    def test_a_case_without_a_fixture_needs_no_registration(self) -> None:
        self.assertEqual(HARNESS._mechanical_failures("not-registered", {}, "draft"), [])


if __name__ == "__main__":
    unittest.main()
