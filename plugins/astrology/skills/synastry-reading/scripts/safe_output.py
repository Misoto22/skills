"""Install output bytes atomically, without ever replacing a file the caller forbade.

A validator that writes a ledger or a reading must not clobber the source it just
read, a file it was told not to overwrite, or anything swapped into the destination
while it worked. The install writes a private temporary, pins whatever it is about
to displace, and publishes with a hard link or an OS-level atomic exchange; every
identity is re-checked after the move, and a raced or aliased entry is put back.
There is deliberately no unconditional-replace fallback, so a platform without an
exchange primitive refuses an overwrite rather than racing it.
"""

from __future__ import annotations

import ctypes
import errno
import os
import secrets
import sys
from contextlib import suppress
from pathlib import Path

from file_identity import (
    SourceIdentityError,
    existing_regular_file_matches,
    path_identity,
    published_output_matches,
    regular_file_identity,
)


class OutputExistsError(FileExistsError):
    """An exclusive output destination already exists."""


def fsync_directory(path: Path) -> None:
    """Flush a directory's entries, so a rename or link inside it survives a crash."""

    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_atomic_bytes(
    payload: bytes,
    destination: Path,
    *,
    overwrite: bool,
    temporary_prefix: str,
    forbidden_identity: tuple[int, int] | None = None,
    accept_identical: bool = False,
) -> Path:
    """Publish payload at destination durably, or raise with the destination as it was.

    Without overwrite an existing entry raises OutputExistsError, unless
    accept_identical is set and it already holds exactly these bytes as a private
    regular file. An entry whose identity is forbidden_identity is never replaced:
    that raises SourceIdentityError, including when one is swapped in mid-install.
    """

    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    backup: Path | None = None
    recovery_directory: Path | None = None
    descriptor: int | None = None
    prepared_identity: tuple[int, int] | None = None
    try:
        for _ in range(32):
            candidate = destination.parent / f".{temporary_prefix}-{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            break
        if descriptor is None or temporary is None:
            raise FileExistsError(errno.EEXIST, "could not allocate an exclusive temporary file")

        descriptor_chmod = getattr(os, "fchmod", None)
        if descriptor_chmod is not None:
            descriptor_chmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError("could not complete file write")
            view = view[written:]
        os.fsync(descriptor)
        prepared_status = os.fstat(descriptor)
        prepared_identity = (prepared_status.st_dev, prepared_status.st_ino)
        os.close(descriptor)
        descriptor = None

        existing_identity = path_identity(destination)
        if forbidden_identity is not None and existing_identity == forbidden_identity:
            raise SourceIdentityError("output must not replace the source JSON")
        if not overwrite and existing_identity is not None:
            if accept_identical and existing_regular_file_matches(
                destination,
                payload,
                forbidden_identity=forbidden_identity,
            ):
                unpublished_temporary = temporary
                temporary = None
                _discard_published_temporary(unpublished_temporary)
                fsync_directory(destination.parent)
                return destination
            raise OutputExistsError(
                errno.EEXIST,
                f"output already exists: {destination}",
                destination,
            )

        if overwrite:
            if existing_identity is None:
                try:
                    os.link(temporary, destination)
                except FileExistsError as error:
                    raise OSError(errno.EBUSY, "output changed during installation") from error
                except BaseException:
                    if prepared_identity is None or regular_file_identity(destination) != prepared_identity:
                        raise
                published_temporary = temporary
                temporary = None
                _discard_published_temporary(published_temporary)
            else:
                regular_identity = regular_file_identity(destination)
                if regular_identity != existing_identity:
                    if forbidden_identity is not None and regular_identity == forbidden_identity:
                        raise SourceIdentityError("output must not replace the source JSON")
                    raise OSError(errno.EBUSY, "output changed during installation")
                backup = _pin_destination(destination, temporary_prefix)
                pinned_identity = regular_file_identity(backup)
                current_identity = regular_file_identity(destination)
                if pinned_identity != existing_identity or current_identity != existing_identity:
                    if forbidden_identity is not None and (
                        pinned_identity == forbidden_identity or current_identity == forbidden_identity
                    ):
                        raise SourceIdentityError("output must not replace the source JSON")
                    raise OSError(errno.EBUSY, "output changed during installation")
                recovery_directory = _allocate_recovery_directory(
                    destination.parent,
                    temporary_prefix,
                )
                exchange_paths(temporary, destination)
                inspection_error: OSError | None = None
                try:
                    displaced_identity = path_identity(temporary)
                    displaced_regular_identity = regular_file_identity(temporary)
                except OSError as error:
                    inspection_error = error
                    displaced_identity = None
                    displaced_regular_identity = None
                changed = (
                    inspection_error is not None
                    or displaced_identity != existing_identity
                    or displaced_regular_identity != existing_identity
                )
                source_alias = (
                    inspection_error is None
                    and forbidden_identity is not None
                    and (
                        displaced_identity == forbidden_identity
                        or displaced_regular_identity == forbidden_identity
                    )
                )
                if changed or source_alias:
                    try:
                        if prepared_identity is None:
                            raise OSError(errno.EIO, "prepared output identity is unavailable")
                        _restore_displaced_entry(
                            temporary,
                            destination,
                            prepared_identity,
                            recovery_directory,
                        )
                    except OSError:
                        # The exchanged entry and its pinned predecessor are recovery data.
                        # Never let generic temporary cleanup unlink either after restore failure.
                        temporary = None
                        backup = None
                        recovery_directory = None
                        raise
                    temporary = None
                    recovery_directory.rmdir()
                    recovery_directory = None
                    if backup is not None:
                        backup.unlink()
                        backup = None
                    if source_alias:
                        raise SourceIdentityError("output must not replace the source JSON")
                    raise OSError(errno.EBUSY, "output changed during installation") from inspection_error
                temporary.unlink()
                temporary = None
                backup.unlink()
                backup = None
                recovery_directory.rmdir()
                recovery_directory = None
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as error:
                if accept_identical and existing_regular_file_matches(
                    destination,
                    payload,
                    forbidden_identity=forbidden_identity,
                ):
                    unpublished_temporary = temporary
                    temporary = None
                    _discard_published_temporary(unpublished_temporary)
                    fsync_directory(destination.parent)
                    return destination
                raise OutputExistsError(
                    errno.EEXIST,
                    f"output already exists: {destination}",
                    destination,
                ) from error
            except BaseException:
                if not accept_identical or not published_output_matches(
                    destination,
                    payload,
                    forbidden_identity=forbidden_identity,
                ):
                    raise
            published_temporary = temporary
            temporary = None
            _discard_published_temporary(published_temporary)
        fsync_directory(destination.parent)
        return destination
    finally:
        try:
            if descriptor is not None:
                os.close(descriptor)
        finally:
            if temporary is not None:
                with suppress(FileNotFoundError):
                    temporary.unlink()
            if backup is not None:
                with suppress(FileNotFoundError):
                    backup.unlink()
            if recovery_directory is not None:
                with suppress(FileNotFoundError):
                    recovery_directory.rmdir()


