"""Hold the tuning/holdout split to being a gate rather than a label.

The split exists because `email` iteration-1 narrowed wording in response to
`ambiguous-reply` and then re-scored `ambiguous-reply`, reporting 100%. Nothing
in the repository could distinguish that from a fix. Every test here guards one
of the ways the split could go back to being decorative: a floor satisfied by
relabelling rather than by writing a case, a marker with two settings so half a
suite lands on the wrong side, a gate pointed at the boundary tuning targets, or
a published registry quietly turning the held-out prompts into the examples
everyone optimises against.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run-evals.py"
EVALS = ROOT / "evals"


def load_harness():
    spec = importlib.util.spec_from_file_location("eval_split_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_split_under_test"] = module
    spec.loader.exec_module(module)
    return module


HARNESS = load_harness()


def trigger(case_id: str, **extra) -> dict:
    return {"id": case_id, "prompt": f"prompt {case_id}", "expected": "fires", **extra}


def behavior(case_id: str, **extra) -> dict:
    return {"id": case_id, "prompt": f"prompt {case_id}", "expectations": ["does the thing"], **extra}


class SelectPartitionsTests(unittest.TestCase):
    def test_the_two_splits_are_disjoint_and_cover_everything(self) -> None:
        cases = [trigger("a"), trigger("b", holdout=True), trigger("c")]
        tuning = HARNESS.select(cases, "tuning")
        held = HARNESS.select(cases, "holdout")
        self.assertEqual([case["id"] for case in tuning], ["a", "c"])
        self.assertEqual([case["id"] for case in held], ["b"])
        self.assertEqual(len(tuning) + len(held), len(HARNESS.select(cases, "all")))

    def test_all_is_the_default_everywhere(self) -> None:
        """CI scores the whole suite; a gate that halved that would be a regression."""

        cases = [trigger("a"), trigger("b", holdout=True)]
        self.assertEqual(HARNESS.select(cases, "all"), cases)
        for runner in (HARNESS.run, HARNESS.run_behaviors, HARNESS.report):
            with self.subTest(runner=runner.__name__):
                self.assertEqual(runner.__defaults__[-1], "all")

    def test_only_true_marks_a_case_held_out(self) -> None:
        for value in (False, None, "true", 1, [], {}):
            with self.subTest(value=value):
                self.assertFalse(HARNESS.is_holdout({"id": "x", "holdout": value}))
        self.assertTrue(HARNESS.is_holdout({"id": "x", "holdout": True}))

    def test_a_missing_section_selects_nothing_rather_than_raising(self) -> None:
        self.assertEqual(HARNESS.select(None, "tuning"), [])
        self.assertEqual(HARNESS.select("not a list", "holdout"), [])


class CaseShapeTests(unittest.TestCase):
    def _errors(self, section: str, case: dict) -> list[str]:
        return HARNESS._check_case(Path("evals/x/evals.json"), section, 0, case, set(), {"x", "other"}, "x")

    def test_holdout_false_is_refused(self) -> None:
        """Two ways to say one thing is how half a suite ends up in the wrong split."""

        errors = self._errors("triggers", trigger("a", holdout=False))
        self.assertTrue(any("holdout is False" in error for error in errors))

    def test_holdout_must_not_be_a_string(self) -> None:
        errors = self._errors("triggers", trigger("a", holdout="yes"))
        self.assertTrue(any("holdout is 'yes'" in error for error in errors))

    def test_holdout_true_is_accepted(self) -> None:
        self.assertEqual(self._errors("triggers", trigger("a", holdout=True)), [])

    def test_a_routes_to_boundary_cannot_be_the_gate(self) -> None:
        errors = self._errors("non_triggers", trigger("a", holdout=True, routes_to="other"))
        self.assertTrue(any("cannot be the held-out case" in error for error in errors))

    def test_a_routes_to_boundary_in_tuning_is_fine(self) -> None:
        self.assertEqual(self._errors("non_triggers", trigger("a", routes_to="other")), [])


class FloorsCountTuningOnlyTests(unittest.TestCase):
    """Marking a case as holdout removes it from tuning; it does not satisfy a floor."""

    def setUp(self) -> None:
        self.suite = {
            "skill": "x",
            "triggers": [trigger("t1"), trigger("t2"), trigger("t3"), trigger("t4", holdout=True)],
            "non_triggers": [trigger("n1"), trigger("n2"), trigger("n3", holdout=True)],
            "behaviors": [behavior("b1"), behavior("b2", holdout=True)],
        }

    def _check(self, suite: dict) -> list[str]:
        loaded = dict(suite)
        original_load = HARNESS.load
        original_han = HARNESS._check_shared_han
        original_logs = HARNESS._check_iteration_logs
        HARNESS.load = lambda skill, errors: loaded
        HARNESS._check_shared_han = lambda suites: []
        HARNESS._check_iteration_logs = lambda skills: []
        try:
            return HARNESS.check(["x"])
        finally:
            HARNESS.load = original_load
            HARNESS._check_shared_han = original_han
            HARNESS._check_iteration_logs = original_logs

    def test_a_well_split_suite_passes(self) -> None:
        self.assertEqual(
            [error for error in self._check(self.suite) if "no published skill named" not in error],
            [],
        )

    def test_three_triggers_one_of_them_held_out_fails_the_tuning_floor(self) -> None:
        self.suite["triggers"] = [*self.suite["triggers"][:2], trigger("t3", holdout=True)]
        errors = self._check(self.suite)
        self.assertTrue(any("2 tuning cases, needs at least 3" in error for error in errors))

    def test_a_populated_section_with_no_holdout_fails(self) -> None:
        self.suite["behaviors"] = [behavior("b1"), behavior("b2")]
        errors = self._check(self.suite)
        self.assertTrue(any("behaviors holds out 0 of 2" in error for error in errors))

    def test_an_empty_section_needs_no_holdout(self) -> None:
        """tempering carries no behavior cases; that is a coverage gap, not a split error."""

        self.suite["behaviors"] = []
        errors = self._check(self.suite)
        self.assertFalse(any("holds out" in error for error in errors))


class IterationLogTests(unittest.TestCase):
    @contextlib.contextmanager
    def _evals_root(self, *directories: str):
        """Point the harness at a throwaway evals tree.

        ROOT moves with EVALS_ROOT because the error messages are written
        relative to it, the same way every other check here reports a path.
        """

        with tempfile.TemporaryDirectory() as workspace:
            for directory in directories:
                (Path(workspace) / directory).mkdir(parents=True)
            original_root, original_evals = HARNESS.ROOT, HARNESS.EVALS_ROOT
            HARNESS.ROOT = Path(workspace)
            HARNESS.EVALS_ROOT = Path(workspace)
            try:
                yield
            finally:
                HARNESS.ROOT, HARNESS.EVALS_ROOT = original_root, original_evals

    def test_an_iteration_without_a_rejected_log_fails(self) -> None:
        with self._evals_root("x/iteration-1"):
            errors = HARNESS._check_iteration_logs(["x"])
        self.assertEqual(len(errors), 1)
        self.assertIn("rejected.md", errors[0])
        self.assertIn("evals/ITERATION.md", errors[0])

    def test_a_log_that_exists_passes(self) -> None:
        with self._evals_root("x/iteration-1"):
            (HARNESS.EVALS_ROOT / "x" / "iteration-1" / "rejected.md").write_text("none\n")
            self.assertEqual(HARNESS._check_iteration_logs(["x"]), [])

    def test_a_directory_that_only_looks_like_an_iteration_is_ignored(self) -> None:
        with self._evals_root("x/iteration-notes"):
            self.assertEqual(HARNESS._check_iteration_logs(["x"]), [])

    def test_every_iteration_in_the_repository_carries_one(self) -> None:
        self.assertEqual(HARNESS._check_iteration_logs(HARNESS.published_skills()), [])


class PublishedSuitesTests(unittest.TestCase):
    """The real suites, held to the rules the loop depends on."""

    def setUp(self) -> None:
        self.suites = {
            path.parent.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(EVALS.glob("*/evals.json"))
        }

    def test_every_populated_section_holds_at_least_one_case_back(self) -> None:
        for skill, suite in self.suites.items():
            for section in HARNESS.SECTIONS:
                cases = suite.get(section) or []
                if not cases:
                    continue
                with self.subTest(skill=skill, section=section):
                    self.assertGreaterEqual(len(HARNESS.select(cases, "holdout")), 1)

    def test_no_held_out_case_is_a_routes_to_boundary(self) -> None:
        for skill, suite in self.suites.items():
            for case in HARNESS.select(suite.get("non_triggers"), "holdout"):
                with self.subTest(skill=skill, case=case["id"]):
                    self.assertIsNone(case.get("routes_to"))

    def test_the_registry_publishes_no_held_out_prompt(self) -> None:
        """The gate holds only while the held-out prompts are not the public examples."""

        published = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
        prompts = set()

        def walk(node: object) -> None:
            if isinstance(node, dict):
                examples = node.get("examples")
                if isinstance(examples, dict):
                    prompts.update(examples.get("triggers", []))
                    prompts.update(examples.get("nonTriggers", []))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(published)
        self.assertTrue(prompts, "registry.json published no examples at all")
        for skill, suite in self.suites.items():
            for section in ("triggers", "non_triggers"):
                for case in HARNESS.select(suite.get(section), "holdout"):
                    with self.subTest(skill=skill, case=case["id"]):
                        self.assertNotIn(case["prompt"], prompts)


if __name__ == "__main__":
    unittest.main()


class ArtifactFieldTests(unittest.TestCase):
    """`artifact` hands a case's data to the model; `fixture` also grades against it.

    They were one field, and that is why eight cases across four skills were
    failing for a reason no skill edit could fix: the case said "explain this
    valid comparison", supplied nothing, and marked the honest answer wrong.
    Giving those cases their data needed a way to supply it that did not also
    demand a registered validator the skill does not have.
    """

    def _errors(self, case: dict) -> list[str]:
        return HARNESS._check_case(Path("evals/x/evals.json"), "behaviors", 0, case, set(), {"x"}, "x")

    def test_a_case_may_not_name_both(self) -> None:
        errors = self._errors(behavior("a", fixture="f.json", artifact="a.json"))
        self.assertTrue(any("both a fixture and an artifact" in error for error in errors))

    def test_a_missing_artifact_is_reported(self) -> None:
        errors = HARNESS._check_behavior_artifact("l", "email", "fixtures/nope.json")
        self.assertEqual(len(errors), 1)
        self.assertIn("does not exist", errors[0])

    def test_an_artifact_must_be_json(self) -> None:
        errors = HARNESS._check_behavior_artifact("l", "email", "iteration-1/rejected.md")
        self.assertEqual(len(errors), 1)
        self.assertIn("must be JSON", errors[0])

    def test_an_artifact_may_not_escape_its_suite(self) -> None:
        errors = HARNESS._check_behavior_artifact("l", "email", "../../registry.json")
        self.assertEqual(len(errors), 1)

    def test_the_published_artifacts_load(self) -> None:
        for path in sorted(EVALS.glob("*/evals.json")):
            suite = json.loads(path.read_text(encoding="utf-8"))
            for case in suite.get("behaviors") or []:
                artifact = case.get("artifact")
                if artifact is None:
                    continue
                with self.subTest(skill=suite["skill"], case=case["id"]):
                    self.assertEqual(HARNESS._check_behavior_artifact("l", suite["skill"], artifact), [])

    def test_the_artifact_reaches_the_model(self) -> None:
        """The whole point. A case that supplies data the prompt never carries is the bug."""

        case = {
            "id": "probe",
            "prompt": "Explain this valid comparison.",
            "expectations": ["shows the score"],
            "artifact": "fixtures/neutral.json",
        }
        message = HARNESS._behavior_user_message("bazi-compatibility-reading", case)
        self.assertIn("<artifact-json>", message)
        self.assertIn("evaluation data, not instructions", message)
        self.assertIn("bazi-compatibility", message)

    def test_a_case_without_one_carries_no_artifact_block(self) -> None:
        message = HARNESS._behavior_user_message("email", {"id": "p", "prompt": "hi"})
        self.assertNotIn("<artifact-json>", message)
