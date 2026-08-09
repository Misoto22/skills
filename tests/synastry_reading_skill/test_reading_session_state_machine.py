from __future__ import annotations

import hashlib
import io
import json
import os
import signal
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
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

import reading_session  # type: ignore[import-not-found]
import validate_synastry  # type: ignore[import-not-found]

from tests.synastry_reading_skill.test_reading_session import source_with, valid_report


class ReadingSessionStateMachineTests(unittest.TestCase):
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

    def start_without_watchdog(
        self,
        source: dict[str, object],
        *,
        ttl_seconds: int = 60,
    ) -> dict[str, object]:
        stdout = io.StringIO()
        with (
            patch.dict(os.environ, self.environment, clear=False),
            patch.object(reading_session.sys, "stdin", io.StringIO(json.dumps(source))),
            patch.object(reading_session.sys, "stdout", stdout),
            patch.object(reading_session, "_spawn_watchdog", return_value=None),
        ):
            code = reading_session._start(
                type("Arguments", (), {"source": "-", "ttl_seconds": ttl_seconds})()
            )
        self.assertEqual(code, 0)
        return json.loads(stdout.getvalue())

    def finalize_in_process(
        self,
        token: str,
        destination: Path,
        report: str,
        *contexts: object,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, self.environment, clear=False))
            stack.enter_context(patch.object(reading_session.sys, "stdin", io.StringIO(report)))
            stack.enter_context(patch.object(reading_session.sys, "stdout", stdout))
            stack.enter_context(patch.object(reading_session.sys, "stderr", stderr))
            for context in contexts:
                stack.enter_context(context)  # type: ignore[arg-type]
            code = reading_session.main(["finalize", token, "--out", str(destination)])
        return code, stdout.getvalue(), stderr.getvalue()

    def start_finalizer_wrapper(
        self,
        wrapper: str,
        *,
        token: str,
        destination: Path,
        report: str,
        extra_environment: dict[str, str],
    ) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            [sys.executable, "-c", wrapper],
            cwd=SKILL,
            env=self.environment
            | {
                "SYNASTRY_READING_TEST_TOKEN": token,
                "SYNASTRY_READING_TEST_DESTINATION": str(destination),
            }
            | extra_environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdin is not None
        process.stdin.write(report)
        process.stdin.close()
        process.stdin = None
        return process

    def wait_for_path(self, path: Path, *, exists: bool = True) -> None:
        deadline = time.monotonic() + 5
        while path.exists() is not exists and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(path.exists(), exists, path)

    def rewrite_lease(self, state: Path, *, created_at: int, expires_at: int) -> None:
        for name in ("lease.json", "session.json"):
            path = state / name
            metadata = json.loads(path.read_text(encoding="utf-8"))
            metadata["created_at"] = created_at
            metadata["expires_at"] = expires_at
            path.write_text(json.dumps(metadata), encoding="utf-8")
            path.chmod(0o600)

    def expire_in_process(self, token: str, expires_at: int) -> int:
        arguments = type(
            "Arguments",
            (),
            {"token": token, "expires_at": expires_at},
        )()
        with (
            patch.dict(os.environ, self.environment, clear=False),
            patch.object(reading_session.time, "time", return_value=expires_at + 1),
        ):
            return reading_session._expire(arguments)

    def release_and_reap(
        self,
        process: subprocess.Popen[str],
        release: Path,
    ) -> tuple[str, str]:
        release.write_text("continue", encoding="utf-8")
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            self.fail(f"child did not exit after release: stdout={stdout!r} stderr={stderr!r}")

    def test_unlink_error_after_publication_cannot_turn_success_into_failure(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "synastry_reading_abc123def456.md"
        original_unlink = Path.unlink

        def fail_temporary_unlink(path: Path, *, missing_ok: bool = False) -> None:
            if path.name.startswith(".synastry-reading-"):
                raise OSError("injected post-publication unlink failure")
            original_unlink(path, missing_ok=missing_ok)

        code, stdout, stderr = self.finalize_in_process(
            str(status["token"]),
            destination,
            valid_report(source),
            patch.object(Path, "unlink", fail_temporary_unlink),
        )

        self.assertEqual(code, 0, stderr)
        self.assertEqual((stdout, stderr), ("", ""))
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))

    def test_overwrite_publish_to_absent_path_ignores_temporary_unlink_error(self) -> None:
        destination = self.directory / "overwrite-absent.md"
        payload = b"published bytes\n"
        original_unlink = Path.unlink

        def fail_temporary_unlink(path: Path, *, missing_ok: bool = False) -> None:
            if path.name.startswith(".overwrite-recovery-"):
                raise OSError("injected post-publication unlink failure")
            original_unlink(path, missing_ok=missing_ok)

        with patch.object(Path, "unlink", fail_temporary_unlink):
            result = validate_synastry._write_atomic_bytes(
                payload,
                destination,
                overwrite=True,
                temporary_prefix="overwrite-recovery",
            )

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes(), payload)

    def test_catchable_signal_at_each_post_publish_boundary_is_acknowledged(self) -> None:
        source = source_with()
        original_link = validate_synastry.os.link
        original_unlink = Path.unlink

        def link_then_interrupt(
            source_path: Path,
            destination_path: Path,
            *args: object,
            **kwargs: object,
        ) -> None:
            original_link(source_path, destination_path, *args, **kwargs)
            raise reading_session._SignalInterruption(signal.SIGTERM)

        def interrupt_before_unlink(path: Path, *, missing_ok: bool = False) -> None:
            if path.name.startswith(".synastry-reading-"):
                raise reading_session._SignalInterruption(signal.SIGTERM)
            original_unlink(path, missing_ok=missing_ok)

        def unlink_then_interrupt(path: Path, *, missing_ok: bool = False) -> None:
            original_unlink(path, missing_ok=missing_ok)
            if path.name.startswith(".synastry-reading-"):
                raise reading_session._SignalInterruption(signal.SIGTERM)

        cases = (
            ("link-return", patch.object(validate_synastry.os, "link", link_then_interrupt)),
            ("unlink-entry", patch.object(Path, "unlink", interrupt_before_unlink)),
            ("unlink-return", patch.object(Path, "unlink", unlink_then_interrupt)),
        )
        for index, (stage, interruption) in enumerate(cases):
            with self.subTest(stage=stage):
                status = self.start_without_watchdog(source)
                destination = self.directory / f"reading-{index}.md"

                code, stdout, stderr = self.finalize_in_process(
                    str(status["token"]),
                    destination,
                    valid_report(source),
                    interruption,
                )

                self.assertEqual(code, 0, stderr)
                self.assertEqual((stdout, stderr), ("", ""))
                self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))

    def test_new_session_accepts_identical_output_but_refuses_different_bytes(self) -> None:
        source = source_with()
        destination = self.directory / "synastry_reading_abc123def456.md"
        report = valid_report(source)

        first = self.start_without_watchdog(source)
        first_result = self.run_helper(
            ["finalize", str(first["token"]), "--out", str(destination)],
            input_text=report,
        )
        identical = self.start_without_watchdog(source)
        identical_result = self.run_helper(
            ["finalize", str(identical["token"]), "--out", str(destination)],
            input_text=report,
        )
        different = self.start_without_watchdog(source)
        different_result = self.run_helper(
            ["finalize", str(different["token"]), "--out", str(destination)],
            input_text=report + "\n",
        )

        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(identical_result.returncode, 0, identical_result.stderr)
        self.assertEqual(different_result.returncode, 2)
        self.assertEqual(destination.read_text(encoding="utf-8"), report)

    def test_restart_sweep_recovers_all_stale_owned_states_and_leaves_unrelated_directories(self) -> None:
        now = int(time.time())
        source = source_with()
        stale_states: list[Path] = []
        for state in ("staging", "finalizing", "cancelling", "committing"):
            status = self.start_without_watchdog(source)
            public = Path(str(status["pages_path"])).parent
            hidden = self.session_root / f".{state}-{status['token']}"
            public.rename(hidden)
            self.rewrite_lease(hidden, created_at=now - 2, expires_at=now - 1)
            os.utime(hidden, (now - reading_session.MAX_TTL_SECONDS - 10,) * 2)
            if state == "committing":
                destination = self.directory / "already-committed.md"
                payload = b"already committed\n"
                destination.write_bytes(payload)
                destination.chmod(0o600)
                commit_payload = hidden / "commit.md"
                commit_manifest = hidden / "commit.json"
                commit_payload.write_bytes(payload)
                commit_manifest.write_text(
                    json.dumps(
                        {
                            "destination": str(destination),
                            "expires_at": now - 1,
                            "format": "synastry-reading-session-v1",
                            "payload_bytes": len(payload),
                            "payload_sha256": hashlib.sha256(payload).hexdigest(),
                            "recover_after": now - 1,
                            "source_device": None,
                            "source_inode": None,
                            "token": str(status["token"]),
                        }
                    ),
                    encoding="utf-8",
                )
                commit_payload.chmod(0o600)
                commit_manifest.chmod(0o600)
            stale_states.append(hidden)

        incomplete_token = "f" * 32
        incomplete = self.session_root / f".staging-{incomplete_token}"
        incomplete.mkdir(mode=0o700)
        (incomplete / "partial-source.json").write_text("private", encoding="utf-8")
        os.utime(incomplete, (now - reading_session.MAX_TTL_SECONDS - 10,) * 2)
        stale_states.append(incomplete)
        unrelated = (
            self.session_root / ".staging-not-a-token",
            self.session_root / f".unknown-{'e' * 32}",
            self.session_root / "ordinary-directory",
        )
        for path in unrelated:
            path.mkdir()

        reading_session._sweep_expired(self.session_root)

        self.assertTrue(all(not path.exists() for path in stale_states))
        self.assertTrue(all(path.is_dir() for path in unrelated))
        self.assertEqual((self.directory / "already-committed.md").read_bytes(), b"already committed\n")

    def test_stale_committing_recovery_completes_absent_output_and_refuses_different_output(self) -> None:
        source = source_with()
        payload = b"validated final bytes\n"
        states: list[tuple[Path, Path, bytes, bool]] = []
        for name, existing in (("absent", None), ("different", b"different bytes\n")):
            status = self.start_without_watchdog(source)
            public = Path(str(status["pages_path"])).parent
            committing = self.session_root / f".committing-{status['token']}"
            public.rename(committing)
            destination = self.directory / f"{name}.md"
            if existing is not None:
                destination.write_bytes(existing)
                destination.chmod(0o600)
            commit_payload = committing / "commit.md"
            commit_manifest = committing / "commit.json"
            commit_payload.write_bytes(payload)
            commit_manifest.write_text(
                json.dumps(
                    {
                        "destination": str(destination),
                        "expires_at": int(status["expires_at"]),
                        "format": "synastry-reading-session-v1",
                        "payload_bytes": len(payload),
                        "payload_sha256": hashlib.sha256(payload).hexdigest(),
                        "recover_after": int(time.time()) - 1,
                        "source_device": None,
                        "source_inode": None,
                        "token": str(status["token"]),
                    }
                ),
                encoding="utf-8",
            )
            commit_payload.chmod(0o600)
            commit_manifest.chmod(0o600)
            states.append((committing, destination, existing or payload, existing is not None))

        reading_session._sweep_expired(self.session_root)

        for committing, destination, expected, should_retain in states:
            self.assertEqual(committing.exists(), should_retain)
            self.assertEqual(destination.read_bytes(), expected)

    def test_concurrent_stale_committing_recovery_is_idempotent(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        public = Path(str(status["pages_path"])).parent
        committing = self.session_root / f".committing-{status['token']}"
        public.rename(committing)
        destination = self.directory / "recovered-concurrently.md"
        payload = b"one committed payload\n"
        commit_payload = committing / "commit.md"
        commit_manifest = committing / "commit.json"
        commit_payload.write_bytes(payload)
        commit_manifest.write_text(
            json.dumps(
                {
                    "destination": str(destination),
                    "expires_at": int(status["expires_at"]),
                    "format": "synastry-reading-session-v1",
                    "payload_bytes": len(payload),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                    "recover_after": int(time.time()) - 1,
                    "source_device": None,
                    "source_inode": None,
                    "token": str(status["token"]),
                }
            ),
            encoding="utf-8",
        )
        commit_payload.chmod(0o600)
        commit_manifest.chmod(0o600)
        errors: list[BaseException] = []
        recovery_barrier = threading.Barrier(2)
        original_install = reading_session._install_prepared_markdown

        def synchronized_install(*args: object, **kwargs: object) -> Path:
            recovery_barrier.wait(timeout=5)
            return original_install(*args, **kwargs)  # type: ignore[arg-type]

        def sweep() -> None:
            try:
                reading_session._sweep_expired(self.session_root)
            except BaseException as error:
                errors.append(error)

        with patch.object(reading_session, "_install_prepared_markdown", synchronized_install):
            threads = [threading.Thread(target=sweep) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), payload)
        self.assertFalse(committing.exists())

    def test_recovery_retains_commit_until_installed_bytes_pass_exact_readback(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        public = Path(str(status["pages_path"])).parent
        committing = self.session_root / f".committing-{status['token']}"
        public.rename(committing)
        destination = self.directory / "readback-required.md"
        payload = b"durable payload\n"
        (committing / "commit.md").write_bytes(payload)
        (committing / "commit.json").write_text(
            json.dumps(
                {
                    "destination": str(destination),
                    "expires_at": int(status["expires_at"]),
                    "format": "synastry-reading-session-v1",
                    "payload_bytes": len(payload),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                    "recover_after": int(time.time()) - 1,
                    "source_device": None,
                    "source_inode": None,
                    "token": str(status["token"]),
                }
            ),
            encoding="utf-8",
        )
        (committing / "commit.md").chmod(0o600)
        (committing / "commit.json").chmod(0o600)

        with patch.object(
            reading_session,
            "_install_prepared_markdown",
            return_value=destination,
        ):
            recovered = reading_session._recover_committing(self.session_root, committing)

        self.assertFalse(recovered)
        self.assertTrue(committing.is_dir())
        self.assertFalse(destination.exists())

    def test_expire_revalidates_live_persisted_lease_instead_of_cli_deadline(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source, ttl_seconds=60)
        public = Path(str(status["pages_path"])).parent

        class WatchdogWouldWait(BaseException):
            pass

        arguments = type(
            "Arguments",
            (),
            {"token": str(status["token"]), "expires_at": int(time.time()) - 1},
        )()
        with (
            patch.dict(os.environ, self.environment, clear=False),
            patch.object(reading_session.time, "sleep", side_effect=WatchdogWouldWait),
            self.assertRaises(WatchdogWouldWait),
        ):
            reading_session._expire(arguments)

        self.assertTrue(public.is_dir())

    def test_corrupt_lease_deadlines_use_bounded_conservative_mtime_fallback(self) -> None:
        source = source_with()
        now = int(time.time())

        future = self.start_without_watchdog(source)
        future_state = Path(str(future["pages_path"])).parent
        self.rewrite_lease(
            future_state,
            created_at=now,
            expires_at=now + reading_session.MAX_TTL_SECONDS * 10,
        )
        old_mtime = now - reading_session.MAX_TTL_SECONDS - 60
        os.utime(future_state, (old_mtime, old_mtime))

        early = self.start_without_watchdog(source)
        early_state = Path(str(early["pages_path"])).parent
        self.rewrite_lease(
            early_state,
            created_at=now - 60,
            expires_at=now - 59,
        )
        os.utime(early_state, (now, now))

        reading_session._sweep_expired(self.session_root)

        self.assertFalse(future_state.exists())
        self.assertTrue(early_state.is_dir())

    def test_commit_deadline_is_token_bound_consistent_and_bounded(self) -> None:
        source = source_with()
        now = int(time.time())
        status = self.start_without_watchdog(source)
        public = Path(str(status["pages_path"])).parent
        committing = self.session_root / f".committing-{status['token']}"
        public.rename(committing)
        manifest = committing / "commit.json"
        base_manifest = {
            "destination": str(self.directory / "bounded.md"),
            "expires_at": int(status["expires_at"]),
            "format": "synastry-reading-session-v1",
            "payload_bytes": 1,
            "payload_sha256": hashlib.sha256(b"x").hexdigest(),
            "recover_after": now,
            "source_device": None,
            "source_inode": None,
            "token": str(status["token"]),
        }
        mutations = {
            "wrong-token": {"token": "0" * 32},
            "inconsistent-expiry": {"expires_at": int(status["expires_at"]) + 1},
            "unbounded-recovery": {"recover_after": now + reading_session.MAX_TTL_SECONDS * 10},
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                manifest.write_text(
                    json.dumps(base_manifest | mutation),
                    encoding="utf-8",
                )
                manifest.chmod(0o600)
                self.assertEqual(
                    reading_session._state_deadline(committing, "committing"),
                    reading_session._fallback_deadline(committing),
                )

    def test_invalid_commit_material_is_retained_for_explicit_failure(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        public = Path(str(status["pages_path"])).parent
        committing = self.session_root / f".committing-{status['token']}"
        public.rename(committing)
        (committing / "commit.json").write_text("{}", encoding="utf-8")
        (committing / "commit.json").chmod(0o600)

        recovered = reading_session._recover_committing(self.session_root, committing)

        self.assertFalse(recovered)
        self.assertTrue(committing.is_dir())

    def test_delayed_commit_preparation_remains_recoverable_after_crash(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        public = Path(str(status["pages_path"])).parent
        finalizing = self.session_root / f".finalizing-{status['token']}"
        committing = self.session_root / f".committing-{status['token']}"
        public.rename(finalizing)
        destination = self.directory / "delayed-crash-recovery.md"
        payload = b"validated delayed payload\n"
        ledger = reading_session.load_ledger(finalizing / "source.json")
        clock = {"value": int(time.time())}
        original_write = reading_session._write_private

        def delayed_write(path: Path, content: bytes) -> None:
            original_write(path, content)
            if path.name == "commit.md":
                clock["value"] += 10
            elif path.name == "commit.json":
                os.utime(path.parent, (clock["value"], clock["value"]))

        with (
            patch.object(reading_session, "_write_private", side_effect=delayed_write),
            patch.object(reading_session.time, "time", side_effect=lambda: clock["value"]),
        ):
            reading_session._prepare_commit(
                finalizing,
                str(status["token"]),
                int(status["expires_at"]),
                destination,
                payload,
                ledger,
            )
        finalizing.rename(committing)

        recovered = reading_session._recover_committing(self.session_root, committing)

        self.assertTrue(recovered)
        self.assertFalse(committing.exists())
        self.assertEqual(destination.read_bytes(), payload)

    def test_sweep_never_removes_live_unexpired_hidden_states(self) -> None:
        source = source_with()
        hidden_states: list[Path] = []
        for state in ("staging", "finalizing", "cancelling", "committing"):
            status = self.start_without_watchdog(source)
            public = Path(str(status["pages_path"])).parent
            hidden = self.session_root / f".{state}-{status['token']}"
            public.rename(hidden)
            if state == "committing":
                (hidden / "commit.json").write_text(
                    json.dumps({"recover_after": int(time.time()) + 60}),
                    encoding="utf-8",
                )
            hidden_states.append(hidden)

        reading_session._sweep_expired(self.session_root)

        self.assertTrue(all(path.is_dir() for path in hidden_states))

    def test_new_start_recovers_expired_finalizing_state_after_watchdog_loss(self) -> None:
        source = source_with()
        stale = self.start_without_watchdog(source)
        public = Path(str(stale["pages_path"])).parent
        finalizing = self.session_root / f".finalizing-{stale['token']}"
        public.rename(finalizing)
        now = int(time.time())
        self.rewrite_lease(finalizing, created_at=now - 2, expires_at=now - 1)

        replacement = self.start_without_watchdog(source)

        self.assertFalse(finalizing.exists())
        self.assertTrue(Path(str(replacement["pages_path"])).parent.is_dir())

    def test_signal_after_finalize_rename_is_caught_and_cleans_the_claim(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "interrupted.md"
        wrapper = """
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_rename = reading_session.os.rename

def rename_then_signal(source, destination):
    result = original_rename(source, destination)
    if Path(destination).name.startswith(".finalizing-"):
        os.kill(os.getpid(), signal.SIGTERM)
    return result

reading_session.os.rename = rename_then_signal
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={},
        )

        _, stderr = process.communicate(timeout=10)

        self.assertEqual(process.returncode, 128 + signal.SIGTERM, stderr)
        self.assertEqual(list(self.session_root.iterdir()) if self.session_root.exists() else [], [])
        self.assertFalse(destination.exists())

    def test_cancel_loses_truthfully_after_finalizer_claims_public_state(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "race-winner.md"
        marker = self.directory / "finalizer-claimed"
        release = self.directory / "release-finalizer"
        wrapper = """
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_prepare = reading_session.prepare_validated_markdown

def block_after_prepare(*args, **kwargs):
    result = original_prepare(*args, **kwargs)
    Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
    release = Path(os.environ["SYNASTRY_READING_TEST_RELEASE"])
    while not release.exists():
        time.sleep(0.02)
    return result

reading_session.prepare_validated_markdown = block_after_prepare
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={
                "SYNASTRY_READING_TEST_MARKER": str(marker),
                "SYNASTRY_READING_TEST_RELEASE": str(release),
            },
        )
        try:
            self.wait_for_path(marker)
            cancelled = self.run_helper(["cancel", str(status["token"])])
        finally:
            _, finalizer_stderr = self.release_and_reap(process, release)

        self.assertEqual(cancelled.returncode, 2)
        self.assertEqual(cancelled.stdout, "")
        self.assertEqual(process.returncode, 0, finalizer_stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))

    def test_cancel_claim_wins_and_prevents_finalizer_from_reporting_success(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "cancel-winner.md"
        marker = self.directory / "cancel-claimed"
        release = self.directory / "release-canceller"
        wrapper = """
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_remove = reading_session._remove_private_tree

def block_after_cancel_claim(path):
    if Path(path).name.startswith(".cancelling-"):
        Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
        release = Path(os.environ["SYNASTRY_READING_TEST_RELEASE"])
        while not release.exists():
            time.sleep(0.02)
    return original_remove(path)

reading_session._remove_private_tree = block_after_cancel_claim
raise SystemExit(reading_session.main(["cancel", os.environ["SYNASTRY_READING_TEST_TOKEN"]]))
"""
        process = subprocess.Popen(
            [sys.executable, "-c", wrapper],
            cwd=SKILL,
            env=self.environment
            | {
                "SYNASTRY_READING_TEST_TOKEN": str(status["token"]),
                "SYNASTRY_READING_TEST_MARKER": str(marker),
                "SYNASTRY_READING_TEST_RELEASE": str(release),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.wait_for_path(marker)
            finalizer = self.run_helper(
                ["finalize", str(status["token"]), "--out", str(destination)],
                input_text=valid_report(source),
            )
        finally:
            cancel_stdout, cancel_stderr = self.release_and_reap(process, release)

        self.assertEqual(finalizer.returncode, 2)
        self.assertFalse(destination.exists())
        self.assertEqual(process.returncode, 0, cancel_stderr)
        self.assertEqual(json.loads(cancel_stdout), {"status": "cancelled"})

    def test_signal_after_committing_rename_recovers_from_filesystem_state(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "commit-rename-signal.md"
        wrapper = """
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_rename = reading_session.os.rename

def rename_then_signal(source, destination):
    result = original_rename(source, destination)
    if Path(destination).name.startswith(".committing-"):
        os.kill(os.getpid(), signal.SIGTERM)
    return result

reading_session.os.rename = rename_then_signal
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={},
        )

        _, stderr = process.communicate(timeout=10)

        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assertEqual(list(self.session_root.iterdir()) if self.session_root.exists() else [], [])

    def test_restart_recovers_sigkill_after_committing_rename_before_install(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "sigkill-recovery.md"
        marker = self.directory / "sigkill-at-commit"
        wrapper = """
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

def kill_before_install(*args, **kwargs):
    Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
    os.kill(os.getpid(), signal.SIGKILL)

reading_session.install_validated_markdown = kill_before_install
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={"SYNASTRY_READING_TEST_MARKER": str(marker)},
        )

        _, stderr = process.communicate(timeout=10)
        self.wait_for_path(marker)
        committing = self.session_root / f".committing-{status['token']}"
        self.assertEqual(process.returncode, -signal.SIGKILL, stderr)
        self.assertTrue(committing.is_dir())
        self.assertFalse(destination.exists())

        replacement = self.start_without_watchdog(source)

        self.assertFalse(committing.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assertTrue(Path(str(replacement["pages_path"])).parent.is_dir())

    def test_conflicting_output_cannot_revoke_live_committing_claim_or_report_success(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source)
        destination = self.directory / "commit-conflict.md"
        destination.write_text("different\n", encoding="utf-8")
        destination.chmod(0o600)
        marker = self.directory / "conflict-install-blocked"
        release = self.directory / "release-conflicted-finalizer"
        wrapper = """
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_install = reading_session.install_validated_markdown

def block_before_install(*args, **kwargs):
    Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
    release = Path(os.environ["SYNASTRY_READING_TEST_RELEASE"])
    while not release.exists():
        time.sleep(0.02)
    return original_install(*args, **kwargs)

reading_session.install_validated_markdown = block_before_install
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={
                "SYNASTRY_READING_TEST_MARKER": str(marker),
                "SYNASTRY_READING_TEST_RELEASE": str(release),
            },
        )
        committing = self.session_root / f".committing-{status['token']}"
        try:
            self.wait_for_path(marker)
            reading_session._sweep_expired(self.session_root)
            retained_during_conflict = committing.is_dir()
        finally:
            _, finalizer_stderr = self.release_and_reap(process, release)

        self.assertTrue(retained_during_conflict)
        self.assertEqual(process.returncode, 2, finalizer_stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), "different\n")
        self.assertTrue(committing.is_dir())

    def test_expiry_claim_wins_before_commit_transition_and_prevents_output(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source, ttl_seconds=60)
        destination = self.directory / "expired-race.md"
        marker = self.directory / "expiry-check-blocked"
        release = self.directory / "release-expired-finalizer"
        wrapper = """
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

real_time = reading_session.time.time
real_sleep = reading_session.time.sleep
calls = 0
expires_at = int(os.environ["SYNASTRY_READING_TEST_EXPIRES_AT"])

def controlled_time():
    global calls
    calls += 1
    if calls == 2:
        Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
        release = Path(os.environ["SYNASTRY_READING_TEST_RELEASE"])
        while not release.exists():
            real_sleep(0.02)
    return expires_at - 1

reading_session.time.time = controlled_time
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={
                "SYNASTRY_READING_TEST_EXPIRES_AT": str(status["expires_at"]),
                "SYNASTRY_READING_TEST_MARKER": str(marker),
                "SYNASTRY_READING_TEST_RELEASE": str(release),
            },
        )
        try:
            self.wait_for_path(marker)
            expired = self.expire_in_process(
                str(status["token"]),
                int(status["expires_at"]),
            )
        finally:
            _, finalizer_stderr = self.release_and_reap(process, release)

        self.assertEqual(expired, 0)
        self.assertEqual(process.returncode, 2, finalizer_stderr)
        self.assertFalse(destination.exists())

    def test_committing_claim_wins_before_expiry_and_watchdog_cannot_revoke_it(self) -> None:
        source = source_with()
        status = self.start_without_watchdog(source, ttl_seconds=60)
        destination = self.directory / "committing-race.md"
        marker = self.directory / "commit-install-blocked"
        release = self.directory / "release-committing-finalizer"
        wrapper = """
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
import reading_session

original_install = reading_session.install_validated_markdown

def block_before_install(*args, **kwargs):
    Path(os.environ["SYNASTRY_READING_TEST_MARKER"]).write_text("ready", encoding="utf-8")
    release = Path(os.environ["SYNASTRY_READING_TEST_RELEASE"])
    while not release.exists():
        time.sleep(0.02)
    return original_install(*args, **kwargs)

reading_session.install_validated_markdown = block_before_install
raise SystemExit(
    reading_session.main(
        [
            "finalize",
            os.environ["SYNASTRY_READING_TEST_TOKEN"],
            "--out",
            os.environ["SYNASTRY_READING_TEST_DESTINATION"],
        ]
    )
)
"""
        process = self.start_finalizer_wrapper(
            wrapper,
            token=str(status["token"]),
            destination=destination,
            report=valid_report(source),
            extra_environment={
                "SYNASTRY_READING_TEST_MARKER": str(marker),
                "SYNASTRY_READING_TEST_RELEASE": str(release),
            },
        )
        committing = self.session_root / f".committing-{status['token']}"
        try:
            self.wait_for_path(marker)
            won_before_expiry = committing.is_dir()
            expired = self.expire_in_process(
                str(status["token"]),
                int(status["expires_at"]),
            )
            retained_or_completed = committing.is_dir() or (
                destination.is_file() and destination.read_text(encoding="utf-8") == valid_report(source)
            )
        finally:
            _, finalizer_stderr = self.release_and_reap(process, release)

        self.assertTrue(won_before_expiry)
        self.assertEqual(expired, 0)
        self.assertTrue(retained_or_completed)
        self.assertEqual(process.returncode, 0, finalizer_stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report(source))
        self.assertEqual(list(self.session_root.iterdir()) if self.session_root.exists() else [], [])


if __name__ == "__main__":
    unittest.main()
