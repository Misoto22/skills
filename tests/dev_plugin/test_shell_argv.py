"""The shell reader both dev hooks share, tested directly.

guard-git and orchestrate test what they refuse; these pin the step underneath, because a
wrapper or assignment it fails to strip hides the real command from both hooks at once.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "plugins" / "dev" / "hooks" / "shell_argv.py"


def _load():
    spec = importlib.util.spec_from_file_location("shell_argv", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


shell_argv = _load()


class SegmentTests(unittest.TestCase):
    def test_every_command_separator_starts_a_new_segment(self) -> None:
        self.assertEqual(
            shell_argv.SEGMENT.split("a && b || c; d | e\nf"),
            ["a", "b", "c", "d", "e", "f"],
        )


class UnwrapTests(unittest.TestCase):
    def test_wrappers_that_run_their_command_are_removed(self) -> None:
        for words, expected in (
            (["command", "git", "push"], ["git", "push"]),
            (["exec", "tee", "x"], ["tee", "x"]),
            (["env", "A=1", "B=2", "git", "commit"], ["git", "commit"]),
            (["/usr/bin/env", "A=1", "command", "git"], ["git"]),
            (["A=1", "git", "commit"], ["git", "commit"]),
        ):
            with self.subTest(words=words):
                self.assertEqual(shell_argv.unwrap(words), expected)

    def test_words_that_only_describe_a_command_stay(self) -> None:
        for words in (["echo", "env", "A=1"], ["git", "commit", "-m", "A=1"], ["sudo", "git", "push"], []):
            with self.subTest(words=words):
                self.assertEqual(shell_argv.unwrap(words), words)

    def test_the_input_list_is_not_mutated(self) -> None:
        words = ["env", "A=1", "git"]
        shell_argv.unwrap(words)
        self.assertEqual(words, ["env", "A=1", "git"])


class EnvironmentTests(unittest.TestCase):
    def test_leading_assignments_bare_or_after_env_are_returned(self) -> None:
        environment, words = shell_argv.unwrap_env(
            ["A=1", "env", "GIT_CONFIG_PARAMETERS='core.hooksPath'='x'", "B=", "git", "commit", "C=3"]
        )

        self.assertEqual(environment, {"A": "1", "GIT_CONFIG_PARAMETERS": "'core.hooksPath'='x'", "B": ""})
        self.assertEqual(words, ["git", "commit", "C=3"])

    def test_no_assignments_is_an_empty_environment(self) -> None:
        self.assertEqual(shell_argv.unwrap_env(["git", "status"]), ({}, ["git", "status"]))


if __name__ == "__main__":
    unittest.main()
