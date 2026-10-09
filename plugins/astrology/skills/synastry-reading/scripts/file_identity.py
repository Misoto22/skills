"""What sits at an output path, read without following a link or blocking on a device.

Every check an atomic install makes before and after it moves an entry comes down to
two questions: is this path one particular regular file, and does an existing file
already hold exactly these bytes. Both are answered here through a descriptor opened
with O_NOFOLLOW and compared against the lstat of the same path, so a symlink, FIFO,
socket or directory swapped in at the wrong moment is refused rather than read.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from pathlib import Path


class SourceIdentityError(ValueError):
    """An output path names the opened source artifact."""


def regular_file_identity(path: Path) -> tuple[int, int] | None:
    """Return one non-symlink regular-file identity, rejecting other entry types."""

    try:
        link_status = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(link_status.st_mode):
        raise OSError(errno.EINVAL, "overwrite destination must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened_status = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = (opened_status.st_dev, opened_status.st_ino)
    if not stat.S_ISREG(opened_status.st_mode) or identity != (link_status.st_dev, link_status.st_ino):
        raise OSError(errno.EBUSY, "output changed during installation")
    return identity


def path_identity(path: Path) -> tuple[int, int] | None:
    """Return one regular-file identity without blocking on or following special entries."""

    return regular_file_identity(path)


def existing_regular_file_matches(
    destination: Path,
    payload: bytes,
    *,
    forbidden_identity: tuple[int, int] | None,
) -> bool:
    """Compare bytes through one pinned regular-file descriptor without following links."""

    link_status = os.lstat(destination)
    if not stat.S_ISREG(link_status.st_mode):
        raise OSError(errno.EINVAL, "existing output must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags)
    try:
        opened_status = os.fstat(descriptor)
        identity = (opened_status.st_dev, opened_status.st_ino)
        if not stat.S_ISREG(opened_status.st_mode) or identity != (
            link_status.st_dev,
            link_status.st_ino,
        ):
            raise OSError(errno.EBUSY, "output changed during installation")
        if forbidden_identity is not None and identity == forbidden_identity:
            raise SourceIdentityError("output must not replace the source JSON")
        if hasattr(os, "getuid") and opened_status.st_uid != os.getuid():
            return False
        if stat.S_IMODE(opened_status.st_mode) != 0o600:
            return False
        initial_fingerprint = (
            opened_status.st_size,
            opened_status.st_mtime_ns,
            opened_status.st_ctime_ns,
            opened_status.st_mode,
            opened_status.st_uid,
        )
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 65_536)
            if not chunk:
                break
            digest.update(chunk)
        final_status = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (final_status.st_dev, final_status.st_ino) != identity:
        raise OSError(errno.EBUSY, "output changed during installation")
    final_fingerprint = (
        final_status.st_size,
        final_status.st_mtime_ns,
        final_status.st_ctime_ns,
        final_status.st_mode,
        final_status.st_uid,
    )
    if final_fingerprint != initial_fingerprint:
        raise OSError(errno.EBUSY, "output changed during installation")
    if regular_file_identity(destination) != identity:
        raise OSError(errno.EBUSY, "output changed during installation")
    return final_status.st_size == len(payload) and digest.digest() == hashlib.sha256(payload).digest()


def published_output_matches(
    destination: Path,
    payload: bytes,
    *,
    forbidden_identity: tuple[int, int] | None,
) -> bool:
    """Return false when interrupted publication left no destination."""

    try:
        return existing_regular_file_matches(
            destination,
            payload,
            forbidden_identity=forbidden_identity,
        )
    except FileNotFoundError:
        return False