def _discard_published_temporary(temporary: Path) -> None:
    """Best-effort cleanup that cannot invalidate an already published output."""

    try:
        temporary.unlink()
    except BaseException:
        # Publication is the commit point. A signal or unlink failure can leave a
        # private hard link, but must not turn the committed destination into failure.
        return


def _restore_displaced_entry(
    displaced: Path,
    destination: Path,
    prepared_identity: tuple[int, int],
    recovery_directory: Path,
) -> None:
    """Restore any displaced entry type and quarantine the installed output if needed."""

    if regular_file_identity(destination) != prepared_identity:
        raise OSError(errno.EBUSY, "installed output changed during recovery")
    try:
        os.replace(displaced, destination)
        return
    except OSError:
        pass

    installed_output = recovery_directory / "installed-output"
    installed_moved = False
    try:
        os.rename(destination, installed_output)
        installed_moved = True
        os.rename(displaced, destination)
        if regular_file_identity(installed_output) != prepared_identity:
            raise OSError(errno.EBUSY, "installed output changed during recovery")
        installed_output.unlink()
    except OSError as recovery_error:
        if not installed_moved:
            try:
                exchange_paths(displaced, destination)
                if regular_file_identity(displaced) != prepared_identity:
                    raise OSError(errno.EBUSY, "installed output changed during recovery")
                displaced.unlink()
            except OSError as fallback_error:
                raise recovery_error from fallback_error
            return
        # Once the installed output moves, every remaining path is recovery data:
        # the displaced entry, the quarantined output, or the restored destination.
        # The caller deliberately excludes them from generic cleanup on this error.
        raise


def _allocate_recovery_directory(parent: Path, temporary_prefix: str) -> Path:
    """Reserve a private sibling directory for a failed post-exchange recovery."""

    for _ in range(32):
        recovery = parent / f".{temporary_prefix}-recovery-{secrets.token_hex(8)}.tmp"
        try:
            recovery.mkdir(mode=0o700)
        except FileExistsError:
            continue
        return recovery
    raise FileExistsError(errno.EEXIST, "could not allocate an exclusive recovery directory")


def _pin_destination(destination: Path, temporary_prefix: str) -> Path:
    """Create an exclusive hard-link backup that pins the pre-install inode."""

    for _ in range(32):
        backup = destination.parent / f".{temporary_prefix}-backup-{secrets.token_hex(8)}.tmp"
        try:
            os.link(destination, backup, follow_symlinks=False)
        except FileExistsError:
            continue
        return backup
    raise FileExistsError(errno.EEXIST, "could not allocate an exclusive backup link")


def exchange_paths(first: Path, second: Path) -> None:
    """Atomically exchange entries only where the OS exposes a reviewed primitive.

    There is deliberately no ``os.replace`` fallback: a check followed by an
    unconditional replacement cannot defend the opened source identity from a
    hostile destination swap. Unsupported systems fail before either entry moves.
    """

    library = ctypes.CDLL(None, use_errno=True)
    encoded_first = os.fsencode(first)
    encoded_second = os.fsencode(second)
    if sys.platform == "darwin":
        operation = getattr(library, "renameatx_np", None)
        if operation is None:
            raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(-2, encoded_first, -2, encoded_second, 0x00000002)
    elif sys.platform.startswith("linux"):
        operation = getattr(library, "renameat2", None)
        if operation is None:
            raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        result = operation(-100, encoded_first, -100, encoded_second, 0x00000002)
    else:
        raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def write_stdout(payload: bytes) -> bool:
    """Write and flush stdout, quarantining a failed real pipe before finalization."""

    try:
        sys.stdout.write(payload.decode("utf-8"))
        sys.stdout.flush()
        return True
    except (OSError, ValueError):
        quarantine_stdout()
        return False


def quarantine_stdout() -> None:
    """Point stdout at the null device, so a broken pipe cannot fail a later write."""

    try:
        stdout_descriptor = sys.stdout.fileno()
        null_descriptor = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError, ValueError):
        return
    try:
        os.dup2(null_descriptor, stdout_descriptor)
    finally:
        os.close(null_descriptor)


def matches_identity(path: Path, identity: tuple[int, int] | None) -> bool:
    """Return whether path is the regular file with this (device, inode) identity."""

    return identity is not None and path_identity(path) == identity
