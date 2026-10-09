"""Ship's in-place baseline, run from SKILL.md's own commands against a real repository.

The stash stack is shared by every worktree of a repository, so the entry ship pushes is
not necessarily on top when it comes back for it. These run the documented commands with
another session's push landing in between, which is the case a bare `pop` gets wrong.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "dev" / "skills" / "ship" / "SKILL.md"
RUN_LINE = "# run the test command"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def stash_block() -> str:
    """The indented bash block in step 2a that sets the change aside, dedented."""
    text = SKILL.read_text(encoding="utf-8")
    start = text.index("```bash\n", text.index("set the change aside in place")) + len("```bash\n")
    end = text.index("```", start)
    return "\n".join(line.strip() for line in text[start:end].splitlines())


class StashBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.env = {**os.environ, **GIT_ENV}
        self.git("init", "-q")
        (self.repo / "app.py").write_text("base\n")
        self.git("add", "app.py")
        self.git("commit", "-qm", "init")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, check=True
        ).stdout

    def run_block(self, during: str) -> subprocess.CompletedProcess[str]:
        script = stash_block().replace(RUN_LINE, during)
        return subprocess.run(
            ["bash", "-c", script], cwd=self.repo, env=self.env, capture_output=True, text=True, check=False
        )

    def test_the_block_names_a_tag_a_sha_and_no_pop(self) -> None:
        block = stash_block()

        self.assertIn(RUN_LINE, block)
        self.assertIn('git stash push -u -m "$tag"', block)
        self.assertIn('git stash apply "$sha"', block)
        self.assertNotIn("stash pop", block)

    def test_its_own_entry_comes_back_when_another_session_pushed_on_top(self) -> None:
        (self.repo / "app.py").write_text("mine\n")
        (self.repo / "new.py").write_text("untracked\n")
        other_session = (
            'test "$(cat app.py)" = base && test ! -e new.py && '
            "echo theirs > theirs.txt && git stash push -q -u -m other-session"
        )

        result = self.run_block(other_session)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / "app.py").read_text(), "mine\n")
        self.assertEqual((self.repo / "new.py").read_text(), "untracked\n")
        self.assertFalse((self.repo / "theirs.txt").exists(), "the other session's entry was applied")
        remaining = self.git("stash", "list", "--format=%gs").splitlines()
        self.assertEqual(len(remaining), 1)
        self.assertIn("other-session", remaining[0], "its own entry is dropped, the other one kept")

    def test_a_clean_tree_stashes_nothing_and_yields_an_empty_sha(self) -> None:
        lines = stash_block().split(RUN_LINE)[0] + 'printf "sha=[%s]" "$sha"'

        result = subprocess.run(
            ["bash", "-c", lines], cwd=self.repo, env=self.env, capture_output=True, text=True, check=False
        )

        self.assertIn("sha=[]", result.stdout)
        self.assertEqual(self.git("stash", "list"), "")


if __name__ == "__main__":
    unittest.main()
