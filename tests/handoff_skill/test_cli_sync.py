"""Exercise command dispatch against temporary configuration and real runner copies."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/dev/skills/handoff/scripts"


class CommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("handoff_cli_test", SCRIPTS / "handoff.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.RUNNER_HOME = self.home / ".claude/handoff"
        self.module.CLAUDE_HOOKS = self.home / ".claude/settings.json"
        self.module.CODEX_HOOKS = self.home / ".codex/hooks.json"
        self.module.STATE_PATH = self.home / "legacy.json"
        self.service = SimpleNamespace(
            uninstall_watcher=Mock(return_value={"status": "uninstalled"}),
            install_watcher=Mock(return_value={"status": "installed"}),
            run_once=Mock(return_value={"errors": [], "unfinished": []}),
            record_result=Mock(),
            watch=Mock(),
            request_sync=Mock(),
        )
        for config in (self.module.CLAUDE_HOOKS, self.module.CODEX_HOOKS):
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"unrelated": "preserve"}))

    def command(self, *arguments):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["handoff.py", *arguments]),
            patch.dict(sys.modules, {"service": self.service}),
            patch.object(Path, "home", return_value=self.home),
            contextlib.redirect_stdout(output),
        ):
            status = self.module.main()
        return status, output.getvalue()

    def test_install_and_uninstall_preserve_unrelated_settings_and_runner(self):
        self.assertEqual(self.command("install")[0], 0)
        self.service.install_watcher.assert_called_once()
        for name in self.module.RUNNER_MODULES:
            self.assertEqual((self.module.RUNNER_HOME / name).read_bytes(), (SCRIPTS / name).read_bytes())
        self.assertEqual(len(list((self.module.RUNNER_HOME / "backups").iterdir())), 2)
        self.assertEqual(self.command("uninstall")[0], 0)
        self.assertTrue((self.module.RUNNER_HOME / "sync.py").exists())
        for config in (self.module.CLAUDE_HOOKS, self.module.CODEX_HOOKS):
            self.assertEqual(json.loads(config.read_text())["unrelated"], "preserve")

    def test_sync_exit_status_distinguishes_plan_and_partial_apply(self):
        self.service.run_once.return_value = {"errors": [], "unfinished": [{"status": "planned"}]}
        self.assertEqual(self.command("sync")[0], 0)
        self.service.record_result.assert_not_called()
        self.assertEqual(self.command("sync", "--apply", "--home", str(self.home))[0], 1)
        self.service.record_result.assert_called_once()

    def test_status_reports_corrupt_watcher_state_as_unverified(self):
        self.module.RUNNER_HOME.mkdir(parents=True)
        (self.module.RUNNER_HOME / "watcher-state.json").write_text("{broken")
        status, output = self.command("status")
        self.assertEqual(status, 0)
        self.assertIn("synchronization is not verified", output)

    def test_status_shows_saved_completion_and_installed_hooks(self):
        self.command("install", "--no-watch")
        self.service.install_watcher.assert_not_called()
        (self.module.RUNNER_HOME / "watcher-state.json").write_text('{"status":"complete"}')
        _, output = self.command("status")
        self.assertIn('"complete"', output)
        self.assertIn("installed (claude)", output)
        self.assertIn("installed (codex)", output)

    def test_hook_wakeup_failure_does_not_fail_parent(self):
        self.service.request_sync.side_effect = OSError("unavailable")
        self.assertEqual(self.command("mirror", "--from", "codex"), (0, ""))

    def test_watch_passes_explicit_configuration(self):
        self.assertEqual(self.command("watch", "--interval", "15", "--home", str(self.home))[0], 0)
        self.service.watch.assert_called_once_with(self.home, interval=15, codex_binary="codex")
