"""The git command-line reader both dev hooks share, tested directly.

guard-git and orchestrate each have their own tests for what they refuse; these pin the
reading underneath, because a mistake here opens the same hole in both at once.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "plugins" / "dev" / "hooks" / "git_argv.py"


def _load():
    spec = importlib.util.spec_from_file_location("git_argv", MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


git_argv = _load()


class SplitTests(unittest.TestCase):
    def test_options_with_a_separate_value_consume_it(self) -> None:
        options, subcommand, rest = git_argv.split(["-C", "push", "-c", "a=b", "status", "-s"])

        self.assertEqual(options, [("-C", "push"), ("-c", "a=b")])
        self.assertEqual((subcommand, rest), ("status", ["-s"]))

    def test_flags_and_equals_forms_take_no_next_word(self) -> None:
        options, subcommand, rest = git_argv.split(["--no-pager", "-P", "--git-dir=.git", "log", "-n", "5"])

        self.assertEqual(options, [("--no-pager", None), ("-P", None), ("--git-dir=.git", None)])
        self.assertEqual((subcommand, rest), ("log", ["-n", "5"]))

    def test_no_subcommand_is_empty(self) -> None:
        self.assertEqual(git_argv.split(["--version"]), ([("--version", None)], "", []))
        self.assertEqual(git_argv.split(["-C"]), ([("-C", None)], "", []))
        self.assertEqual(git_argv.split([]), ([], "", []))


class DirectoryTests(unittest.TestCase):
    def test_repeated_dash_c_options_join_as_git_joins_them(self) -> None:
        self.assertEqual(git_argv.directory([("-C", "a"), ("-C", "b")]), "a/b")
        self.assertEqual(git_argv.directory([("-C", "a"), ("-C", "/abs")]), "/abs")
        self.assertEqual(git_argv.directory([("-c", "x=y")]), "")


class HooksPathTests(unittest.TestCase):
    def test_every_spelling_of_a_hooks_path_override_is_seen(self) -> None:
        for args in (
            ["-c", "core.hooksPath=/dev/null", "commit"],
            ["-c", "CORE.HOOKSPATH=x", "push"],
            ["-c", "core.hooksPath", "merge"],
            ["--config-env=core.hooksPath=HOOKS", "rebase"],
            ["--config-env", "core.hooksPath=HOOKS", "commit"],
        ):
            with self.subTest(args=args):
                self.assertTrue(git_argv.overrides_hooks(git_argv.split(args)[0]))

    def test_other_settings_and_later_words_are_not_overrides(self) -> None:
        for args in (
            ["-c", "core.editor=true", "commit"],
            ["-c", "core.hooksPathology=x", "commit"],
            ["commit", "-c", "core.hooksPath=x"],
        ):
            with self.subTest(args=args):
                self.assertFalse(git_argv.overrides_hooks(git_argv.split(args)[0]))


class ForceTests(unittest.TestCase):
    def test_force_flags_and_plus_refspecs_force_a_push(self) -> None:
        for rest in (["--force"], ["-f"], ["-fu", "origin", "x"], ["origin", "+main"]):
            with self.subTest(rest=rest):
                self.assertTrue(git_argv.is_forced_push(rest))

    def test_the_sanctioned_forms_do_not(self) -> None:
        for rest in (["--force-with-lease"], ["--force-if-includes"], ["-u", "origin", "a:b"]):
            with self.subTest(rest=rest):
                self.assertFalse(git_argv.is_forced_push(rest))


if __name__ == "__main__":
    unittest.main()
