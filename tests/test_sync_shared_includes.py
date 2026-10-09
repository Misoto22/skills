"""sync-shared.py honours a skill's shared.json: vendor what it names, prune the rest.

Each test runs the real script against a throwaway repository, so a prune can
never reach this checkout.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync-shared.py"
SOURCE_FILES = {
    "notes.md": "notes\n",
    "extra.md": "extra\n",
    "pkg/__init__.py": "",
    "pkg/mod.py": "VALUE = 1\n",
}


class SyncSharedIncludeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        (self.root / "scripts").mkdir()
        shutil.copyfile(SCRIPT, self.root / "scripts" / "sync-shared.py")
        plugin = self.root / "plugins" / "demo"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
        for relative, content in SOURCE_FILES.items():
            path = plugin / "shared" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        for skill in ("listed", "unlisted"):
            (plugin / "skills" / skill).mkdir(parents=True)
            (plugin / "skills" / skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        self.listed = plugin / "skills" / "listed"
        self.unlisted = plugin / "skills" / "unlisted"

    def tearDown(self) -> None:
        self._directory.cleanup()

    def run_sync(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/sync-shared.py", *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def declare(self, manifest: object) -> None:
        (self.listed / "shared.json").write_text(json.dumps(manifest), encoding="utf-8")

    def vendored(self, skill: Path) -> set[str]:
        shared = skill / "shared"
        return {path.relative_to(shared).as_posix() for path in shared.rglob("*") if path.is_file()}

    def test_a_skill_without_a_list_receives_everything(self) -> None:
        self.declare({"include": ["notes.md"]})

        self.assertEqual(self.run_sync().returncode, 0)

        self.assertEqual(self.vendored(self.unlisted), set(SOURCE_FILES))

    def test_a_list_vendors_exactly_the_files_and_directories_it_names(self) -> None:
        self.declare({"$comment": "why", "include": ["notes.md", "pkg"]})

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.vendored(self.listed), {"notes.md", "pkg/__init__.py", "pkg/mod.py"})
        self.assertEqual(self.run_sync("--check").returncode, 0)

    def test_a_written_run_prunes_files_the_list_drops_and_the_directories_they_leave(self) -> None:
        self.assertEqual(self.run_sync().returncode, 0)
        self.declare({"include": ["extra.md"]})

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.vendored(self.listed), {"extra.md"})
        self.assertFalse((self.listed / "shared" / "pkg").exists())

    def test_check_reports_an_orphan_and_leaves_it_in_place(self) -> None:
        self.assertEqual(self.run_sync().returncode, 0)
        self.declare({"include": ["notes.md"]})

        result = self.run_sync("--check")

        self.assertEqual(result.returncode, 1)
        self.assertIn("listed/shared/extra.md (not in the skill's shared.json)", result.stderr)
        self.assertTrue((self.listed / "shared" / "extra.md").is_file())

    def test_check_reports_drift_in_an_included_file(self) -> None:
        self.declare({"include": ["notes.md"]})
        self.assertEqual(self.run_sync().returncode, 0)
        (self.listed / "shared" / "notes.md").write_text("edited\n", encoding="utf-8")

        result = self.run_sync("--check")

        self.assertEqual(result.returncode, 1)
        self.assertIn("stale vendored copy: plugins/demo/skills/listed/shared/notes.md\n", result.stderr)

    def test_an_empty_list_leaves_the_skill_without_shared(self) -> None:
        self.assertEqual(self.run_sync().returncode, 0)
        self.declare({"include": []})

        self.assertEqual(self.run_sync().returncode, 0)

        self.assertFalse((self.listed / "shared").exists())
        self.assertEqual(self.run_sync("--check").returncode, 0)

    def test_a_list_naming_a_missing_path_fails_before_writing(self) -> None:
        self.declare({"include": ["notes.md", "gone.py"]})

        result = self.run_sync()

        self.assertEqual(result.returncode, 2)
        self.assertIn("includes 'gone.py', which is not in the plugin's shared/", result.stderr)
        self.assertFalse((self.listed / "shared").exists())

    def test_a_malformed_list_is_refused(self) -> None:
        cases = {
            "not an object": ["notes.md"],
            "no include": {"files": ["notes.md"]},
            "unknown key": {"include": ["notes.md"], "exclude": []},
            "not a string": {"include": [3]},
            "climbs out": {"include": ["../notes.md"]},
            "absolute": {"include": ["/notes.md"]},
            "trailing slash": {"include": ["pkg/"]},
            "twice": {"include": ["notes.md", "notes.md"]},
        }
        for label, manifest in cases.items():
            with self.subTest(label):
                self.declare(manifest)
                result = self.run_sync("--check")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("listed/shared.json", result.stderr)

    def test_invalid_json_is_refused(self) -> None:
        (self.listed / "shared.json").write_text("{", encoding="utf-8")

        result = self.run_sync("--check")

        self.assertEqual(result.returncode, 2)
        self.assertIn("listed/shared.json is not valid JSON", result.stderr)


if __name__ == "__main__":
    unittest.main()
