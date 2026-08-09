#!/usr/bin/env python3
"""Manage one private, expiring synastry-reading validation session."""

from __future__ import annotations

import argparse
import errno
import hashlib
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
from dataclasses import replace
from pathlib import Path

from validate_reading import (
    ReadingError,
    _install_prepared_markdown,
    install_validated_markdown,
    prepare_validated_markdown,
)
from validate_synastry import (
    EvidenceLedger,
    OutputExistsError,
    SchemaError,
    SourceIdentityError,
    _existing_regular_file_matches,
    _ledger_bytes,
    _quarantine_stdout,
    load_ledger,
)

DEFAULT_TTL_SECONDS = 900
MAX_TTL_SECONDS = 3600
PAGE_BYTES = 16_384
_TOKEN = re.compile(r"\A[0-9a-f]{32}\Z")
_HIDDEN_STATE = re.compile(r"\A\.(staging|finalizing|cancelling|committing)-([0-9a-f]{32})\Z")
_ROOT_ENV = "SYNASTRY_READING_SESSION_ROOT"
_SESSION_FORMAT = "synastry-reading-session-v1"
_LEASE_MANIFEST = "lease.json"
_COMMIT_PAYLOAD = "commit.md"
_COMMIT_MANIFEST = "commit.json"
_HANDLED_SIGNAL_NAMES = ("SIGINT", "SIGTERM", "SIGHUP")
_CLOCK_GRACE_SECONDS = 5


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


def _absolute_output_path(path: Path, root: Path) -> Path:
    expanded = path.expanduser()
    absolute = expanded if expanded.is_absolute() else Path.cwd() / expanded
    try:
        resolved_parent = absolute.parent.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise ValueError("invalid output path") from error
    candidate = resolved_parent / absolute.name
    if candidate.is_relative_to(resolved_root):
        raise ValueError("final output must be outside the private session")
    return candidate


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


def _cancelling_path(root: Path, token: str) -> Path:
    _session_path(root, token)
    return root / f".cancelling-{token}"


def _committing_path(root: Path, token: str) -> Path:
    _session_path(root, token)
    return root / f".committing-{token}"


def _state_path(root: Path, token: str, state: str) -> Path:
    paths = {
        "staging": _staging_path,
        "public": _session_path,
        "finalizing": _finalizing_path,
        "cancelling": _cancelling_path,
        "committing": _committing_path,
    }
    try:
        return paths[state](root, token)
    except KeyError as error:
        raise ValueError("invalid session state") from error


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


def _read_metadata(session: Path, token: str) -> dict[str, object]:
    payload = json.loads(_read_private_bytes(session / "session.json").decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("invalid session metadata")
    if payload.get("format") != _SESSION_FORMAT or payload.get("token") != token:
        raise ValueError("invalid session metadata")
    expires_at = _strict_int(payload.get("expires_at"), "session expiry")
    if _persisted_expiry(session, token) != expires_at:
        raise ValueError("inconsistent session lease")
    return payload


def _strict_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"invalid {label}")
    return value


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


def _best_effort_remove_private_tree(path: Path) -> None:
    try:
        _remove_private_tree(path)
    except BaseException:
        # A committing state is recovery data after publication. Cleanup cannot
        # reverse or invalidate the content-addressed destination.
        return


def _owned_state(candidate: Path) -> tuple[str, str] | None:
    if _TOKEN.fullmatch(candidate.name):
        state_token = ("public", candidate.name)
    else:
        match = _HIDDEN_STATE.fullmatch(candidate.name)
        if match is None:
            return None
        state_token = match.group(1), match.group(2)
    try:
        status = os.lstat(candidate)
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
        return None
    if hasattr(os, "getuid") and status.st_uid != os.getuid():
        return None
    return state_token


def _fallback_deadline(candidate: Path) -> int:
    try:
        observed_mtime = min(int(os.lstat(candidate).st_mtime), int(time.time()))
    except FileNotFoundError:
        return 0
    return observed_mtime + MAX_TTL_SECONDS + _CLOCK_GRACE_SECONDS


def _candidate_token(candidate: Path) -> str | None:
    if _TOKEN.fullmatch(candidate.name):
        return candidate.name
    match = _HIDDEN_STATE.fullmatch(candidate.name)
    return None if match is None else match.group(2)


