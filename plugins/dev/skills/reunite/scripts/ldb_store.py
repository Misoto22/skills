"""Read one key's latest value from a LevelDB directory, and append a new value for it.

What is live is what the MANIFEST says: ``CURRENT`` names it, and it is a log of
VersionEdits recording which tables exist, which write-ahead log is current, and the
last sequence number handed out. A key's value is the entry with the highest sequence
number across those tables and the live logs; a deletion with the highest sequence
means the key is gone.

Writing appends one WriteBatch to the newest live log, numbered past every sequence on
disk. LevelDB replays its logs when it next opens the database, so the value takes
effect then — which is also why nothing may hold the database open while this writes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import ldb_log
import ldb_table
from ldb_codec import LevelDBError, read_slice, read_varint

_MANIFEST_NAME = re.compile(r"MANIFEST-(\d+)")
_LOG_NAME = re.compile(r"(\d+)\.log")
TAG_COMPARATOR, TAG_LOG_NUMBER, TAG_NEXT_FILE, TAG_LAST_SEQUENCE = 1, 2, 3, 4
TAG_COMPACT_POINTER, TAG_DELETED_FILE, TAG_NEW_FILE, TAG_PREV_LOG_NUMBER = 5, 6, 7, 9


@dataclass
class Version:
    """The database state the MANIFEST describes."""

    log_number: int = 0
    prev_log_number: int = 0
    last_sequence: int = 0
    tables: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class Found:
    """The newest entry for one key, and the highest sequence anywhere in the database."""

    value: bytes | None
    sequence: int
    max_sequence: int


def _apply_edit(version: Version, edit: bytes) -> None:
    pos = 0
    while pos < len(edit):
        tag, pos = read_varint(edit, pos)
        if tag == TAG_COMPARATOR:
            _, pos = read_slice(edit, pos)
        elif tag in (TAG_LOG_NUMBER, TAG_NEXT_FILE, TAG_LAST_SEQUENCE, TAG_PREV_LOG_NUMBER):
            number, pos = read_varint(edit, pos)
            if tag == TAG_LOG_NUMBER:
                version.log_number = number
            elif tag == TAG_PREV_LOG_NUMBER:
                version.prev_log_number = number
            elif tag == TAG_LAST_SEQUENCE:
                version.last_sequence = number
        elif tag == TAG_COMPACT_POINTER:
            _, pos = read_varint(edit, pos)
            _, pos = read_slice(edit, pos)
        elif tag == TAG_DELETED_FILE:
            _, pos = read_varint(edit, pos)
            number, pos = read_varint(edit, pos)
            version.tables.discard(number)
        elif tag == TAG_NEW_FILE:
            _, pos = read_varint(edit, pos)
            number, pos = read_varint(edit, pos)
            _, pos = read_varint(edit, pos)
            _, pos = read_slice(edit, pos)
            _, pos = read_slice(edit, pos)
            version.tables.add(number)
        else:
            raise LevelDBError(f"unknown MANIFEST tag {tag}")


def read_version(directory: Path) -> Version:
    """Replay the MANIFEST that CURRENT names."""
    try:
        name = (directory / "CURRENT").read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise LevelDBError(f"no readable CURRENT in {directory}: {error}") from error
    if not _MANIFEST_NAME.fullmatch(name):
        raise LevelDBError(f"CURRENT in {directory} names {name!r}, not a MANIFEST")
    try:
        data = (directory / name).read_bytes()
    except OSError as error:
        raise LevelDBError(f"cannot read {name} in {directory}: {error}") from error
    version = Version()
    for edit in ldb_log.read_records(data).records:
        _apply_edit(version, edit)
    return version


def live_logs(directory: Path, version: Version) -> list[Path]:
    """The write-ahead logs LevelDB replays on open, oldest first."""
    found = []
    for path in directory.iterdir():
        match = _LOG_NAME.fullmatch(path.name)
        if match:
            number = int(match.group(1))
            if number >= version.log_number or number == version.prev_log_number:
                found.append((number, path))
    return [path for _, path in sorted(found)]


def table_path(directory: Path, number: int) -> Path:
    """A live table's file: ``.ldb``, or ``.sst`` from older LevelDB versions."""
    for suffix in (".ldb", ".sst"):
        path = directory / f"{number:06d}{suffix}"
        if path.is_file():
            return path
    raise LevelDBError(f"the MANIFEST lists table {number:06d}, which is missing from {directory}")


def _log_entries(path: Path):
    for record in ldb_log.read_records(path.read_bytes()).records:
        for sequence, kind, key, value in ldb_log.decode_batch(record):
            yield key, sequence, kind, value


def find(directory: Path, key: bytes) -> Found:
    """The newest entry for ``key`` across every live table and log."""
    version = read_version(directory)
    sources = [ldb_table.table_entries(table_path(directory, n)) for n in sorted(version.tables)]
    sources += [_log_entries(path) for path in live_logs(directory, version)]
    best: tuple[int, int, bytes | None] = (-1, ldb_log.TYPE_DELETION, None)
    highest = version.last_sequence
    for source in sources:
        for user_key, sequence, kind, value in source:
            highest = max(highest, sequence)
            if user_key == key and sequence > best[0]:
                best = (sequence, kind, value)
    value = best[2] if best[1] == ldb_log.TYPE_VALUE else None
    return Found(value, best[0], highest)


def read(directory: Path, key: bytes) -> bytes | None:
    """The current value of ``key``, or None when it is absent or deleted."""
    return find(directory, key).value


def put(directory: Path, key: bytes, value: bytes) -> int:
    """Append a put for ``key`` to the newest live log; return the sequence it was given."""
    version = read_version(directory)
    logs = live_logs(directory, version)
    if not logs:
        raise LevelDBError(f"no live write-ahead log in {directory} to append to")
    current = logs[-1]
    if not ldb_log.read_records(current.read_bytes()).clean_end:
        raise LevelDBError(f"{current.name} ends inside a record; the database was not closed cleanly")
    sequence = find(directory, key).max_sequence + 1
    ldb_log.append_record(current, ldb_log.encode_batch(sequence, key, value))
    return sequence
