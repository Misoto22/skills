"""Use Codex's native session importer instead of inventing task database rows."""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class NativeError(RuntimeError):
    """A stable local error code, without raw server messages or session content."""


@dataclass(frozen=True)
class ImportResult:
    thread_id: str
    rollout_path: Path
    changed: bool


class NativeCodex:
    """One serial JSON-RPC connection; importing a session never starts a model turn."""

    def __init__(
        self,
        codex_home: Path,
        executable: str = "codex",
        *,
        command: list[str] | None = None,
        timeout: float = 60,
    ):
        self.home = codex_home.expanduser().resolve()
        self.command = command or [executable, "app-server", "--stdio"]
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self.messages: queue.Queue = queue.Queue()
        self.notifications: list[dict] = []
        self.sequence = 0
        self.detected: set[str] = set()
        self.detection_complete = False

    def begin_pass(self) -> None:
        self.detection_complete = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    def start(self) -> None:
        if self.process is not None:
            return
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env={**os.environ, "CODEX_HOME": str(self.home)},
            )
        except OSError as error:
            raise NativeError("native_client_unavailable") from error
        threading.Thread(target=self._read, daemon=True).start()
        try:
            result = self.call(
                "initialize",
                {
                    "clientInfo": {"name": "session_handoff", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            actual_home = result.get("codexHome")
            if not isinstance(actual_home, str) or Path(actual_home).resolve() != self.home:
                raise NativeError("native_home_mismatch")
            self._send({"method": "initialized", "params": {}})
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            if stream:
                stream.close()

    def _read(self) -> None:
        process = self.process
        assert process is not None and process.stdout is not None
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict):
                    self.messages.put(message)
        finally:
            self.messages.put(None)

    def _send(self, message: dict) -> None:
        assert self.process is not None and self.process.stdin is not None
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError) as error:
            raise NativeError("native_connection_closed") from error

    def _next(self, deadline: float) -> dict:
        try:
            message = self.messages.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty as error:
            raise NativeError("native_request_timeout") from error
        if message is None:
            raise NativeError("native_connection_closed")
        return message

    def _remember(self, message: dict) -> None:
        if message.get("method") == "externalAgentConfig/import/completed":
            self.notifications.append(message)
        elif "id" in message and "method" in message:
            # No import should ask to execute a tool or obtain a permission grant.
            self._send({"id": message["id"], "error": {"code": -32601, "message": "Unsupported request"}})

    def call(self, method: str, params: dict, *, timeout: float | None = None) -> dict:
        if self.process is None:
            self.start()
        self.sequence += 1
        request_id = self.sequence
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while True:
            message = self._next(deadline)
            if message.get("id") == request_id:
                if "error" in message:
                    raise NativeError("native_request_failed:" + method)
                result = message.get("result")
                if not isinstance(result, dict):
                    raise NativeError("native_invalid_response:" + method)
                return result
            self._remember(message)

    def _completed(self, import_id: str) -> dict:
        deadline = time.monotonic() + self.timeout
        while True:
            for i, message in enumerate(self.notifications):
                if message.get("params", {}).get("importId") == import_id:
                    return self.notifications.pop(i)["params"]
            self._remember(self._next(deadline))

    def existing_imports(self) -> list[dict]:
        path = self.home / "external_agent_session_imports.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            raise NativeError("native_import_registry_unreadable") from error
        records = data.get("records") if isinstance(data, dict) else None
        if not isinstance(records, list):
            raise NativeError("native_import_registry_invalid")
        return [
            record
            for record in records
            if isinstance(record, dict)
            and isinstance(record.get("source_path"), str)
            and isinstance(record.get("imported_thread_id"), str)
        ]

    def _detect(self, cwd: str) -> None:
        result = self.call(
            "externalAgentConfig/detect",
            {
                "migrationSource": "claude",
                "includeHome": True,
                "cwds": [cwd],
                "maxSessionAgeDays": 36500,
                "maxSessions": 1000000,
            },
            # Native discovery scans the complete local archive before returning.
            timeout=max(self.timeout, 300),
        )
        self.detection_complete = True
        for item in result.get("items", []):
            if not isinstance(item, dict) or item.get("itemType") != "SESSIONS":
                continue
            for session in (item.get("details") or {}).get("sessions", []):
                path = session.get("path")
                if isinstance(path, str):
                    self.detected.add(str(Path(path).resolve()))

    def read_thread(self, thread_id: str) -> dict[str, Any]:
        result = self.call("thread/read", {"threadId": thread_id, "includeTurns": False})
        thread = result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("path"), str):
            raise NativeError("native_thread_unreadable")
        if not Path(thread["path"]).is_file():
            raise NativeError("native_rollout_missing")
        return thread

    def import_session(self, source) -> ImportResult:
        path = str(source.path.resolve())
        existing = next(
            (r for r in self.existing_imports() if str(Path(r["source_path"]).resolve()) == path), None
        )
        if path not in self.detected and (
            not self.detection_complete or "-handoff-imports" in source.path.parts
        ):
            self._detect(source.cwd)
        if path not in self.detected:
            raise NativeError("native_session_not_detected")
        result = self.call(
            "externalAgentConfig/import",
            {
                "migrationSource": "claude",
                "source": "session_handoff",
                "migrationItems": [
                    {
                        "itemType": "SESSIONS",
                        "description": "Synchronize one local conversation",
                        "details": {"sessions": [{"path": path, "cwd": source.cwd, "title": source.title}]},
                    }
                ],
            },
        )
        import_id = result.get("importId")
        if not isinstance(import_id, str):
            raise NativeError("native_import_id_missing")
        completed = self._completed(import_id)
        successes = []
        for outcome in completed.get("itemTypeResults", []):
            if outcome.get("itemType") != "SESSIONS":
                continue
            for failure in outcome.get("failures", []):
                code = failure.get("subErrorType") or "import_failed"
                safe_code = (
                    code if isinstance(code, str) and re.fullmatch(r"[a-z_]+", code) else "import_failed"
                )
                raise NativeError("native_import_failed:" + safe_code)
            successes.extend(outcome.get("successes", []))
        success = next(
            (
                s
                for s in successes
                if isinstance(s.get("source"), str)
                and str(Path(s["source"]).resolve()) == path
                and isinstance(s.get("target"), str)
            ),
            None,
        )
        thread_id = success["target"] if success else existing["imported_thread_id"] if existing else None
        if not thread_id:
            raise NativeError("native_no_import_result")
        thread = self.read_thread(thread_id)
        if success and existing is None and source.title:
            self.call("thread/name/set", {"threadId": thread_id, "name": source.title})
        if success and existing is None and source.archived:
            self.call("thread/archive", {"threadId": thread_id})
            thread = self.read_thread(thread_id)
        return ImportResult(thread_id, Path(thread["path"]), changed=success is not None)
