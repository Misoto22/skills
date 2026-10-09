"""The file-size ratchet: a recorded file may shrink, never grow; no other file may cross the limit."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-file-size.py"
LIMIT = 5


def write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"line_{index} = {index}\n" for index in range(count)), encoding="utf-8")


class FileSizeRatchetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        write_lines(self.root / "scripts" / "small.py", 3)
        write_lines(self.root / "plugins" / "demo" / "shared" / "big.py", 8)
        self.write_baseline({"plugins/demo/shared/big.py": 8})

    def tearDown(self) -> None:
        self._directory.cleanup()

    def write_baseline(self, files: dict[str, int]) -> None:
        baseline = self.root / ".rulesync" / "file-size-baseline.json"
        baseline.parent.mkdir(exist_ok=True)
        baseline.write_text(json.dumps({"limit": LIMIT, "files": files}), encoding="utf-8")

    def baseline(self) -> dict[str, int]:
        return json.loads((self.root / ".rulesync" / "file-size-baseline.json").read_text(encoding="utf-8"))[
            "files"
        ]

    def run_checker(self, *arguments: str, root: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments, "--root", str(root or self.root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_a_tree_matching_its_baseline_passes(self) -> None:
        result = self.run_checker("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_new_file_over_the_limit_fails(self) -> None:
        write_lines(self.root / "scripts" / "new.py", LIMIT + 1)

        result = self.run_checker("--check")

        self.assertEqual(result.returncode, 1)
        self.assertIn("scripts/new.py: 6 lines, over the 5-line limit", result.stderr)

    def test_a_recorded_file_that_grows_fails_and_update_refuses_to_record_it(self) -> None:
        write_lines(self.root / "plugins" / "demo" / "shared" / "big.py", 9)

        checked = self.run_checker("--check")
        updated = self.run_checker("--update")

        self.assertEqual(checked.returncode, 1)
        self.assertIn("grew from 8 to 9 lines", checked.stderr)
        self.assertEqual(updated.returncode, 1)
        self.assertEqual(self.baseline(), {"plugins/demo/shared/big.py": 8})

    def test_a_shrunk_file_fails_check_until_update_lowers_its_count(self) -> None:
        write_lines(self.root / "plugins" / "demo" / "shared" / "big.py", 7)

        stale = self.run_checker("--check")
        updated = self.run_checker("--update")
        after = self.run_checker("--check")

        self.assertEqual(stale.returncode, 1)
        self.assertIn("recorded at 8 lines but is 7 now", stale.stderr)
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(self.baseline(), {"plugins/demo/shared/big.py": 7})
        self.assertEqual(after.returncode, 0, after.stderr)

    def test_update_drops_a_file_that_fell_under_the_limit_or_was_removed(self) -> None:
        write_lines(self.root / "scripts" / "gone.py", LIMIT + 2)
        self.write_baseline({"plugins/demo/shared/big.py": 8, "scripts/gone.py": 7})
        write_lines(self.root / "plugins" / "demo" / "shared" / "big.py", LIMIT)
        (self.root / "scripts" / "gone.py").unlink()

        updated = self.run_checker("--update")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(self.baseline(), {})

    def test_vendored_skill_copies_and_non_source_files_are_not_held(self) -> None:
        write_lines(self.root / "plugins" / "demo" / "skills" / "one" / "shared" / "big.py", LIMIT + 10)
        write_lines(self.root / "plugins" / "demo" / "skills" / "one" / "SKILL.md", LIMIT + 10)
        write_lines(self.root / "plugins" / "demo" / "shared" / "rules" / "table.json", LIMIT + 10)

        result = self.run_checker("--check")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_repository_holds_its_own_baseline_and_ci_runs_it(self) -> None:
        result = self.run_checker("--check", root=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/check-file-size.py --check", workflow)


if __name__ == "__main__":
    unittest.main()
