"""The git guard, run the way Claude Code runs a PreToolUse hook and in-process for its parsing.

The three refusals restate rules `ship` and `shared/git.md` carry as prose. What a test
has to hold is the other side: every sanctioned form still runs, because a guard that
refuses `--force-with-lease` teaches the model to stop using it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "plugins" / "dev" / "hooks" / "guard-git.py"


def _load():
    spec = importlib.util.spec_from_file_location("guard_git", GUARD)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


guard = _load()

REFUSED = [
    "git push --force",
    "git push -f origin feature/x",
    "git push origin feature/x -f",
    "git push -fu origin feature/x",
    "git commit --no-verify -m 'skip hooks'",
    "git commit -n -m 'skip hooks'",
    "git commit -am 'msg' --no-verify",
    "git push --no-verify",
    "git rebase --no-verify main",
    "gh pr merge 12 --admin --squash",
    "git add -A && git commit --no-verify -m x",
    "git fetch; git push --force origin feature/x",
]

ALLOWED = [
    "git push --force-with-lease origin feature/x",
    "git push --force-with-lease=feature/x:abc123",
    "git push --force-if-includes --force-with-lease",
    "git push -u origin feature/x",
    "git commit -m 'note: --no-verify is refused here'",
    "git commit -am 'msg'",
    "gh pr merge 12 --rebase --delete-branch",
    "gh pr view 12 --json state",
    "grep -rn -- '--force' plugins/",
    "echo 'git push --force' > notes.txt",
    "git log --oneline -n 5",
    "git push origin --delete feature/x",
]


class GuardParsingTests(unittest.TestCase):
    def test_every_forbidden_form_is_refused(self) -> None:
        for command in REFUSED:
            with self.subTest(command=command):
                self.assertIsNotNone(guard.offence(command))

    def test_every_sanctioned_form_runs(self) -> None:
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(guard.offence(command))

    def test_each_refusal_names_the_sanctioned_alternative(self) -> None:
        self.assertIn("--force-with-lease", guard.offence("git push --force"))
        self.assertIn("fix what it names", guard.offence("git commit --no-verify"))
        self.assertIn("human", guard.offence("gh pr merge --admin"))


class GuardProcessTests(unittest.TestCase):
    def run_guard(self, payload: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GUARD)],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_a_forbidden_command_exits_two_with_the_reason(self) -> None:
        event = {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}}
        result = self.run_guard(json.dumps(event))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Refused", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_a_sanctioned_command_stays_silent(self) -> None:
        event = {"tool_name": "Bash", "tool_input": {"command": "git push --force-with-lease"}}
        result = self.run_guard(json.dumps(event))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_anything_unparseable_lets_the_command_run(self) -> None:
        for payload in ("", "not json", "[]", '{"tool_input": "x"}', '{"tool_input": {"command": 7}}'):
            with self.subTest(payload=payload):
                result = self.run_guard(payload)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