def _state_deadline(candidate: Path, state: str) -> int:
    fallback = _fallback_deadline(candidate)
    token = _candidate_token(candidate)
    if token is None:
        return fallback
    expires_at = _persisted_expiry(candidate, token)
    if expires_at is None:
        return fallback
    if state != "committing":
        return expires_at
    try:
        manifest = json.loads(_read_private_bytes(candidate / _COMMIT_MANIFEST).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("invalid commit manifest")
        return _validated_commit_deadline(candidate, token, expires_at, manifest)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _persisted_expiry(candidate: Path, token: str) -> int | None:
    records: list[tuple[int, int]] = []
    for name in ("session.json", _LEASE_MANIFEST):
        try:
            payload = json.loads(_read_private_bytes(candidate / name).decode("utf-8"))
            if not isinstance(payload, dict):
                return None
            if payload.get("format") != _SESSION_FORMAT or payload.get("token") != token:
                return None
            created_at = _strict_int(payload.get("created_at"), "lease creation time")
            expires_at = _strict_int(payload.get("expires_at"), "lease expiry")
            records.append((created_at, expires_at))
        except FileNotFoundError:
            continue
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
    if not records or any(record != records[0] for record in records[1:]):
        return None
    created_at, expires_at = records[0]
    if not 1 <= expires_at - created_at <= MAX_TTL_SECONDS:
        return None
    try:
        modified_at = int(os.lstat(candidate).st_mtime)
    except FileNotFoundError:
        return None
    if created_at > modified_at + _CLOCK_GRACE_SECONDS:
        return None
    if expires_at < modified_at - _CLOCK_GRACE_SECONDS:
        return None
    if expires_at > modified_at + MAX_TTL_SECONDS + _CLOCK_GRACE_SECONDS:
        return None
    return expires_at


def _validated_commit_deadline(
    committing: Path,
    token: str,
    expires_at: int,
    manifest: Mapping[str, object],
) -> int:
    if manifest.get("format") != _SESSION_FORMAT or manifest.get("token") != token:
        raise ValueError("invalid commit identity")
    if _strict_int(manifest.get("expires_at"), "commit expiry") != expires_at:
        raise ValueError("inconsistent commit expiry")
    recover_after = _strict_int(manifest.get("recover_after"), "commit recovery time")
    modified_at = int(os.lstat(committing).st_mtime)
    if not modified_at - _CLOCK_GRACE_SECONDS <= recover_after <= modified_at + _CLOCK_GRACE_SECONDS:
        raise ValueError("invalid commit recovery time")
    if recover_after > expires_at + _CLOCK_GRACE_SECONDS:
        raise ValueError("commit recovery exceeds the session lease")
    return recover_after


def _transition_state(root: Path, token: str, source_state: str, target_state: str) -> Path:
    source = _state_path(root, token, source_state)
    target = _state_path(root, token, target_state)
    if _entry_exists(target):
        raise ValueError("session state is unavailable")
    try:
        os.rename(source, target)
    except FileNotFoundError as error:
        raise ValueError("session state is unavailable") from error
    return target


def _discard_expired_state(root: Path, token: str, state: str, now: int) -> bool:
    candidate = _state_path(root, token, state)
    if _owned_state(candidate) != (state, token) or _state_deadline(candidate, state) > now:
        return False
    if state == "cancelling":
        _best_effort_remove_private_tree(_cancelling_path(root, token))
        return True
    try:
        cancelling = _transition_state(root, token, state, "cancelling")
    except ValueError:
        return False
    _best_effort_remove_private_tree(cancelling)
    return True


def _sweep_expired(root: Path) -> None:
    if not root.exists():
        return
    now = int(time.time())
    for candidate in tuple(root.iterdir()):
        owned = _owned_state(candidate)
        if owned is None:
            continue
        state, token = owned
        if state == "committing":
            if _state_deadline(candidate, state) <= now:
                _recover_committing(root, candidate)
        else:
            _discard_expired_state(root, token, state, now)


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

    for name in _HANDLED_SIGNAL_NAMES:
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


@contextmanager
def _defer_cleanup_signals() -> Iterator[None]:
    """Defer handled signals until a rename result is recorded by the caller."""

    mask_operation = getattr(signal, "pthread_sigmask", None)
    if mask_operation is None:
        yield
        return
    signals = {
        signum for name in _HANDLED_SIGNAL_NAMES if (signum := getattr(signal, name, None)) is not None
    }
    previous = mask_operation(signal.SIG_BLOCK, signals)
    try:
        yield
    finally:
        mask_operation(signal.SIG_SETMASK, previous)


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
            created_at = int(time.time())
            expires_at = created_at + arguments.ttl_seconds
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
                conflicts = (
                    session,
                    _finalizing_path(root, token),
                    _cancelling_path(root, token),
                    _committing_path(root, token),
                )
                if any(_entry_exists(path) for path in conflicts):
                    _remove_private_tree(staging)
                    continue
                break

            _write_private(
                staging / _LEASE_MANIFEST,
                json.dumps(
                    {
                        "created_at": created_at,
                        "expires_at": expires_at,
                        "format": _SESSION_FORMAT,
                        "token": token,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
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
                "created_at": created_at,
                "expires_at": expires_at,
                "format": _SESSION_FORMAT,
                "source": stored_source,
                "source_digest": ledger.source_digest,
                "source_kind": source_kind,
                "token": token,
            }
            _write_private(
                staging / "session.json",
                json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            )
            if expires_at <= int(time.time()):
                raise ValueError("session expired during construction")
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
    return _transition_state(root, token, "public", "finalizing")


def _cleanup_claim(root: Path, claimed: Path) -> None:
    _remove_private_tree(claimed)
    _prune_root(root)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_commit(
    claimed: Path,
    token: str,
    expires_at: int,
    target: Path,
    payload: bytes,
    ledger: EvidenceLedger,
) -> None:
    _write_private(claimed / _COMMIT_PAYLOAD, payload)
    manifest = {
        "destination": str(target),
        "expires_at": expires_at,
        "format": _SESSION_FORMAT,
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "recover_after": int(time.time()),
        "source_device": ledger.source_device,
        "source_inode": ledger.source_inode,
        "token": token,
    }
    _write_private(
        claimed / _COMMIT_MANIFEST,
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    _fsync_directory(claimed)


def _read_private_bytes(path: Path) -> bytes:
    link_status = os.lstat(path)
    if not stat.S_ISREG(link_status.st_mode) or stat.S_ISLNK(link_status.st_mode):
        raise OSError("private commit entry is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened_status = os.fstat(descriptor)
        identity = (opened_status.st_dev, opened_status.st_ino)
        if identity != (link_status.st_dev, link_status.st_ino):
            raise OSError("private commit entry changed while opening")
        if hasattr(os, "getuid") and opened_status.st_uid != os.getuid():
            raise OSError("private commit entry has the wrong owner")
        if stat.S_IMODE(opened_status.st_mode) != 0o600:
            raise OSError("private commit entry has unsafe permissions")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        final_status = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (final_status.st_dev, final_status.st_ino) != identity:
        raise OSError("private commit entry changed while reading")
    if not stat.S_ISREG(final_status.st_mode) or stat.S_IMODE(final_status.st_mode) != 0o600:
        raise OSError("private commit entry changed type or permissions")
    current_status = os.lstat(path)
    if (current_status.st_dev, current_status.st_ino) != identity:
        raise OSError("private commit entry changed after reading")
    return b"".join(chunks)


def _commit_material(root: Path, committing: Path) -> tuple[bytes, Path, tuple[int, int] | None]:
    owned = _owned_state(committing)
    if owned is None or owned[0] != "committing":
        raise ValueError("invalid committing state")
    _, token = owned
    expires_at = _persisted_expiry(committing, token)
    if expires_at is None:
        raise ValueError("invalid committing lease")
    payload = _read_private_bytes(committing / _COMMIT_PAYLOAD)
    manifest_bytes = _read_private_bytes(committing / _COMMIT_MANIFEST)
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("invalid commit manifest")
    _validated_commit_deadline(committing, token, expires_at, manifest)
    payload_bytes = _strict_int(manifest.get("payload_bytes"), "commit payload length")
    if payload_bytes < 0 or payload_bytes != len(payload):
        raise ValueError("commit payload length changed")
    payload_sha256 = manifest.get("payload_sha256")
    if (
        not isinstance(payload_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", payload_sha256) is None
        or payload_sha256 != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError("commit payload digest changed")
    destination = manifest.get("destination")
    if not isinstance(destination, str):
        raise ValueError("invalid commit destination")
    target = Path(destination)
    if not target.is_absolute():
        raise ValueError("invalid commit destination")
    target = _absolute_output_path(target, root)
    device = manifest["source_device"]
    inode = manifest["source_inode"]
    if device is None and inode is None:
        forbidden_identity = None
    elif (
        isinstance(device, int)
        and not isinstance(device, bool)
        and device >= 0
        and isinstance(inode, int)
        and not isinstance(inode, bool)
        and inode >= 0
    ):
        forbidden_identity = device, inode
    else:
        raise ValueError("invalid source identity")
    return payload, target, forbidden_identity


def _require_exact_committed_output(
    payload: bytes,
    target: Path,
    forbidden_identity: tuple[int, int] | None,
) -> None:
    if not _existing_regular_file_matches(
        target,
        payload,
        forbidden_identity=forbidden_identity,
    ):
        raise OutputExistsError(
            errno.EEXIST,
            f"output differs from committed bytes: {target}",
            target,
        )


def _ledger_source_identity(ledger: EvidenceLedger) -> tuple[int, int] | None:
    if ledger.source_device is None and ledger.source_inode is None:
        return None
    if ledger.source_device is None or ledger.source_inode is None:
        raise ValueError("invalid source identity")
    return ledger.source_device, ledger.source_inode


def _complete_known_commit(
    payload: bytes,
    target: Path,
    ledger: EvidenceLedger,
) -> None:
    install_validated_markdown(
        payload,
        ledger,
        target,
        accept_identical=True,
    )
    _require_exact_committed_output(payload, target, _ledger_source_identity(ledger))


def _complete_committing(root: Path, committing: Path) -> None:
    payload, target, forbidden_identity = _commit_material(root, committing)
    _install_prepared_markdown(
        payload,
        target,
        forbidden_identity=forbidden_identity,
        accept_identical=True,
    )
    _require_exact_committed_output(payload, target, forbidden_identity)
    _best_effort_remove_private_tree(committing)
    try:
        _prune_root(root)
    except BaseException:
        return


def _recover_committing(root: Path, committing: Path) -> bool:
    try:
        _complete_committing(root, committing)
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        OutputExistsError,
        SourceIdentityError,
        TypeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
    return True


def _finalize(arguments: argparse.Namespace) -> int:
    root = _root(create=False)
    claimed: Path | None = None
    committing: Path | None = None
    with _cleanup_signal_handlers():
        try:
            with _defer_cleanup_signals():
                claimed = _claim_session(root, arguments.token)
            metadata = _read_metadata(claimed, arguments.token)
            expires_at = _strict_int(metadata.get("expires_at"), "session expiry")
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
            destination = _absolute_output_path(arguments.out, root)
            markdown = sys.stdin.read()
            content_ledger = replace(ledger, source_device=None, source_inode=None)
            target, payload = prepare_validated_markdown(
                markdown,
                content_ledger,
                destination,
                arguments.language or ledger.language,
                arguments.modules,
            )
            if expires_at <= int(time.time()):
                raise ValueError("session expired")
            _prepare_commit(
                claimed,
                arguments.token,
                expires_at,
                target,
                payload,
                ledger,
            )
            if expires_at <= int(time.time()):
                raise ValueError("session expired")
            with _defer_cleanup_signals():
                committing = _transition_state(root, arguments.token, "finalizing", "committing")
                claimed = None
                _fsync_directory(root)
            _complete_known_commit(payload, target, ledger)
            _best_effort_remove_private_tree(committing)
            with suppress(BaseException):
                _prune_root(root)
            committing = None
        except _SignalInterruption:
            if committing is not None:
                _complete_known_commit(payload, target, ledger)
                _best_effort_remove_private_tree(committing)
                with suppress(BaseException):
                    _prune_root(root)
                committing = None
                return 0
            raise
        finally:
            if claimed is not None:
                _cleanup_claim(root, claimed)
    return 0


def _cancel(arguments: argparse.Namespace) -> int:
    root = _root(create=False)
    cancelling: Path | None = None
    with _cleanup_signal_handlers():
        try:
            with _defer_cleanup_signals():
                cancelling = _transition_state(root, arguments.token, "public", "cancelling")
            _remove_private_tree(cancelling)
            cancelling = None
            _prune_root(root)
            _emit({"status": "cancelled"})
        finally:
            if cancelling is not None:
                _best_effort_remove_private_tree(cancelling)
                _prune_root(root)
    return 0


def _expire(arguments: argparse.Namespace) -> int:
    root = _root(create=False)
    tracked_states = ("staging", "public", "finalizing", "cancelling", "committing")
    while True:
        if not root.exists():
            return 0
        observed: list[tuple[str, Path, int]] = []
        for state in tracked_states:
            path = _state_path(root, arguments.token, state)
            if _owned_state(path) == (state, arguments.token):
                observed.append((state, path, _state_deadline(path, state)))
        if not observed:
            return 0
        now = int(time.time())
        due = [entry for entry in observed if entry[2] <= now]
        if not due:
            delay = min(deadline for _, _, deadline in observed) - now
            time.sleep(max(0.01, min(delay, 1)))
            continue
        attempted_commit_recovery = False
        for state, path, _deadline in due:
            if state == "committing":
                attempted_commit_recovery = True
                _recover_committing(root, path)
            else:
                _discard_expired_state(root, arguments.token, state, now)
        with suppress(BaseException):
            _prune_root(root)
        if attempted_commit_recovery:
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
