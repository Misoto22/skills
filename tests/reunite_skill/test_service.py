"""The opt-in launchd service: its agent definition, its lock, and that a run after a run is a no-op."""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import environments_sync
import ldb_store
import lifecycle
import local_storage
import service
import service_run
import sidebar
import sidebar_auto
import stars

from tests.reunite_skill.test_ldb_files import FIXTURE
from tests.reunite_skill.test_merge import MERGE, merge
from tests.reunite_skill.test_sidebar_sync import ORGS, SCOPES, A, B, C, snapshot

SCRIPTS = MERGE.parent


class FakeLaunchctl:
    """Records every launchctl call and answers ``print`` as loaded or not."""

    def __init__(self, loaded: bool = False, fail: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self.loaded = loaded
        self.fail = fail

    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        verb = argv[1]
        if verb == self.fail:
            return subprocess.CompletedProcess(argv, 5, "", "Bootstrap failed: 5: Input/output error")
        if verb == "print":
            return subprocess.CompletedProcess(argv, 0 if self.loaded else 113, "", "")
        if verb == "bootstrap":
            self.loaded = True
        if verb == "bootout":
            code = 0 if self.loaded else 3
            self.loaded = False
            return subprocess.CompletedProcess(argv, code, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")


class ServiceCase(unittest.TestCase):
    """A temporary home holding a session index, a presets file and a Local Storage copy."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "sessions"
        self.app = self.home / "app"
        self.store = self.home / "Local Storage" / "leveldb"
        shutil.copytree(FIXTURE, self.store)
        self.app.mkdir()
        self.projects = self.home / ".claude" / "projects" / "proj"
        self.projects.mkdir(parents=True)
        for account in (A, B, C):
            (self.root / account / ORGS[account]).mkdir(parents=True)
        self.session(A, "s1")
        presets = {
            "byAccount": {A: {"presets": [{"id": "p1", "name": "P1", "createdAt": 1, "lastUsedAt": 1}]}}
        }
        (self.app / environments_sync.PRESETS_NAME).write_text(json.dumps(presets, indent="\t"))
        env = {
            "HOME": str(self.home),
            merge.SESSIONS_ROOT_ENV: str(self.root),
            local_storage.STORE_ENV: str(self.store),
            environments_sync.APP_DIR_ENV: str(self.app),
        }
        self.running = patch.object(local_storage, "app_running", return_value=False)
        for patcher in (patch.dict(os.environ, env), self.running):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop(merge.CONFIG_DIR_ENV, None)

    def session(self, account: str, sid: str, **fields) -> Path:
        (self.projects / f"{sid}.jsonl").write_text("{}")
        path = self.root / account / ORGS[account] / f"local_{sid}.json"
        entry = {
            "sessionId": f"local_{sid}",
            "cliSessionId": sid,
            "title": sid,
            "lastActivityAt": 1,
            **fields,
        }
        path.write_text(json.dumps(entry))
        return path

    def run_merge(self, *flags: str, code: int = 0) -> str:
        out = io.StringIO()
        with patch.object(sys, "argv", ["merge.py", *flags]), contextlib.redirect_stdout(out):
            self.assertEqual(merge.main(), code, out.getvalue())
        return out.getvalue()

    def service_run(self) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(service_run.run(self.root), 0, out.getvalue())
        return out.getvalue()

    def state(self) -> dict:
        return json.loads((self.root / service.STATE_NAME).read_text())

    def everything(self) -> dict[str, bytes]:
        """Every file the service could write, except its own state and lock files."""
        own = {service.STATE_NAME, service.LOCK_NAME}
        files = {f"root/{k}": v for k, v in snapshot(self.root).items() if k not in own}
        files.update({f"app/{k}": v for k, v in snapshot(self.app).items()})
        files.update({f"store/{k}": v for k, v in snapshot(self.store).items()})
        return files


class PlistTests(unittest.TestCase):
    def test_the_agent_runs_the_installed_copy_on_changes_and_every_five_minutes(self) -> None:
        script = Path("/stable/scripts/merge.py")
        watched = [Path("/index"), Path("/app/ccd-session-presets.json")]
        log = Path("/logs/reunite-service.log")

        with patch.dict(os.environ, {merge.SESSIONS_ROOT_ENV: "/index"}, clear=True):
            agent = plistlib.loads(service.render_plist(script, watched, Path("/py/bin"), log))

        self.assertEqual(agent["Label"], service.LABEL)
        self.assertEqual(agent["ProgramArguments"], ["/usr/bin/env", "python3", str(script), "--service-run"])
        self.assertEqual(agent["WatchPaths"], ["/index", "/app/ccd-session-presets.json"])
        self.assertEqual(agent["StartInterval"], 300)
        self.assertEqual(agent["ThrottleInterval"], 30)
        self.assertIs(agent["RunAtLoad"], True)
        self.assertEqual(agent["StandardOutPath"], str(log))
        self.assertEqual(agent["StandardErrorPath"], str(log))
        # launchd's own PATH finds the system Python first, which is too old for these scripts.
        self.assertTrue(agent["EnvironmentVariables"]["PATH"].startswith("/py/bin:"))
        self.assertEqual(agent["EnvironmentVariables"][merge.SESSIONS_ROOT_ENV], "/index")


class InstallTests(ServiceCase):
    def install(self, runner: FakeLaunchctl, code: int = 0) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(
                service.install(self.root, SCRIPTS, runner, Path("/py/bin")), code, out.getvalue()
            )
        return out.getvalue()

    def test_install_refuses_before_a_manual_apply(self) -> None:
        runner = FakeLaunchctl()

        report = self.install(runner, code=1)

        self.assertIn("merge.py --apply", report)
        self.assertEqual(runner.calls, [])
        self.assertFalse(service.plist_path().exists())

    def test_install_copies_the_scripts_writes_the_agent_and_bootstraps_it(self) -> None:
        self.run_merge("--apply")
        runner = FakeLaunchctl()

        self.install(runner)

        copied = service.install_dir() / "scripts"
        self.assertTrue((copied / "merge.py").is_file())
        self.assertFalse(list(copied.rglob("__pycache__")))
        agent = plistlib.loads(service.plist_path().read_bytes())
        self.assertEqual(agent["ProgramArguments"][2], str(copied / "merge.py"))
        self.assertEqual(
            agent["WatchPaths"], [str(self.root), str(self.app / environments_sync.PRESETS_NAME)]
        )
        uid = os.getuid()
        self.assertIn(["launchctl", "bootstrap", f"gui/{uid}", str(service.plist_path())], runner.calls)
        self.assertTrue(service.installed())

    def test_installing_again_upgrades_the_copy_and_reloads_the_agent(self) -> None:
        self.run_merge("--apply")
        runner = FakeLaunchctl()
        self.install(runner)
        stale = service.install_dir() / "scripts" / "merge.py"
        stale.write_text("# an older release\n")

        self.install(runner)

        self.assertEqual(stale.read_bytes(), (SCRIPTS / "merge.py").read_bytes())
        verbs = [call[1] for call in runner.calls if call[1] in ("bootout", "bootstrap")]
        self.assertEqual(verbs, ["bootstrap", "bootout", "bootstrap"])

    def test_a_failed_bootstrap_is_reported(self) -> None:
        self.run_merge("--apply")

        report = self.install(FakeLaunchctl(fail="bootstrap"), code=1)

        self.assertIn("Input/output error", report)

    def test_uninstall_boots_the_agent_out_and_removes_it(self) -> None:
        self.run_merge("--apply")
        runner = FakeLaunchctl()
        self.install(runner)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(service.uninstall(runner), 0)

        self.assertIn(["launchctl", "bootout", f"gui/{os.getuid()}/{service.LABEL}"], runner.calls)
        self.assertFalse(service.plist_path().exists())
        self.assertFalse(service.install_dir().exists())
        self.assertFalse(service.installed())

    def test_status_names_the_agent_and_the_last_run(self) -> None:
        self.run_merge("--apply")
        self.service_run()
        out = io.StringIO()

        with contextlib.redirect_stdout(out):
            service.status(self.root, FakeLaunchctl(loaded=True))

        self.assertIn("loaded", out.getvalue())
        self.assertIn("last run", out.getvalue())
        self.assertIn(self.state()["result"], out.getvalue())

    def test_undo_refuses_while_the_service_is_installed(self) -> None:
        self.run_merge("--apply")
        self.install(FakeLaunchctl())

        for flag in ("--undo", "--undo-sidebar"):
            with (
                self.subTest(flag=flag),
                patch.object(sys, "argv", ["merge.py", flag]),
                self.assertRaises(SystemExit) as raised,
            ):
                merge.main()
            self.assertIn("--uninstall-service", str(raised.exception.code))
        self.assertTrue((self.root / merge.MANIFEST_NAME).exists())


class ServiceRunTests(ServiceCase):
    def test_nothing_is_aligned_before_a_manual_apply(self) -> None:
        self.session(B, "s2")
        before = self.everything()

        line = self.service_run()

        self.assertIn("index: waiting for a first manual --apply", line)
        self.assertEqual(self.everything(), before)

    def test_a_run_aligns_index_and_environments_and_logs_one_line(self) -> None:
        self.run_merge("--apply")
        self.session(A, "s2", title="new")

        line = self.service_run()

        self.assertEqual(line.count("\n"), 1)
        self.assertIn("index: +2", line)
        for account in (B, C):
            self.assertTrue((self.root / account / ORGS[account] / "local_s2.json").exists())
        self.assertNotIn("new", line)
        self.assertEqual(self.state()["result"], line.split(" ", 1)[1].strip())

    def test_a_run_right_after_a_run_writes_nothing(self) -> None:
        self.run_merge("--apply")
        self.session(A, "s2")
        self.service_run()
        written = self.everything()

        line = self.service_run()

        self.assertIn("index: unchanged", line)
        self.assertIn("environments: unchanged", line)
        self.assertEqual(self.everything(), written)

    def test_a_deletion_the_baseline_proves_is_carried_and_nothing_else_is_removed(self) -> None:
        self.session(B, "s2")
        self.run_merge("--apply")
        (self.root / A / ORGS[A] / "local_s1.json").unlink()

        self.service_run()

        for account in (B, C):
            self.assertFalse((self.root / account / ORGS[account] / "local_s1.json").exists())
            self.assertTrue((self.root / account / ORGS[account] / "local_s2.json").exists())

    def test_a_deleted_conversation_is_never_resurrected_by_later_runs(self) -> None:
        self.session(B, "s2")
        self.run_merge("--apply")
        (self.root / A / ORGS[A] / "local_s1.json").unlink()
        self.service_run()

        self.service_run()
        self.service_run()

        for account in (A, B, C):
            self.assertFalse((self.root / account / ORGS[account] / "local_s1.json").exists())

    def test_a_run_while_another_holds_the_lock_exits_quietly_and_writes_nothing(self) -> None:
        self.run_merge("--apply")
        self.session(A, "s2")
        before = self.everything()

        with (self.root / service.LOCK_NAME).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            line = self.service_run()

        self.assertEqual(line, "")
        self.assertEqual(self.everything(), before)
        self.assertFalse((self.root / service.STATE_NAME).exists())

    def test_a_manual_apply_waits_for_a_running_service_pass(self) -> None:
        with (self.root / service.LOCK_NAME).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            with patch.object(sys, "argv", ["merge.py", "--apply"]), self.assertRaises(SystemExit) as raised:
                merge.main()
        self.assertIn("service", str(raised.exception.code))

    def test_service_writes_are_undoable(self) -> None:
        self.run_merge("--apply")
        self.session(A, "s2")
        self.service_run()

        self.run_merge("--undo")

        self.assertFalse((self.root / B / ORGS[B] / "local_s2.json").exists())
        self.assertFalse((self.root / B / ORGS[B] / "local_s1.json").exists())
        # A later install starts over: its first pass records rather than compares.
        self.assertFalse((self.root / service.STATE_NAME).exists())

    def test_an_error_is_logged_and_recorded_without_contents(self) -> None:
        self.run_merge("--apply")
        (self.root / lifecycle.BASELINE_NAME).write_text("[]")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(service_run.run(self.root), 1)

        self.assertIn("error:", out.getvalue())
        self.assertIn("error:", self.state()["result"])


class SourceSelectionTests(unittest.TestCase):
    def test_no_previous_run_chooses_nothing(self) -> None:
        self.assertIsNone(sidebar_auto.choose_source(None, {A: "1", B: "2"}, A))

    def test_the_single_changed_scope_is_the_source(self) -> None:
        self.assertEqual(sidebar_auto.choose_source({A: "1", B: "2"}, {A: "1", B: "3"}, A), B)

    def test_several_changed_prefer_the_signed_in_account(self) -> None:
        self.assertEqual(sidebar_auto.choose_source({A: "1", B: "2"}, {A: "4", B: "3"}, B), B)

    def test_several_changed_without_the_signed_in_account_among_them_choose_nothing(self) -> None:
        self.assertIsNone(sidebar_auto.choose_source({A: "1", B: "2", C: "5"}, {A: "4", B: "3", C: "5"}, C))

    def test_nothing_changed_chooses_nothing(self) -> None:
        self.assertIsNone(sidebar_auto.choose_source({A: "1"}, {A: "1"}, A))

    def test_a_newly_seen_account_is_never_the_source(self) -> None:
        self.assertIsNone(sidebar_auto.choose_source({A: "1"}, {A: "1", B: "9"}, B))


class ServiceSidebarTests(ServiceCase):
    def setUp(self) -> None:
        super().setUp()
        for account in (B, C):
            self.session(account, "s1")
        self.run_merge("--apply")

    def change_layout(self, scope: str) -> None:
        document = sidebar.decode(ldb_store.read(self.store, sidebar.STORE_KEY))
        sections = document["state"][sidebar.SECTIONS_BY_SCOPE][scope]["sections"]
        sections[0]["collapsed"] = not sections[0].get("collapsed")
        ldb_store.put(self.store, sidebar.STORE_KEY, sidebar.encode(document))

    def layout(self, scope: str) -> dict | None:
        document = sidebar.decode(ldb_store.read(self.store, sidebar.STORE_KEY))
        return document["state"][sidebar.SECTIONS_BY_SCOPE].get(scope)

    def test_the_first_run_only_records_each_scope(self) -> None:
        before = snapshot(self.store)

        line = self.service_run()

        self.assertIn("sidebar: recorded", line)
        self.assertEqual(snapshot(self.store), before)
        self.assertEqual(set(self.state()["sidebar"]), {A, B, C})

    def test_the_scope_that_changed_since_the_last_run_is_copied_to_the_others(self) -> None:
        self.service_run()
        self.change_layout(SCOPES[A])
        ldb_store.put_many(
            self.store, [(stars.key(A), b'\x01{"value":["preset::p1"],"tabId":"","timestamp":1}')]
        )

        line = self.service_run()

        self.assertIn(f"sidebar: from {A[:8]}", line)
        source = self.layout(SCOPES[A])
        for account in (B, C):
            self.assertEqual(
                self.layout(SCOPES[account])["sections"][0]["collapsed"], source["sections"][0]["collapsed"]
            )
            self.assertEqual(
                ldb_store.read(self.store, stars.key(account)), ldb_store.read(self.store, stars.key(A))
            )
        self.assertTrue(list((self.root / merge.BACKUP_DIR).glob("local-storage-*")))

        written = self.everything()
        self.assertIn("sidebar: unchanged", self.service_run())
        self.assertEqual(self.everything(), written)

    def test_while_the_app_runs_the_sidebar_waits_and_keeps_the_change_pending(self) -> None:
        self.service_run()
        self.change_layout(SCOPES[B])
        before = snapshot(self.store)

        with patch.object(local_storage, "app_running", return_value=True):
            line = self.service_run()

        self.assertIn("sidebar: waiting for Claude to quit", line)
        self.assertEqual(snapshot(self.store), before)
        self.assertIn(f"sidebar: from {B[:8]}", self.service_run())


if __name__ == "__main__":
    unittest.main()
