"""The watcher installs only its own launch agent and persists observable results."""

import importlib.util
import json
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/dev/skills/handoff/scripts"


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        spec = importlib.util.spec_from_file_location("handoff_service", SCRIPTS / "service.py")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        self.runner = self.home / ".claude/handoff/handoff.py"
        self.runner.parent.mkdir(parents=True)
        self.runner.write_text("# test runner\n")
        self.commands = []
        patcher = patch.object(self.module.shutil, "which", return_value="/usr/bin/codex")
        patcher.start()
        self.addCleanup(patcher.stop)

    def launchctl(self, args, **kwargs):
        self.commands.append(args)
        return SimpleNamespace(returncode=0, stdout="state = running\npid = 12\n", stderr="")

    def test_install_uses_argument_array_and_only_its_own_service(self):
        result = self.module.install_watcher(self.home, self.runner, run=self.launchctl, system="Darwin")
        plist = plistlib.loads(Path(result["plist"]).read_bytes())
        self.assertEqual(plist["ProgramArguments"][1:3], [str(self.runner), "watch"])
        self.assertTrue(plist["RunAtLoad"])
        self.assertTrue(all(self.module.LABEL in " ".join(command) for command in self.commands))
        self.assertEqual(result["status"], "installed")

    def test_install_refuses_to_replace_an_unrelated_launch_agent(self):
        plist = self.home / "Library/LaunchAgents" / (self.module.LABEL + ".plist")
        plist.parent.mkdir(parents=True)
        original = plistlib.dumps({"Label": self.module.LABEL, "ProgramArguments": ["unrelated"]})
        plist.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "watcher_label_conflict"):
            self.module.install_watcher(self.home, self.runner, run=self.launchctl, system="Darwin")
        self.assertEqual(plist.read_bytes(), original)
        self.assertEqual(self.commands, [])

    def test_unsupported_platform_is_reported_without_writing_a_plist(self):
        result = self.module.install_watcher(self.home, self.runner, run=self.launchctl, system="Linux")
        self.assertEqual(result["status"], "not-installed")
        self.assertEqual(self.commands, [])

    def test_failed_bootstrap_is_not_reported_as_installed(self):
        def failed(args, **kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="private detail")

        with self.assertRaisesRegex(ValueError, "watcher_bootstrap_failed"):
            self.module.install_watcher(self.home, self.runner, run=failed, system="Darwin")

    def test_sync_request_records_no_transcript_or_hook_payload(self):
        path = self.module.request_sync(self.home)
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(), "")

    def test_uninstall_only_removes_its_own_service(self):
        self.assertEqual(
            self.module.uninstall_watcher(self.home, self.runner, run=self.launchctl)["status"],
            "not-installed",
        )
        installed = self.module.install_watcher(self.home, self.runner, run=self.launchctl, system="Darwin")
        self.assertEqual(
            self.module.uninstall_watcher(self.home, self.runner, run=self.launchctl)["status"], "uninstalled"
        )
        self.assertFalse(Path(installed["plist"]).exists())
        self.assertTrue(self.runner.exists())

    def test_watcher_records_failures_and_restarts_native_connection(self):
        native = SimpleNamespace(NativeCodex=Mock())
        report = {"errors": [], "unfinished": [], "results": [{"status": "imported"}]}
        with (
            patch.dict(sys.modules, {"native": native}),
            patch.object(
                self.module, "run_once", side_effect=[RuntimeError("private"), report, KeyboardInterrupt]
            ),
            patch.object(self.module.time, "sleep"),
            patch.object(self.module.time, "monotonic", side_effect=range(0, 1000, 10)),
            patch.object(self.module.os, "umask"),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.module.watch(self.home, interval=5)
        state = json.loads((self.runner.parent / "watcher-state.json").read_text())
        self.assertEqual(state["status"], "complete")
        self.assertEqual(state["outcomes"], {"imported": 1})
        self.assertGreaterEqual(native.NativeCodex.call_count, 2)
        native.NativeCodex.return_value.close.assert_called()
        self.assertNotIn("private", (self.runner.parent / "last-sync-report.json").read_text())

    def test_run_once_closes_only_a_client_it_created(self):
        native = SimpleNamespace(NativeCodex=Mock())
        sync = SimpleNamespace(Paths=Mock(), synchronize=Mock(return_value={"errors": []}))
        with patch.dict(sys.modules, {"native": native, "sync": sync}):
            self.module.run_once(self.home, apply=True)
            native.NativeCodex.return_value.close.assert_called_once()
            supplied = Mock()
            self.module.run_once(self.home, apply=False, native=supplied)
            supplied.close.assert_not_called()
            sync.synchronize.side_effect = ValueError("invalid store")
            with self.assertRaises(ValueError):
                self.module.run_once(self.home, apply=True)
            self.assertEqual(native.NativeCodex.return_value.close.call_count, 2)

    def test_summary_exposes_incomplete_work_instead_of_a_false_pass(self):
        report = {
            "counts": {"claude": 2, "codex": 3},
            "results": [{"status": "copied"}],
            "errors": [{"error": "native_request_timeout"}],
            "unfinished": [{"status": "error"}],
        }
        result = self.module.record_result(self.home, report)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["error_count"], 1)
        saved = json.loads((self.runner.parent / "watcher-state.json").read_text())
        self.assertEqual(saved, result)


if __name__ == "__main__":
    unittest.main()
