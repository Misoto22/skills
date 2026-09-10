"""Installed-path smoke test for Codex's orchestrator refusal.

Codex has no `agent_id` on a tool call and no transcript to read, so the model on the
event is the whole signal. That makes the installed artifact the thing to test: a hook
that lost its executable path, its manifest pointer, or its Codex wording refuses
nothing there and says so nowhere.

The tool name is the other half. Codex reports a file edit as `apply_patch` with the
patch body in `tool_input.command`, so a hook that knows only `Edit` and `Write` passes
every Codex edit through while every Claude Code test still passes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts" / "verify-codex-orchestrate.py"
DEV_PLUGIN = ROOT / "plugins" / "dev"


class InstalledCodexOrchestrateTests(unittest.TestCase):
    def _verify(self, install_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), str(install_root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_verifier_accepts_the_shipped_orchestrate_hook(self) -> None:
        result = self._verify(DEV_PLUGIN)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex orchestrate hook verified", result.stdout)

    def test_verifier_discovers_the_hook_below_a_marketplace_cache(self) -> None:
        """CI must derive the installed plugin root instead of naming the dev plugin."""
        result = self._verify(ROOT / "plugins")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex orchestrate hook verified", result.stdout)

    def test_verifier_discovers_the_versioned_codex_cache_layout(self) -> None:
        """Codex installs plugins below marketplace/name/version, not directly below a marketplace."""
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "plugins" / "cache" / "misoto22"
            manifest = json.loads((DEV_PLUGIN / ".codex-plugin" / "plugin.json").read_text())
            copytree(DEV_PLUGIN, cache / "dev" / manifest["version"])
            result = self._verify(cache)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex orchestrate hook verified", result.stdout)

    def test_verifier_reports_a_hook_that_cannot_see_a_codex_patch(self) -> None:
        """The regression this exists for: `apply_patch` handled as an unrecognised tool."""
        with tempfile.TemporaryDirectory() as temporary:
            install = Path(temporary) / "dev"
            copytree(DEV_PLUGIN, install)
            hook = install / "hooks" / "orchestrate.py"
            source = hook.read_text(encoding="utf-8")
            hook.write_text(source.replace('PATCH_TOOL = "apply_patch"', 'PATCH_TOOL = ""'), encoding="utf-8")
            result = self._verify(install)

        self.assertEqual(result.returncode, 1)
        self.assertIn("apply_patch", result.stderr)

    def test_verifier_reports_an_install_holding_no_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self._verify(Path(temporary))

        self.assertEqual(result.returncode, 1)
        self.assertIn("no installed orchestrate hook", result.stderr)


if __name__ == "__main__":
    unittest.main()
