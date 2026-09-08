"""Installed-path smoke test for Codex's first-prompt title hook."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts" / "verify-codex-retitle.py"
DEV_PLUGIN = ROOT / "plugins" / "dev"


class InstalledCodexHookTests(unittest.TestCase):
    def test_verifier_accepts_a_codex_task_title_hook(self) -> None:
        """A client-specific title tool must survive the plugin artifact boundary."""
        result = subprocess.run(
            [sys.executable, str(VERIFY), str(DEV_PLUGIN)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex retitle hook verified", result.stdout)

    def test_verifier_discovers_the_hook_below_a_marketplace_cache(self) -> None:
        """CI must derive the installed plugin root instead of naming the dev plugin."""
        result = subprocess.run(
            [sys.executable, str(VERIFY), str(ROOT / "plugins")],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex retitle hook verified", result.stdout)

    def test_verifier_discovers_the_versioned_codex_cache_layout(self) -> None:
        """Codex installs plugins below marketplace/name/version, not directly below a marketplace."""
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "plugins" / "cache" / "misoto22"
            manifest = json.loads((DEV_PLUGIN / ".codex-plugin" / "plugin.json").read_text())
            copytree(DEV_PLUGIN, cache / "dev" / manifest["version"])
            result = subprocess.run(
                [sys.executable, str(VERIFY), str(cache)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex retitle hook verified", result.stdout)
