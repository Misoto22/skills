"""LevelDB's log format: the write-ahead log and the MANIFEST are both written in it.

A log is a sequence of 32 KiB blocks. Each record carries a 7-byte header — masked
CRC32C, payload length, fragment type — and a record that does not fit in what is left
of a block is split into FIRST, MIDDLE and LAST fragments. A block tail too short for a
header is zero-filled. The write-ahead log's records are WriteBatches: a sequence
number, a count, then that many puts and deletes.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

from ldb_codec import LevelDBError, crc32c, encode_varint, mask_crc, read_slice, unmask_crc

BLOCK_SIZE = 32 * 1024
HEADER_SIZE = 7
ZERO, FULL, FIRST, MIDDLE, LAST = 0, 1, 2, 3, 4
TYPE_DELETION, TYPE_VALUE = 0, 1
_HEADER = struct.Struct("<IHB")
_BATCH_HEADER = struct.Struct("<QI")


@dataclass(frozen=True)
class LogScan:
    """Every complete record in a log, and whether the file ends on a record boundary.

    A log whose writer died mid-record ends in a fragment; LevelDB drops it on replay,
    but anything appended after it would be read as part of that broken record.
    """

    records: list[bytes]
    clean_end: bool


def _checked_fragment(data: bytes, pos: int) -> tuple[int, bytes] | None:
    """The (type, payload) of the fragment at ``pos``, or None when the file ends inside it."""
    if pos + HEADER_SIZE > len(data):
        return None
    masked, length, kind = _HEADER.unpack_from(data, pos)
    start = pos + HEADER_SIZE
    if start + length > len(data):
        return None
    payload = data[start : start + length]
    if kind == ZERO and length == 0:
        return kind, payload
    if kind not in (FULL, FIRST, MIDDLE, LAST):
        raise LevelDBError(f"unknown log record type {kind} at offset {pos}")
    if unmask_crc(masked) != crc32c(payload, crc32c(bytes([kind]))):
        raise LevelDBError(f"log record checksum mismatch at offset {pos}")
    return kind, payload


def read_records(data: bytes) -> LogScan:
    """Reassemble the logical records of a log file's bytes, verifying every checksum."""
    records: list[bytes] = []
    pending: bytearray | None = None
    pos = 0
    while pos < len(data):
        left = BLOCK_SIZE - pos % BLOCK_SIZE
        if left < HEADER_SIZE:
            pos += left
            continue
        fragment = _checked_fragment(data, pos)
        if fragment is None:
            return LogScan(records, False)
        kind, payload = fragment
        pos += HEADER_SIZE + len(payload)
        if kind == FULL and pending is None:
            records.append(payload)
        elif kind == FIRST and pending is None:
            pending = bytearray(payload)
        elif kind in (MIDDLE, LAST) and pending is not None:
            pending += payload
            if kind == LAST:
                records.append(bytes(pending))
                pending = None
        elif kind != ZERO:
            raise LevelDBError(f"log fragment out of sequence at offset {pos}")
    return LogScan(records, pending is None)


def encode_record(payload: bytes, file_size: int) -> bytes:
    """The bytes that append ``payload`` as one logical record to a log of ``file_size`` bytes.

    This mirrors LevelDB's log::Writer::AddRecord, so the result is what LevelDB itself
    would have written at that offset.
    """
    out = bytearray()
    block_offset = file_size % BLOCK_SIZE
    pos, begin = 0, True
    while True:
        leftover = BLOCK_SIZE - block_offset
        if leftover < HEADER_SIZE:
            out += bytes(leftover)
            block_offset = 0
        available = BLOCK_SIZE - block_offset - HEADER_SIZE
        fragment = payload[pos : pos + available]
        end = pos + len(fragment) == len(payload)
        kind = FULL if begin and end else FIRST if begin else LAST if end else MIDDLE
        crc = mask_crc(crc32c(fragment, crc32c(bytes([kind]))))
        out += _HEADER.pack(crc, len(fragment), kind) + fragment
        block_offset += HEADER_SIZE + len(fragment)
        pos += len(fragment)
        begin = False
        if end:
            return bytes(out)


def append_record(path: Path, payload: bytes) -> None:
    """Append one logical record to the log at ``path`` and fsync it."""
    with path.open("ab") as handle:
        handle.write(encode_record(payload, handle.tell()))
        handle.flush()
        os.fsync(handle.fileno())


def encode_batch(sequence: int, key: bytes, value: bytes) -> bytes:
    """A WriteBatch holding exactly one put."""
    body = bytes([TYPE_VALUE]) + encode_varint(len(key)) + key + encode_varint(len(value)) + value
    return _BATCH_HEADER.pack(sequence, 1) + body


def decode_batch(payload: bytes) -> list[tuple[int, int, bytes, bytes | None]]:
    """Each operation in a WriteBatch as (sequence, type, key, value or None for a delete)."""
    if len(payload) < _BATCH_HEADER.size:
        raise LevelDBError("write batch shorter than its header")
    sequence, count = _BATCH_HEADER.unpack_from(payload)
    pos = _BATCH_HEADER.size
    operations: list[tuple[int, int, bytes, bytes | None]] = []
    for index in range(count):
        if pos >= len(payload):
            raise LevelDBError("write batch holds fewer operations than its count")
        kind = payload[pos]
        key, pos = read_slice(payload, pos + 1)
        if kind == TYPE_VALUE:
            value, pos = read_slice(payload, pos)
            operations.append((sequence + index, kind, key, value))
        elif kind == TYPE_DELETION:
            operations.append((sequence + index, kind, key, None))
        else:
            raise LevelDBError(f"unknown write batch operation {kind}")
    if pos != len(payload):
        raise LevelDBError("write batch carries bytes past its last operation")
    return operations
