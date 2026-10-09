"""The cleanup skill's residue pass, run from SKILL.md's own commands against a real repository.

The pass is prose an agent executes, so the commands in the section are the code path.
Two ways it went wrong before: the search descended into other worktrees and read their
live `__pycache__` as residue here, and the tracked-file test asked about the candidate
itself, which git never tracks, so every `__pycache__` looked like residue.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "dev" / "skills" / "cleanup" / "SKILL.md"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def residue_blocks() -> list[str]:
    """The bash blocks of the Residue section, in order: the search, then the test."""
    text = SKILL.read_text(encoding="utf-8")
    section = text.split("## 4. Residue", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```bash\n(.*?)```", section, re.DOTALL)


class ResiduePassTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(os.path.realpath(temporary.name))
        self.repo = base / "repo"
        self.outside = base / "sibling-worktree"
        self.env = {**os.environ, **GIT_ENV}
        self.repo.mkdir()
        self.git("init", "-q")
        files = {"src/x.py": "x", "a/pkg/y.py": "y", ".gitignore": "__pycache__/\n.claude/\n"}
        for path, text in files.items():
            (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / path).write_text(text)
        self.git("add", ".")
        self.git("commit", "-qm", "init")
        self.git("worktree", "add", "-q", str(self.outside), "-b", "outside")
        self.inside = self.repo / ".claude" / "worktrees" / "inner"
        self.git("worktree", "add", "-q", str(self.inside), "-b", "inner")
        # A move leaves the ignored bytecode behind; the live package keeps its own.
        self.git("mv", "a/pkg", "b")
        for directory in ("src", "a/pkg", ".claude/worktrees/inner/src"):
            cache = self.repo / directory / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "m.pyc").write_text("")
        (self.outside / "src" / "__pycache__").mkdir()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, check=True
        ).stdout

    def shell(self, shell: str, script: str) -> str:
        return subprocess.run(
            [shell, "-c", script], cwd=self.repo, env=self.env, capture_output=True, text=True, check=True
        ).stdout

    def candidates(self, shell: str = "bash") -> set[str]:
        return set(self.shell(shell, residue_blocks()[0]).split())

    def is_residue(self, directory: str) -> bool:
        parent_live, untracked = (
            self.shell("bash", line.split("#", 1)[0].replace("<dir>", f"'{directory}'"))
            for line in residue_blocks()[1].strip().splitlines()
        )
        return not parent_live.strip() and not untracked.strip()

    def test_the_search_never_descends_into_another_worktree(self) -> None:
        found = self.candidates()

        self.assertIn(str(self.repo / "a" / "pkg" / "__pycache__"), found)
        self.assertIn(str(self.repo / "src" / "__pycache__"), found)
        for path in found:
            with self.subTest(path=path):
                self.assertFalse(path.startswith(str(self.inside)), path)
                self.assertFalse(path.startswith(str(self.repo / ".claude" / "worktrees")), path)
                self.assertFalse(path.startswith(str(self.outside)), path)

    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
    def test_the_search_runs_the_same_under_zsh(self) -> None:
        self.assertEqual(self.candidates("zsh"), self.candidates("bash"))

    def test_a_pycache_beside_tracked_sources_is_live(self) -> None:
        self.assertFalse(self.is_residue("src/__pycache__"))

    def test_a_pycache_whose_sources_moved_away_is_residue(self) -> None:
        self.assertTrue(self.is_residue("a/pkg/__pycache__"))

    def test_untracked_work_inside_a_candidate_is_never_residue(self) -> None:
        (self.repo / "a" / "pkg" / "__pycache__" / "notes.txt").write_text("keep me")
        (self.repo / ".gitignore").write_text(".claude/\n*.pyc\n")

        self.assertFalse(self.is_residue("a/pkg/__pycache__"))


if __name__ == "__main__":
    unittest.main()
