from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evals.runtime import (
    BudgetLedger,
    CostReservation,
    compare_iteration_runs,
    compare_runs,
    fingerprint,
    make_run_record,
)
from scripts.evals.tools import ToolSandbox, _redact_sandbox_paths


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_sensitive_to_eval_data(self) -> None:
        first = fingerprint({"b": 2, "a": 1})
        self.assertEqual(first, fingerprint({"a": 1, "b": 2}))
        self.assertNotEqual(first, fingerprint({"a": 1, "b": 3}))

    def test_run_record_keeps_candidate_and_judge_separate(self) -> None:
        record = make_run_record(
            suite_fingerprint="suite",
            scoring_fingerprint="scoring",
            skill_fingerprint="before",
            candidate={"provider": "gateway", "model": "candidate"},
            judge={"provider": "gateway", "model": "judge"},
        )
        self.assertEqual(record["models"]["candidate"]["model"], "candidate")
        self.assertEqual(record["models"]["judge"]["model"], "judge")
        self.assertNotIn("api_key", json.dumps(record).lower())


class BudgetTests(unittest.TestCase):
    def test_reservation_uses_worst_case_retries_and_both_models(self) -> None:
        reservation = CostReservation.from_plan(
            cases=2,
            samples=3,
            retries=2,
            candidate_input_tokens=100,
            candidate_output_tokens=50,
            judge_input_tokens=80,
            judge_output_tokens=20,
            candidate_cny_per_million_input=10,
            candidate_cny_per_million_output=20,
            judge_cny_per_million_input=30,
            judge_cny_per_million_output=40,
        )
        self.assertEqual(reservation.calls, 36)
        self.assertAlmostEqual(reservation.cny, 0.0936)

    def test_shared_ledger_refuses_a_second_process_over_the_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = BudgetLedger(Path(temporary) / "ledger.json", limit_cny=1.0)
            ledger.reserve("first", 0.7)
            with self.assertRaisesRegex(ValueError, "budget"):
                ledger.reserve("second", 0.4)
            self.assertAlmostEqual(ledger.snapshot()["reserved_cny"], 0.7)

    def test_untrusted_usage_does_not_release_a_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = BudgetLedger(Path(temporary) / "ledger.json", limit_cny=1.0)
            ledger.reserve("run", 0.8)
            ledger.settle("run", actual_cny=0.2, usage_trusted=False)
            self.assertAlmostEqual(ledger.snapshot()["reserved_cny"], 0.8)

    def test_corrupt_nonempty_ledger_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "corrupt"):
                BudgetLedger(path, limit_cny=1).reserve("run", 0.1)

    def test_valid_json_with_negative_or_nan_held_cost_fails_closed(self) -> None:
        for held in (-1, float("nan")):
            with self.subTest(held=held), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "ledger.json"
                path.write_text(
                    json.dumps(
                        {
                            "currency": "CNY",
                            "limit_cny": 1,
                            "runs": {
                                "tampered": {
                                    "reserved_cny": 0.5,
                                    "held_cny": held,
                                    "usage_trusted": False,
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "corrupt"):
                    BudgetLedger(path, limit_cny=1).snapshot()

    def test_nonfinite_values_are_rejected_and_overspend_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = BudgetLedger(Path(temporary) / "ledger.json", limit_cny=1)
            with self.assertRaises(ValueError):
                ledger.reserve("bad", math.nan)
            ledger.reserve("run", 0.8)
            with self.assertRaisesRegex(ValueError, "breached"):
                ledger.settle("run", actual_cny=1.2, usage_trusted=True)
            item = ledger.snapshot()["runs"]["run"]
            self.assertEqual(item["actual_cny"], 1.2)
            self.assertTrue(item["budget_breached"])

    def test_nonfinite_limit_and_prices_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            BudgetLedger(Path(temporary) / "ledger.json", limit_cny=math.nan)
        with self.assertRaises(ValueError):
            CostReservation.from_plan(
                cases=1,
                samples=1,
                retries=0,
                candidate_input_tokens=1,
                candidate_output_tokens=1,
                judge_input_tokens=1,
                judge_output_tokens=1,
                candidate_cny_per_million_input=math.inf,
                candidate_cny_per_million_output=1,
                judge_cny_per_million_input=1,
                judge_cny_per_million_output=1,
            )


class GateTests(unittest.TestCase):
    def _run(self, skill: str, tuning: tuple[int, int], holdout: tuple[int, int]) -> dict:
        cases = []
        for split, counts in (("tuning", tuning), ("holdout", holdout)):
            cases.extend(
                {
                    "id": f"{split}-{index}",
                    "sample": 1,
                    "arm": "with",
                    "split": split,
                    "status": "pass" if index < counts[0] else "fail",
                    "criteria": [{"passed": index < counts[0]}],
                    "mechanical": [],
                }
                for index in range(counts[1])
            )
        return {
            "run_id": skill,
            "provenance": {"head": "abc123", "dirty": False, "dirty_fingerprint": "clean"},
            "fingerprints": {"suite": "same", "scoring": "same", "skill": skill},
            "resolved_models": {"candidate": ["candidate-v1"], "judge": ["judge-v1"]},
            "model_identity_trusted": True,
            "model_identity_fingerprint": "deployment-v1",
            "judge_independence": {"configured_separately": True, "resolved_distinct": True},
            "usage_trusted": True,
            "actual_cost": {"currency": "CNY", "amount": 0.1, "trusted": True},
            "summary": {
                "with": {
                    "tuning": {"passed": tuning[0], "scored": tuning[1], "void": 0},
                    "holdout": {"passed": holdout[0], "scored": holdout[1], "void": 0},
                }
            },
            "cases": cases,
        }

    def test_gate_allows_skill_change_when_eval_and_scoring_match(self) -> None:
        verdict = compare_runs(self._run("before", (7, 10), (4, 5)), self._run("after", (8, 10), (4, 5)))
        self.assertEqual(verdict["status"], "pass")

    def test_gate_rejects_eval_or_scoring_drift(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        after["fingerprints"]["suite"] = "changed"
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")

    def test_gate_requires_tuning_gain_and_no_holdout_loss(self) -> None:
        self.assertEqual(
            compare_runs(self._run("before", (7, 10), (4, 5)), self._run("after", (7, 10), (4, 5)))["status"],
            "fail",
        )
        self.assertEqual(
            compare_runs(self._run("before", (7, 10), (4, 5)), self._run("after", (8, 10), (3, 5)))["status"],
            "fail",
        )

    def test_void_or_changed_sample_count_is_inconclusive(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        after["summary"]["with"]["holdout"]["void"] = 1
        after["summary"]["with"]["holdout"]["scored"] -= 1
        after["cases"][-1]["status"] = "void"
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")

    def test_gate_rejects_duplicate_runs_and_case_drift(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        after["run_id"] = before["run_id"]
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")

    def test_gate_rejects_missing_or_changed_resolved_models(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        del after["resolved_models"]
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")
        after = self._run("after", (8, 10), (4, 5))
        after["resolved_models"]["candidate"] = ["candidate-v2"]
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")
        after["run_id"] = "after"
        after["cases"][0]["id"] = "different"
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")

    def test_gate_requires_attested_deployment_identity(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        before["model_identity_trusted"] = False
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")
        before = self._run("before", (7, 10), (4, 5))
        after["model_identity_fingerprint"] = "deployment-v2"
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")

    def test_malformed_counts_and_threshold_are_inconclusive(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        after["summary"]["with"]["tuning"]["passed"] = True
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")
        self.assertEqual(
            compare_runs(
                before,
                self._run("after", (8, 10), (4, 5)),
                minimum_tuning_gain=math.nan,
            )["status"],
            "inconclusive",
        )

    def test_gate_rejects_non_object_case_entries(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        after["cases"].append("malformed")
        verdict = compare_runs(before, after)
        self.assertEqual(verdict["status"], "inconclusive")
        self.assertIn("non-object", verdict["reason"])

    def test_unchanged_skill_instruction_is_not_an_iteration(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        after["fingerprints"]["skill"] = before["fingerprints"]["skill"]
        self.assertEqual(compare_runs(before, after)["status"], "inconclusive")

    def test_four_phase_gate_combines_single_split_runs(self) -> None:
        def phase(skill: str, split: str, counts: tuple[int, int]) -> dict:
            run = self._run(
                skill, counts if split == "tuning" else (0, 0), counts if split == "holdout" else (0, 0)
            )
            run["run_id"] = f"{skill}-{split}"
            run["run_config"] = {"split": split}
            run["cases"] = [item for item in run["cases"] if item["split"] == split]
            return run

        verdict = compare_iteration_runs(
            phase("before", "tuning", (7, 10)),
            phase("before", "holdout", (4, 5)),
            phase("after", "tuning", (8, 10)),
            phase("after", "holdout", (4, 5)),
        )
        self.assertEqual(verdict["status"], "pass")

    def test_same_resolved_model_is_reported_but_does_not_block_gate(self) -> None:
        before = self._run("before", (7, 10), (4, 5))
        after = self._run("after", (8, 10), (4, 5))
        for run in (before, after):
            run["resolved_models"] = {"candidate": ["same-v1"], "judge": ["same-v1"]}
            run["judge_independence"]["resolved_distinct"] = False
        self.assertEqual(compare_runs(before, after)["status"], "pass")

    def test_four_phase_gate_rejects_missing_or_drifted_provenance(self) -> None:
        def phase(skill: str, split: str, counts: tuple[int, int]) -> dict:
            run = self._run(
                skill,
                counts if split == "tuning" else (0, 0),
                counts if split == "holdout" else (0, 0),
            )
            run["run_id"] = f"{skill}-{split}"
            run["run_config"] = {"split": split}
            run["cases"] = [item for item in run["cases"] if item["split"] == split]
            return run

        before_tuning = phase("before", "tuning", (7, 10))
        before_holdout = phase("before", "holdout", (4, 5))
        before_holdout["provenance"]["dirty_fingerprint"] = "drifted"
        verdict = compare_iteration_runs(
            before_tuning,
            before_holdout,
            phase("after", "tuning", (8, 10)),
            phase("after", "holdout", (4, 5)),
        )
        self.assertEqual(verdict["status"], "inconclusive")
        self.assertIn("provenance differs", verdict["reason"])


class ToolSandboxTests(unittest.TestCase):
    def test_model_can_write_and_run_only_named_commands_in_a_fixture_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "fixture"
            source.mkdir()
            (source / "input.txt").write_text("hello", encoding="utf-8")
            sandbox = ToolSandbox(
                source,
                {
                    "copy": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('out.txt').write_text(Path('input.txt').read_text())",
                    ]
                },
            )
            try:
                command_definition = next(
                    item for item in sandbox.definitions() if item["function"]["name"] == "run_command"
                )
                self.assertEqual(
                    command_definition["function"]["parameters"]["properties"]["command"]["enum"],
                    ["copy"],
                )
                self.assertIn("hello", sandbox.call("read_file", {"path": "input.txt"}))
                sandbox.call("run_command", {"command": "copy"})
                self.assertEqual(sandbox.call("read_file", {"path": "out.txt"}), "hello")
                with self.assertRaisesRegex(ValueError, "declared"):
                    sandbox.call("run_command", {"command": "anything-else"})
                with self.assertRaisesRegex(ValueError, "sandbox"):
                    sandbox.call("read_file", {"path": "../outside"})
            finally:
                sandbox.close()

    def test_command_output_redacts_the_machine_local_sandbox_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "fixture"
            source.mkdir()
            sandbox = ToolSandbox(
                source,
                {
                    "pwd": [
                        sys.executable,
                        "-c",
                        "import os; print(os.getcwd())",
                    ]
                },
            )
            try:
                result = sandbox.call("run_command", {"command": "pwd"})
                self.assertEqual(json.loads(result)["stdout"].strip(), ".")
                self.assertNotIn(str(sandbox.root), result)
            finally:
                sandbox.close()

    def test_path_redaction_handles_both_macos_var_alias_orders(self) -> None:
        root = Path("/var/folders/example/workspace")
        temporary = Path("/var/folders/example")
        text = "/private/var/folders/example/workspace\n/var/folders/example/workspace\n"
        self.assertEqual(_redact_sandbox_paths(text, root, temporary), ".\n.\n")

    def test_child_environment_contains_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "fixture"
            source.mkdir()
            os.environ["ANTHROPIC_API_KEY"] = "sentinel-secret"
            self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
            sandbox = ToolSandbox(
                source, {"env": [sys.executable, "-c", "import os; print(repr(dict(os.environ)))"]}
            )
            try:
                output = sandbox.call("run_command", {"command": "env"})
                self.assertNotIn("API_KEY", output)
                self.assertNotIn("TOKEN", output)
                self.assertNotIn("sentinel-secret", output)
            finally:
                sandbox.close()

    def test_fixture_symlinks_and_credential_environment_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "fixture"
            fixture.mkdir()
            outside = root / "outside"
            outside.write_text("private", encoding="utf-8")
            (fixture / "link").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlink"):
                ToolSandbox(fixture, {})
            (fixture / "link").unlink()
            sandbox = ToolSandbox(
                fixture,
                {"bad": {"argv": [sys.executable, "-c", "print('x')"], "env": {"GH_TOKEN": "."}}},
            )
            try:
                with self.assertRaisesRegex(ValueError, "credential"):
                    sandbox.call("run_command", {"command": "bad"})
            finally:
                sandbox.close()


if __name__ == "__main__":
    unittest.main()
