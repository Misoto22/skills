#!/usr/bin/env python3
"""Manage one private, expiring synastry-reading validation session."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from pathlib import Path

from validate_reading import (
    ReadingError,
    install_validated_markdown,
    prepare_validated_markdown,
)
from validate_synastry import (
    OutputExistsError,
    SchemaError,
    SourceIdentityError,
    _ledger_bytes,
    _quarantine_stdout,
    load_ledger,
)

DEFAULT_TTL_SECONDS = 900
MAX_TTL_SECONDS = 3600
PAGE_BYTES = 16_384
_TOKEN = re.compile(r"\A[0-9a-f]{32}\Z")
_ROOT_ENV = "SYNASTRY_READING_SESSION_ROOT"


class _SignalInterruption(BaseException):
    """A catchable process signal that preserves conventional shell status."""

    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(signum)


def _root(*, create: bool) -> Path:
    configured = os.environ.get(_ROOT_ENV)
    root = (
        Path(configured).expanduser()
        if configured
        else Path(tempfile.gettempdir()) / f"synastry-reading-{getattr(os, 'getuid', lambda: 0)()}"
    )
    if create:
        with suppress(FileExistsError):
            root.mkdir(mode=0o700, parents=True)
    if root.exists():
        status = os.lstat(root)
        if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
            raise OSError("session root is not a private directory")
        if hasattr(os, "getuid") and status.st_uid != os.getuid():
            raise OSError("session root has the wrong owner")
        os.chmod(root, 0o700)
    return root


def _session_path(root: Path, token: str) -> Path:
    if not _TOKEN.fullmatch(token):
        raise ValueError("invalid session token")
    return root / token


def _staging_path(root: Path, token: str) -> Path:
    _session_path(root, token)
    return root / f".staging-{token}"


def _finalizing_path(root: Path, token: str) -> Path:
    _session_path(root, token)
    return root / f".finalizing-{token}"


def _write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_ledger_pages(session: Path, payload: bytes) -> tuple[Path, int]:
    pages = session / "ledger-pages"
    pages.mkdir(mode=0o700)
    offset = 0
    page_count = 0
    while offset < len(payload):
        end = min(offset + PAGE_BYTES, len(payload))
        while end < len(payload) and payload[end] & 0b1100_0000 == 0b1000_0000:
            end -= 1
        if end <= offset:
            raise ValueError("could not split ledger at a UTF-8 boundary")
        _write_private(pages / f"{page_count:06d}.part", payload[offset:end])
        offset = end
        page_count += 1
    return pages, page_count


def _read_metadata(session: Path) -> dict[str, object]:
    with (session / "session.json").open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("invalid session metadata")
    return payload


def _entry_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _remove_private_tree(path: Path) -> None:
    """Remove one private tree idempotently when another cleanup may win."""

    for _ in range(2):
        if not _entry_exists(path):
            return
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            continue
        if not _entry_exists(path):
            return
    if _entry_exists(path):
        raise OSError("private session cleanup did not complete")


def _prune_root(root: Path) -> None:
    with suppress(OSError):
        root.rmdir()


def _remove_session(root: Path, token: str, *, prune_root: bool = True) -> None:
    _remove_private_tree(_session_path(root, token))
    if prune_root:
        _prune_root(root)


def _remove_start_state(root: Path, token: str) -> None:
    _remove_private_tree(_staging_path(root, token))
    _remove_private_tree(_session_path(root, token))
    _prune_root(root)


def _sweep_expired(root: Path) -> None:
    if not root.exists():
        return
    now = int(time.time())
    for candidate in root.iterdir():
        if not candidate.is_dir() or not _TOKEN.fullmatch(candidate.name):
            continue
        try:
            expires_at = int(_read_metadata(candidate)["expires_at"])
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            expires_at = 0
        if expires_at <= now:
            _remove_session(root, candidate.name, prune_root=False)


def _spawn_watchdog(token: str, expires_at: int) -> None:
    environment = os.environ.copy()
    subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_expire",
            token,
            "--expires-at",
            str(expires_at),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
        env=environment,
    )


@contextmanager
def _cleanup_signal_handlers() -> Iterator[None]:
    """Turn common interactive termination signals into cleanup-safe exceptions."""

    previous: dict[int, object] = {}

    def interrupt(signum: int, _frame: object) -> None:
        raise _SignalInterruption(signum)

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        signum = getattr(signal, name, None)
        if signum is None or signum in previous:
            continue
        try:
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupt)
        except (OSError, ValueError):
            previous.pop(signum, None)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _emit(payload: Mapping[str, object]) -> None:
    try:
        sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    except (OSError, ValueError):
        _quarantine_stdout()
        raise


def _start(arguments: argparse.Namespace) -> int:
    if not 1 <= arguments.ttl_seconds <= MAX_TTL_SECONDS:
        raise ValueError("invalid session lifetime")
    if arguments.source == "-":
        source_payload = json.load(sys.stdin)
        if not isinstance(source_payload, Mapping):
            raise TypeError("pasted source must be a JSON object")
        ledger = load_ledger(source_payload)
        source_kind = "pasted"
        source_value: object = source_payload
    else:
        source_path = Path(arguments.source).expanduser().absolute()
        ledger = load_ledger(source_path)
        source_kind = "attached"
        source_value = str(source_path)

    root: Path | None = None
    token: str | None = None
    complete = False
    with _cleanup_signal_handlers():
        try:
            root = _root(create=True)
            _sweep_expired(root)
            while True:
                token = secrets.token_hex(16)
                session = _session_path(root, token)
                staging = _staging_path(root, token)
                try:
                    staging.mkdir(mode=0o700)
                except FileNotFoundError:
                    _root(create=True)
                    continue
                except FileExistsError:
                    continue
                if _entry_exists(session) or _entry_exists(_finalizing_path(root, token)):
                    _remove_private_tree(staging)
                    continue
                break

            expires_at = int(time.time()) + arguments.ttl_seconds
            # Arm bounded cleanup before writing any source or ledger bytes.
            _spawn_watchdog(token, expires_at)
            if source_kind == "pasted":
                source_file = staging / "source.json"
                _write_private(
                    source_file,
                    json.dumps(source_value, ensure_ascii=False, sort_keys=True).encode("utf-8"),
                )
                stored_source = "source.json"
            else:
                stored_source = source_value
            ledger_payload = _ledger_bytes(ledger)
            _, page_count = _write_ledger_pages(staging, ledger_payload)
            metadata = {
                "expires_at": expires_at,
                "source": stored_source,
                "source_digest": ledger.source_digest,
                "source_kind": source_kind,
            }
            _write_private(
                staging / "session.json",
                json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            )
            os.rename(staging, session)
            pages_path = session / "ledger-pages"
            _emit(
                {
                    "expires_at": expires_at,
                    "ledger_bytes": len(ledger_payload),
                    "page_bytes": PAGE_BYTES,
                    "page_count": page_count,
                    "pages_path": str(pages_path),
                    "status": "ready",
                    "token": token,
                }
            )
            complete = True
        finally:
            if not complete and root is not None and token is not None:
                _remove_start_state(root, token)
    return 0


def _claim_session(root: Path, token: str) -> Path:
    session = _session_path(root, token)
    claimed = _finalizing_path(root, token)
    if _entry_exists(claimed):
        raise ValueError("session is already finalizing")
    try:
        os.rename(session, claimed)
    except FileNotFoundError as error:
        raise ValueError("session is unavailable") from error
    return claimed


def _cleanup_claim(root: Path, claimed: Path) -> None:
    _remove_private_tree(claimed)
    _prune_root(root)


def _finalize(arguments: argparse.Namespace) -> int:
    root = _root(create=False)
    claimed = _claim_session(root, arguments.token)
    prepared = False
    with _cleanup_signal_handlers():
        try:
            metadata = _read_metadata(claimed)
            expires_at = int(metadata["expires_at"])
            if expires_at <= int(time.time()):
                raise ValueError("session expired")
            if metadata["source_kind"] == "pasted":
                source: str | Path = claimed / str(metadata["source"])
            elif metadata["source_kind"] == "attached":
                source = str(metadata["source"])
            else:
                raise ValueError("invalid source kind")
            ledger = load_ledger(source)
            if ledger.source_digest != metadata["source_digest"]:
                raise ValueError("source changed")
            destination = arguments.out.expanduser().resolve(strict=False)
            if destination.is_relative_to(root.resolve(strict=False)):
                raise ValueError("final output must be outside the private session")
            markdown = sys.stdin.read()
            target, payload = prepare_validated_markdown(
                markdown,
                ledger,
                destination,
                arguments.language or ledger.language,
                arguments.modules,
            )
            if expires_at <= int(time.time()):
                raise ValueError("session expired")
            _cleanup_claim(root, claimed)
            prepared = True
        finally:
            if not prepared:
                _cleanup_claim(root, claimed)

    # Installation is the terminal operation: no status write or session cleanup follows it.
    install_validated_markdown(payload, ledger, target)
    return 0


def _cancel(arguments: argparse.Namespace) -> int:
    root = _root(create=False)
    _remove_session(root, arguments.token)
    _emit({"status": "cancelled"})
    return 0


def _expire(arguments: argparse.Namespace) -> int:
    root = _root(create=False)
    session = _session_path(root, arguments.token)
    staging = _staging_path(root, arguments.token)
    finalizing = _finalizing_path(root, arguments.token)
    states = (staging, session, finalizing)
    while True:
        if not root.exists() or not any(_entry_exists(path) for path in states):
            return 0
        delay = arguments.expires_at - int(time.time())
        if delay <= 0:
            break
        time.sleep(min(delay, 1))
    for state in states:
        if not _entry_exists(state):
            continue
        if state == staging:
            _remove_private_tree(state)
            continue
        try:
            expires_at = int(_read_metadata(state)["expires_at"])
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            expires_at = 0
        if expires_at <= int(time.time()):
            _remove_private_tree(state)
    _prune_root(root)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="validate a source and create a private ledger session")
    start.add_argument("source", help="attached JSON path, or - for pasted JSON on stdin")
    start.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS)
    start.set_defaults(handler=_start)
    finalize = commands.add_parser("finalize", help="validate stdin Markdown and install final output")
    finalize.add_argument("token")
    finalize.add_argument("--language")
    finalize.add_argument("--module", action="append", default=[], dest="modules")
    finalize.add_argument("--out", type=Path, required=True)
    finalize.set_defaults(handler=_finalize)
    cancel = commands.add_parser("cancel", help="remove a private session")
    cancel.add_argument("token")
    cancel.set_defaults(handler=_cancel)
    expire = commands.add_parser("_expire", help=argparse.SUPPRESS)
    expire.add_argument("token")
    expire.add_argument("--expires-at", type=int, required=True)
    expire.set_defaults(handler=_expire)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return int(arguments.handler(arguments))
    except _SignalInterruption as error:
        return 128 + error.signum
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        OutputExistsError,
        ReadingError,
        SchemaError,
        SourceIdentityError,
        TypeError,
        UnicodeError,
        ValueError,
    ):
        print("error: session operation failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
