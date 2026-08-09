from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync-shared.py"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_shared", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyncSharedTests(unittest.TestCase):
    def test_runtime_cache_files_never_create_vendoring_drift(self) -> None:
        module = load_sync_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "bazi"
            cache = package / "__pycache__"
            cache.mkdir(parents=True)
            (package / "engine.py").write_text("pass\n", encoding="utf-8")
            (cache / "engine.cpython-314.pyc").write_bytes(b"runtime cache")
            (root / ".DS_Store").write_bytes(b"finder metadata")

            self.assertEqual(module._relative_files(root), {Path("bazi/engine.py")})


if __name__ == "__main__":
    unittest.main()
