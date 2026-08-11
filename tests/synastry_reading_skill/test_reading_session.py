from __future__ import annotations

import argparse
import io
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
HELPER = SKILL / "scripts" / "reading_session.py"
FIXTURE = Path(__file__).parent / "fixtures" / "neutral.json"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

import reading_session  # type: ignore[import-not-found]
from synastry_schema import attach_integrity  # type: ignore[import-not-found]
from validate_synastry import load_ledger  # type: ignore[import-not-found]

UNIVERSAL_HEADINGS = (
    "Basis, provenance, and limitations",
    "Repeated interaction patterns",
    "Reciprocity and asymmetry",
    "Communication and coordination",
    "Tension, boundaries, and repair",
    "Growth and shared direction",
    "Requested or context-specific domains",
    "Overall synthesis",
    "Evidence index",
)


def source_with(
    *,
    label: str = "private-display-name",
    warning_size: int = 0,
    data_path: str | None = None,
) -> dict[str, object]:
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source["subjects"][0]["display_name"] = label
    if warning_size:
        source["provenance"]["warnings"] = ["x" * warning_size]
    if data_path is not None:
        source["provenance"]["data_path"] = data_path
    return attach_integrity(source)


def valid_report(source: dict[str, object]) -> str:
    evidence = load_ledger(source).evidence[0].citation
    lines = ["# Synastry reading"]
    for heading in UNIVERSAL_HEADINGS:
        lines.extend((f"## {heading}", evidence))
    return "\n\n".join(lines) + "\n"


def ledger_bytes(status: dict[str, object]) -> bytes:
    pages = Path(str(status["pages_path"]))
    return b"".join((pages / f"{index:06d}.part").read_bytes() for index in range(int(status["page_count"])))


class ReadingSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.session_root = self.directory / "sessions"
        self.environment = os.environ | {
            "SYNASTRY_READING_SESSION_ROOT": str(self.session_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_helper(
        self, arguments: list[str], *, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HELPER), *arguments],
            cwd=SKILL,
            env=self.environment,
            input=input_text,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )

    def start_pasted(
        self, source: dict[str, object], *, ttl_seconds: int = 60
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = self.run_helper(
            ["start", "-", "--ttl-seconds", str(ttl_seconds)],
            input_text=json.dumps(source),
        )
        status = json.loads(completed.stdout) if completed.stdout else {}
        return completed, status

    def start_blocked_process(
        self,
        source: dict[str, object],
        *,
        marker: Path,
        ttl_seconds: int,
    ) -> subprocess.Popen[str]:
        wrapper = """
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_write = reading_session._write_private

def blocking_write(path, payload):
    original_write(path, payload)
    if path.name == "source.json":
        Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
        while True:
            time.sleep(0.05)

reading_session._write_private = blocking_write
raise SystemExit(
    reading_session.main(["start", "-", "--ttl-seconds", os.environ["SYNASTRY_READING_TEST_TTL"]])
)
"""
        environment = self.environment | {
            "SYNASTRY_READING_TEST_MARKER": str(marker),
            "SYNASTRY_READING_TEST_TTL": str(ttl_seconds),
        }
        process = subprocess.Popen(
            [sys.executable, "-c", wrapper],
            cwd=SKILL,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdin is not None
        process.stdin.write(json.dumps(source))
        process.stdin.close()
        process.stdin = None
        deadline = time.monotonic() + 5
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        if not marker.exists():
            _, stderr = process.communicate(timeout=2)
            self.fail(f"blocked start did not reach the sensitive write: {stderr}")
        return process

    def assert_session_root_empty(self) -> None:
        children = list(self.session_root.iterdir()) if self.session_root.exists() else []
        self.assertEqual(children, [])

    def test_large_ledger_is_private_complete_and_page_readable(self) -> None:
        secret = "private-display-name"
        secret_path = "/Users/private-user/ephemeris-data"
        completed, status = self.start_pasted(
            source_with(label=secret, warning_size=220_000, data_path=secret_path)
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertLess(len(completed.stdout.encode("utf-8")), 1024)
        self.assertNotIn(secret, completed.stdout + completed.stderr)
        self.assertIn("pages_path", status)
        pages_path = Path(str(status["pages_path"]))
        self.assertGreater(int(status["ledger_bytes"]), 200_000)
        self.assertLessEqual(int(status["page_bytes"]), 65_536)
        self.assertGreater(int(status["page_bytes"]), 0)
        self.assertNotIn("ledger_path", status)
        self.assertEqual(stat.S_IMODE(pages_path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(pages_path.stat().st_mode), 0o700)
        page_files = sorted(pages_path.iterdir())
        self.assertEqual(len(page_files), int(status["page_count"]))
        for page in page_files:
            self.assertEqual(stat.S_IMODE(page.stat().st_mode), 0o600)
            self.assertLessEqual(page.stat().st_size, int(status["page_bytes"]))
            page.read_text(encoding="utf-8")
        for artifact in pages_path.parent.iterdir():
            if artifact.is_file():
                self.assertEqual(stat.S_IMODE(artifact.stat().st_mode), 0o600)

        reconstructed = ledger_bytes(status)

        self.assertEqual(len(reconstructed), int(status["ledger_bytes"]))
        ledger = json.loads(reconstructed)
        self.assertEqual(ledger["chart_id"], "abc123def456")
        self.assertEqual(ledger["subjects"], [{"id": "subject-a"}, {"id": "subject-b"}])
        self.assertNotIn("display_name", reconstructed.decode("utf-8"))
        self.assertNotIn("source_path", reconstructed.decode("utf-8"))
        self.assertNotIn(secret_path, reconstructed.decode("utf-8"))
        self.assertNotIn("data_path", ledger["provenance"])
        self.assertEqual(ledger["provenance"]["actual_backend"], "swiss")

    def test_unbounded_session_lifetime_is_rejected_without_artifacts(self) -> None:
        rejected, _ = self.start_pasted(source_with(), ttl_seconds=3_601)

        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(rejected.stdout, "")
        self.assertEqual(rejected.stderr, "error: session operation failed\n")
        self.assertFalse(self.session_root.exists())

    def test_attached_and_pasted_status_never_echoes_source_or_display_name(self) -> None:
        secret = "private-display-name"
        source = source_with(label=secret)
        attached = self.directory / "private-source-path.json"
        attached.write_text(json.dumps(source), encoding="utf-8")

        attached_result = self.run_helper(["start", str(attached)])
        pasted_result, _ = self.start_pasted(source)

        self.assertEqual((attached_result.returncode, pasted_result.returncode), (0, 0))
        combined = (
            attached_result.stdout + attached_result.stderr + pasted_result.stdout + pasted_result.stderr
        )
        self.assertNotIn(secret, combined)
        self.assertNotIn(str(attached), combined)
        for payload in (json.loads(attached_result.stdout), json.loads(pasted_result.stdout)):
            self.assertRegex(str(payload["token"]), r"\A[0-9a-f]{32}\Z")
            self.assertEqual(Path(str(payload["pages_path"])).name, "ledger-pages")

    def test_watchdog_expires_an_interrupted_session(self) -> None:
        completed, status = self.start_pasted(source_with(), ttl_seconds=1)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        pages_path = Path(str(status["pages_path"]))
        deadline = time.monotonic() + 5

        while pages_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)

        self.assertFalse(pages_path.exists())
        self.assertFalse(pages_path.parent.exists())

    def test_short_lifetime_survives_construction_across_a_second(self) -> None:
        # A requested lifetime is a floor, not a budget the helper may spend
        # before the session exists. Truncating the creation stamp used to hand
        # a one-second session anywhere from zero to one second of real life, so
        # any construction crossing a whole-second tick tripped the "expired
        # during construction" guard and rejected a perfectly valid start.
        observed = float(int(time.time())) + 0.4
        elapsed = {"seconds": 0.0}

        def crossing_spawn(token: str, expires_at: int) -> None:
            # Watchdog arming sits between the creation stamp and the guard.
            elapsed["seconds"] = 0.9

        stdout = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, self.environment, clear=False))
            stack.enter_context(
                patch.object(reading_session.sys, "stdin", io.StringIO(json.dumps(source_with())))
            )
            stack.enter_context(patch.object(reading_session.sys, "stdout", stdout))
            stack.enter_context(
                patch.object(reading_session.time, "time", lambda: observed + elapsed["seconds"])
            )
            stack.enter_context(patch.object(reading_session, "_spawn_watchdog", side_effect=crossing_spawn))

            status = reading_session.main(["start", "-", "--ttl-seconds", "1"])

        self.assertEqual(status, 0)
        self.assertGreaterEqual(int(json.loads(stdout.getvalue())["expires_at"]), int(observed) + 1)

    def test_base_exception_at_each_start_stage_leaves_no_sensitive_artifacts(self) -> None:
        class InjectedInterruption(BaseException):
            pass

        stages = (
            "allocated",
            "watchdog",
            "source",
            "ledger",
            "pages",
            "metadata",
            "publish",
            "status",
        )
        original_write = reading_session._write_private
        original_entry_exists = reading_session._entry_exists

        for stage in stages:
            with self.subTest(stage=stage):
                session_root = self.directory / f"sessions-{stage}"
                environment = self.environment | {"SYNASTRY_READING_SESSION_ROOT": str(session_root)}

                def staged_write(path: Path, payload: bytes, selected_stage: str = stage) -> None:
                    if selected_stage == "source" and path.name == "source.json":
                        raise InjectedInterruption(selected_stage)
                    if selected_stage == "metadata" and path.name == "session.json":
                        raise InjectedInterruption(selected_stage)
                    original_write(path, payload)

                entry_checks = 0

                def staged_entry_exists(path: Path, selected_stage: str = stage) -> bool:
                    nonlocal entry_checks
                    entry_checks += 1
                    if selected_stage == "allocated" and entry_checks == 1:
                        raise InjectedInterruption(selected_stage)
                    return original_entry_exists(path)

                with ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, environment, clear=False))
                    stack.enter_context(
                        patch.object(reading_session.sys, "stdin", io.StringIO(json.dumps(source_with())))
                    )
                    stack.enter_context(patch.object(reading_session.sys, "stdout", io.StringIO()))
                    stack.enter_context(
                        patch.object(
                            reading_session,
                            "_spawn_watchdog",
                            side_effect=(InjectedInterruption(stage) if stage == "watchdog" else None),
                        )
                    )
                    stack.enter_context(
                        patch.object(reading_session, "_write_private", side_effect=staged_write)
                    )
                    stack.enter_context(
                        patch.object(
                            reading_session,
                            "_entry_exists",
                            side_effect=staged_entry_exists,
                        )
                    )
                    if stage == "ledger":
                        stack.enter_context(
                            patch.object(
                                reading_session,
                                "_ledger_bytes",
                                side_effect=InjectedInterruption(stage),
                            )
                        )
                    if stage == "pages":
                        stack.enter_context(
                            patch.object(
                                reading_session,
                                "_write_ledger_pages",
                                side_effect=InjectedInterruption(stage),
                            )
                        )
                    if stage == "publish":
                        stack.enter_context(
                            patch.object(
                                reading_session.os,
                                "rename",
                                side_effect=InjectedInterruption(stage),
                            )
                        )
                    if stage == "status":
                        stack.enter_context(
                            patch.object(
                                reading_session,
                                "_emit",
                                side_effect=InjectedInterruption(stage),
                            )
                        )

                    with self.assertRaises(InjectedInterruption):
                        reading_session._start(argparse.Namespace(source="-", ttl_seconds=60))

                children = list(session_root.iterdir()) if session_root.exists() else []
                self.assertEqual(children, [], stage)

    def test_concurrent_sweep_ignores_a_live_unpublished_start(self) -> None:
        original_write = reading_session._write_private
        observed_parent_names: list[str] = []
        sweep_errors: list[BaseException] = []

        def sweep() -> None:
            try:
                reading_session._sweep_expired(self.session_root)
            except BaseException as error:
                sweep_errors.append(error)

        def write_while_sweeping(path: Path, payload: bytes) -> None:
            original_write(path, payload)
            if path.name != "source.json":
                return
            observed_parent_names.append(path.parent.name)
            thread = threading.Thread(target=sweep)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(sweep_errors, [])
            self.assertTrue(path.is_file())

        stdout = io.StringIO()
        with (
            patch.dict(os.environ, self.environment, clear=False),
            patch.object(reading_session.sys, "stdin", io.StringIO(json.dumps(source_with()))),
            patch.object(reading_session.sys, "stdout", stdout),
            patch.object(reading_session, "_spawn_watchdog", return_value=None),
            patch.object(reading_session, "_write_private", side_effect=write_while_sweeping),
        ):
            code = reading_session._start(argparse.Namespace(source="-", ttl_seconds=60))

        self.assertEqual(code, 0)
        self.assertEqual(len(observed_parent_names), 1)
        self.assertNotRegex(observed_parent_names[0], r"\A[0-9a-f]{32}\Z")
        status = json.loads(stdout.getvalue())
        self.assertRegex(Path(str(status["pages_path"])).parent.name, r"\A[0-9a-f]{32}\Z")
        reading_session._remove_session(self.session_root, str(status["token"]))

    def test_sigint_and_sigterm_during_build_cleanup_immediately(self) -> None:
        for name, interruption in (("sigint", signal.SIGINT), ("sigterm", signal.SIGTERM)):
            with self.subTest(signal=name):
                marker = self.directory / f"{name}-ready"
                process = self.start_blocked_process(source_with(), marker=marker, ttl_seconds=60)
                try:
                    process.send_signal(interruption)
                    process.communicate(timeout=5)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate(timeout=2)
                self.assert_session_root_empty()

    def test_watchdog_bounds_sigkill_during_private_build(self) -> None:
        marker = self.directory / "sigkill-ready"
        process = self.start_blocked_process(source_with(), marker=marker, ttl_seconds=1)
        try:
            process.kill()
            process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=2)

        deadline = time.monotonic() + 5
        while self.session_root.exists() and time.monotonic() < deadline:
            time.sleep(0.05)

        self.assert_session_root_empty()

    def test_invalid_finalization_cleans_and_retry_uses_a_fresh_session(self) -> None:
        source = source_with()
        first, first_status = self.start_pasted(source)
        destination = self.directory / "synastry_reading_abc123def456.md"
        self.assertEqual(first.returncode, 0, first.stderr)

        failed = self.run_helper(
            ["finalize", str(first_status["token"]), "--out", str(destination)],
            input_text="# Invalid",
        )

        self.assertEqual(failed.returncode, 2)
        self.assertEqual(failed.stdout, "")
        self.assertEqual(failed.stderr, "error: session operation failed\n")
        self.assertFalse(Path(str(first_status["pages_path"])).parent.exists())
        self.assertFalse(destination.exists())

        second, second_status = self.start_pasted(source)
        self.assertEqual(second.returncode, 0, second.stderr)
        succeeded = self.run_helper(
            ["finalize", str(second_status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertNotEqual(first_status["token"], second_status["token"])
        self.assertEqual(succeeded.returncode, 0, succeeded.stderr)
        self.assertTrue(destination.is_file())
        self.assertFalse(Path(str(second_status["pages_path"])).parent.exists())
        self.assertEqual(list(self.session_root.glob("*")) if self.session_root.exists() else [], [])
        self.assertEqual(list(self.directory.iterdir()), [destination])

    def test_closed_stdout_cannot_turn_a_committed_finalization_into_failure(self) -> None:
        source = source_with()
        started, status = self.start_pasted(source)
        self.assertEqual(started.returncode, 0, started.stderr)
        destination = self.directory / "synastry_reading_abc123def456.md"
        read_descriptor, write_descriptor = os.pipe()
        os.close(read_descriptor)
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(HELPER),
                    "finalize",
                    str(status["token"]),
                    "--out",
                    str(destination),
                ],
                cwd=SKILL,
                env=self.environment,
                stdin=subprocess.PIPE,
                stdout=write_descriptor,
                stderr=subprocess.PIPE,
                text=True,
            )
        finally:
            os.close(write_descriptor)
        _, stderr = process.communicate(valid_report(source), timeout=10)

        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(stderr, "")
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assert_session_root_empty()

        retry = self.run_helper(
            ["finalize", str(status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertEqual(retry.returncode, 2)
        self.assertEqual(retry.stderr, "error: session operation failed\n")
        self.assertNotIn("validation", retry.stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assertEqual(list(self.directory.iterdir()), [destination])

    def test_watchdog_cleanup_race_is_resolved_before_terminal_commit(self) -> None:
        source = source_with()
        started, status = self.start_pasted(source)
        self.assertEqual(started.returncode, 0, started.stderr)
        destination = self.directory / "synastry_reading_abc123def456.md"
        original_rmtree = reading_session.shutil.rmtree

        def watchdog_wins(path: Path, *args: object, **kwargs: object) -> None:
            original_rmtree(path, *args, **kwargs)
            raise FileNotFoundError("watchdog removed the session concurrently")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.dict(os.environ, self.environment, clear=False),
            patch.object(reading_session.sys, "stdin", io.StringIO(valid_report(source))),
            patch.object(reading_session.sys, "stdout", stdout),
            patch.object(reading_session.sys, "stderr", stderr),
            patch.object(reading_session.shutil, "rmtree", side_effect=watchdog_wins),
        ):
            code = reading_session.main(["finalize", str(status["token"]), "--out", str(destination)])

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assert_session_root_empty()

        retry = self.run_helper(
            ["finalize", str(status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )
        self.assertEqual(retry.returncode, 2)
        self.assertNotIn("validation", retry.stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assertEqual(list(self.directory.iterdir()), [destination])

    def test_attached_source_is_revalidated_and_success_leaves_only_final_markdown(self) -> None:
        source = source_with()
        attached = self.directory / "source.json"
        attached.write_text(json.dumps(source), encoding="utf-8")
        started = self.run_helper(["start", str(attached)])
        self.assertEqual(started.returncode, 0, started.stderr)
        status = json.loads(started.stdout)
        destination = self.directory / "synastry_reading_abc123def456.md"

        finalized = self.run_helper(
            ["finalize", str(status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        self.assertEqual(finalized.stdout, "")
        self.assertTrue(destination.is_file())
        self.assertFalse(Path(str(status["pages_path"])).parent.exists())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)

    def test_changed_attached_source_fails_closed_and_cleans_session(self) -> None:
        source = source_with()
        attached = self.directory / "source.json"
        attached.write_text(json.dumps(source), encoding="utf-8")
        started = self.run_helper(["start", str(attached)])
        self.assertEqual(started.returncode, 0, started.stderr)
        status = json.loads(started.stdout)
        changed = source_with(label="changed-private-name")
        attached.write_text(json.dumps(changed), encoding="utf-8")
        destination = self.directory / "synastry_reading_abc123def456.md"

        finalized = self.run_helper(
            ["finalize", str(status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertEqual(finalized.returncode, 2)
        self.assertFalse(destination.exists())
        self.assertFalse(Path(str(status["pages_path"])).parent.exists())
        self.assertNotIn("changed-private-name", finalized.stdout + finalized.stderr)


if __name__ == "__main__":
    unittest.main()
