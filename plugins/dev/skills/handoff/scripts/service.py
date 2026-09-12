"""Install and observe the local watcher without relying on a live chat's hooks."""

from __future__ import annotations

import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

LABEL = "local.skills.handoff"


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".handoff-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _owned_plist(path: Path, runner: Path) -> bool:
    try:
        data = plistlib.loads(path.read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False
    args = data.get("ProgramArguments", [])
    return data.get("Label") == LABEL and len(args) >= 3 and args[1:3] == [str(runner), "watch"]


def install_watcher(
    home: Path,
    runner: Path,
    *,
    run=subprocess.run,
    system: str | None = None,
    interval: float = 30,
) -> dict:
    """Install one user launch agent; other platforms can run `watch` themselves."""
    if (system or platform.system()) != "Darwin":
        return {"status": "not-installed", "reason": "run_watch_under_your_service_manager"}
    if interval < 5:
        raise ValueError("watcher_interval_too_short")
    directory = home / ".claude/handoff"
    plist = home / "Library/LaunchAgents" / (LABEL + ".plist")
    if plist.exists() and not _owned_plist(plist, runner):
        raise ValueError("watcher_label_conflict")
    codex = shutil.which("codex")
    if not codex:
        raise ValueError("native_client_unavailable")
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("watcher.log", "watcher-error.log"):
        path = directory / name
        path.touch(exist_ok=True)
        path.chmod(0o600)
    data = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(runner),
            "watch",
            "--home",
            str(home),
            "--interval",
            str(interval),
            "--codex-binary",
            codex,
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 15,
        "ProcessType": "Background",
        "StandardOutPath": str(directory / "watcher.log"),
        "StandardErrorPath": str(directory / "watcher-error.log"),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    domain = f"gui/{os.getuid()}"
    target = domain + "/" + LABEL
    # Only stop this service, and only after all configuration validation passed.
    run(["launchctl", "bootout", target], capture_output=True, text=True, check=False)
    _write(plist, plistlib.dumps(data))
    # launchd can briefly report EIO while the previous owned job finishes unloading.
    for delay in (0, 0.1, 0.2, 0.4, 0.8):
        if delay:
            time.sleep(delay)
        result = run(
            ["launchctl", "bootstrap", domain, str(plist)], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return {"status": "installed", "plist": str(plist), "label": LABEL}
        if result.returncode != 5:
            break
    raise ValueError("watcher_bootstrap_failed")


def uninstall_watcher(home: Path, runner: Path, *, run=subprocess.run) -> dict:
    plist = home / "Library/LaunchAgents" / (LABEL + ".plist")
    if not plist.exists():
        return {"status": "not-installed"}
    if not _owned_plist(plist, runner):
        raise ValueError("watcher_label_conflict")
    run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True, text=True, check=False)
    plist.unlink()
    return {"status": "uninstalled"}


def request_sync(home: Path) -> Path:
    """Wake the watcher without saving hook payloads or blocking the caller's turn."""
    path = home / ".claude/handoff/sync-request"
    _write(path, b"")
    return path


def record_result(home: Path, report: dict) -> dict:
    errors = report.get("errors", [])
    unfinished = report.get("unfinished", [])
    result = {
        "completed_at": time.time(),
        "pid": os.getpid(),
        "status": "incomplete" if errors or unfinished else "complete",
        "counts": report.get("counts", {}),
        "outcomes": dict(Counter(r.get("status", "unknown") for r in report.get("results", []))),
        "error_count": len(errors),
        "unfinished_count": len(unfinished),
    }
    directory = home / ".claude/handoff"
    _write(
        directory / "last-sync-report.json",
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode(),
    )
    _write(directory / "watcher-state.json", (json.dumps(result, indent=2) + "\n").encode())
    return result


def run_once(home: Path, *, apply: bool, codex_binary: str = "codex", native=None) -> dict:
    from native import NativeCodex
    from sync import Paths, synchronize

    paths = Paths(home)
    own_client = native is None
    client = native or NativeCodex(home / ".codex", executable=codex_binary)
    try:
        return synchronize(paths, client, apply=apply)
    finally:
        if own_client:
            client.close()


def watch(home: Path, *, interval: float = 30, codex_binary: str = "codex") -> None:
    from native import NativeCodex

    if interval < 5:
        raise ValueError("watcher_interval_too_short")
    os.umask(0o077)
    native = NativeCodex(home / ".codex", executable=codex_binary)
    request = home / ".claude/handoff/sync-request"
    try:
        while True:
            # Removing the old request before scanning preserves a new request that
            # arrives while this pass is reading a growing transcript.
            request.unlink(missing_ok=True)
            try:
                report = run_once(home, apply=True, codex_binary=codex_binary, native=native)
            except Exception as error:
                report = {"errors": [{"error": type(error).__name__}], "unfinished": [{"status": "error"}]}
                native.close()
                native = NativeCodex(home / ".codex", executable=codex_binary)
            summary = record_result(home, report)
            print(json.dumps(summary, separators=(",", ":")), flush=True)
            if summary["error_count"]:
                native.close()
                native = NativeCodex(home / ".codex", executable=codex_binary)
            deadline = time.monotonic() + interval
            while time.monotonic() < deadline:
                time.sleep(min(1, max(0, deadline - time.monotonic())))
                if request.exists():
                    break
    finally:
        native.close()
