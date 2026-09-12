from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evals.runtime import make_run_record

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "compare-eval-runs.py"


def phase_record(*, split: str, passed: int, scored: int, version: str) -> dict:
    cases = [
        {
            "id": f"{split}-{index}",
            "sample": 1,
            "arm": "with",
            "split": split,
            "status": "pass" if index < passed else "fail",
            "criteria": [{"passed": index < passed}],
            "mechanical": [],
        }
        for index in range(scored)
    ]
    record = make_run_record(
        suite_fingerprint="suite",
        scoring_fingerprint="scoring",
        skill_fingerprint=version,
        candidate={"provider": "gateway", "model": "candidate-v1", "base_url_label": "scoped-gateway"},
        judge={"provider": "gateway", "model": "judge-v1", "base_url_label": "scoped-gateway"},
    )
    record.update(
        {
            "run_id": f"{version}-{split}",
            "run_config": {"split": split},
            "provenance": {"head": "a" * 40, "dirty": False, "dirty_fingerprint": "b" * 64},
            "resolved_models": {"candidate": ["candidate-v1"], "judge": ["judge-v1"]},
            "model_identity_trusted": True,
            "model_identity_fingerprint": "deployment-v1",
            "judge_independence": {"configured_separately": True, "resolved_distinct": True},
            "usage_trusted": True,
            "actual_cost": {"currency": "CNY", "trusted": True, "amount": 0.01},
            "cases": cases,
        }
    )
    return record


class IterationGateCliTests(unittest.TestCase):
    def phases(
        self,
        *,
        before_tuning=(1, 2),
        before_holdout=(1, 2),
        after_tuning=(2, 2),
        after_holdout=(1, 2),
    ) -> dict[str, dict]:
        return {
            "before_tuning": phase_record(
                split="tuning", passed=before_tuning[0], scored=before_tuning[1], version="before"
            ),
            "before_holdout": phase_record(
                split="holdout", passed=before_holdout[0], scored=before_holdout[1], version="before"
            ),
            "after_tuning": phase_record(
                split="tuning", passed=after_tuning[0], scored=after_tuning[1], version="after"
            ),
            "after_holdout": phase_record(
                split="holdout", passed=after_holdout[0], scored=after_holdout[1], version="after"
            ),
        }

    def invoke(self, phases: dict[str, dict], *extra: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for label, record in phases.items():
                path = root / f"{label}.json"
                path.write_text(json.dumps(record), encoding="utf-8")
                paths[label] = path
            return subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--before-tuning",
                    str(paths["before_tuning"]),
                    "--before-holdout",
                    str(paths["before_holdout"]),
                    "--after-tuning",
                    str(paths["after_tuning"]),
                    "--after-holdout",
                    str(paths["after_holdout"]),
                    *extra,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_passes_only_when_tuning_rises_and_holdout_does_not_fall(self) -> None:
        result = self.invoke(self.phases())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "pass")

    def test_fails_when_holdout_falls(self) -> None:
        result = self.invoke(self.phases(before_holdout=(2, 2), after_holdout=(1, 2)))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "fail")

    def test_inconclusive_when_split_samples_differ(self) -> None:
        result = self.invoke(self.phases(after_tuning=(2, 3)))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "inconclusive")

    def test_inconclusive_when_a_phase_declares_the_wrong_split(self) -> None:
        phases = self.phases()
        phases["before_holdout"]["run_config"]["split"] = "tuning"
        result = self.invoke(phases)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("split", json.loads(result.stdout)["reason"])

    def test_writes_a_human_gate_record_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "benchmark.md"
            result = self.invoke(self.phases(), "--benchmark", str(report))
            self.assertEqual(result.returncode, 0, result.stderr)
            contents = report.read_text(encoding="utf-8")
            self.assertIn("pass", contents)
            self.assertIn("Before Tuning HEAD", contents)
            self.assertIn("Before Tuning dirty fingerprint", contents)
            self.assertIn("a" * 40, contents)
            self.assertIn("b" * 64, contents)
            self.assertIn("After Holdout models", contents)


if __name__ == "__main__":
    unittest.main()
