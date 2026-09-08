"""Safety boundaries for Reunite's recoverable local-index merge."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MERGE = ROOT / "plugins" / "dev" / "skills" / "reunite" / "scripts" / "merge.py"


def load_merge_module():
    """Load the real standalone script without changing its import contract."""
    spec = importlib.util.spec_from_file_location("reunite_merge", MERGE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


merge = load_merge_module()


class UndoBoundaryTests(unittest.TestCase):
    """The undo manifest must only control index files below the chosen root."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name) / "session-index"
        self.root.mkdir()
        self.addCleanup(self._temporary.cleanup)

    def manifest(self, payload: object) -> None:
        (self.root / merge.MANIFEST_NAME).write_text(json.dumps(payload), encoding="utf-8")

    def index_file(self, name: str = "local_session.json") -> Path:
        path = self.root / "account" / "organisation" / name
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"title": "current", "keep": "unchanged"}), encoding="utf-8")
        return path

    def test_undo_never_deletes_a_manifest_path_outside_the_session_root(self) -> None:
        """A tampered manifest must not turn a recovery action into arbitrary deletion."""
        outside = Path(self._temporary.name) / "outside.txt"
        outside.write_text("must survive", encoding="utf-8")
        self.manifest({"copied": [str(outside)], "titles": []})

        self.assertEqual(merge.undo(self.root), 0)

        self.assertTrue(outside.exists())
        self.assertEqual(outside.read_text(encoding="utf-8"), "must survive")

    def test_undo_never_rewrites_a_manifest_title_path_outside_the_session_root(self) -> None:
        """A tampered title record must not overwrite an unrelated JSON file."""
        outside = Path(self._temporary.name) / "outside.json"
        before = {"title": "outside", "keep": "unchanged"}
        outside.write_text(json.dumps(before), encoding="utf-8")
        self.manifest(
            {
                "copied": [],
                "titles": [{"path": str(outside), "title": "attacker", "titleSource": "manual"}],
            }
        )

        self.assertEqual(merge.undo(self.root), 0)

        self.assertEqual(json.loads(outside.read_text(encoding="utf-8")), before)

    def test_undo_restores_a_relative_manifest_path_inside_the_index_tree(self) -> None:
        """New root-relative records must remain undoable without relying on the caller's cwd."""
        index = self.index_file()
        self.manifest(
            {
                "copied": [],
                "titles": [
                    {
                        "path": "account/organisation/local_session.json",
                        "title": "previous",
                        "titleSource": "manual",
                        "previousTitles": ["older"],
                    }
                ],
            }
        )

        self.assertEqual(merge.undo(self.root), 0)

        self.assertEqual(
            json.loads(index.read_text(encoding="utf-8")),
            {"title": "previous", "keep": "unchanged", "titleSource": "manual", "previousTitles": ["older"]},
        )

    def test_write_manifest_records_new_paths_relative_to_the_session_root(self) -> None:
        """Persisting an absolute path would let a later manifest escape its owning root."""
        index = self.index_file()

        manifest = merge.write_manifest(self.root, [str(index)], [])

        self.assertEqual(
            json.loads(manifest.read_text(encoding="utf-8"))["copied"],
            ["account/organisation/local_session.json"],
        )
