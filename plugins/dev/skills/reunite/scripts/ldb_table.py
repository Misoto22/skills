"""Read a LevelDB table (``.ldb``/``.sst``): the sorted, immutable files a flush or compaction writes.

A table ends in a 48-byte footer naming its index block; the index block maps each data
block's last key to that block's offset and size. Every block is followed by a one-byte
compression type and a masked CRC32C, and its entries are prefix-compressed against the
previous key. Keys are internal keys: the user key, then eight bytes packing the
sequence number and whether the entry is a value or a deletion.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path

import ldb_snappy
from ldb_codec import LevelDBError, crc32c, read_varint, unmask_crc

FOOTER_SIZE = 48
TABLE_MAGIC = 0xDB4775248B80FB57
BLOCK_TRAILER_SIZE = 5
NO_COMPRESSION, SNAPPY_COMPRESSION = 0, 1


def read_handle(data: bytes, offset: int) -> tuple[int, int, int]:
    """Decode a BlockHandle: (block offset, block size, next position)."""
    block_offset, offset = read_varint(data, offset)
    size, offset = read_varint(data, offset)
    return block_offset, size, offset


def read_block(data: bytes, offset: int, size: int) -> bytes:
    """One block's contents, checksum-verified and decompressed."""
    end = offset + size
    if offset < 0 or end + BLOCK_TRAILER_SIZE > len(data):
        raise LevelDBError("table block runs past the end of the file")
    raw = data[offset:end]
    kind = data[end]
    (masked,) = struct.unpack_from("<I", data, end + 1)
    if unmask_crc(masked) != crc32c(bytes([kind]), crc32c(raw)):
        raise LevelDBError(f"table block checksum mismatch at offset {offset}")
    if kind == NO_COMPRESSION:
        return raw
    if kind == SNAPPY_COMPRESSION:
        return ldb_snappy.decompress(raw)
    raise LevelDBError(f"unsupported table block compression {kind}")


def block_entries(block: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Every (key, value) in a block, undoing the prefix compression between keys."""
    if len(block) < 4:
        raise LevelDBError("table block too short for its restart count")
    (restarts,) = struct.unpack_from("<I", block, len(block) - 4)
    limit = len(block) - 4 - 4 * restarts
    if limit < 0:
        raise LevelDBError("table block restart array runs past the block")
    pos, key = 0, b""
    while pos < limit:
        shared, pos = read_varint(block, pos)
        unshared, pos = read_varint(block, pos)
        value_length, pos = read_varint(block, pos)
        if shared > len(key) or pos + unshared + value_length > limit:
            raise LevelDBError("table block entry runs past the block")
        key = key[:shared] + block[pos : pos + unshared]
        pos += unshared
        yield key, block[pos : pos + value_length]
        pos += value_length


def table_entries(path: Path) -> Iterator[tuple[bytes, int, int, bytes]]:
    """Every entry in a table as (user key, sequence, value type, value)."""
    data = path.read_bytes()
    if len(data) < FOOTER_SIZE:
        raise LevelDBError(f"{path.name} is shorter than a table footer")
    footer = data[-FOOTER_SIZE:]
    if struct.unpack_from("<Q", footer, FOOTER_SIZE - 8)[0] != TABLE_MAGIC:
        raise LevelDBError(f"{path.name} does not end in a LevelDB table footer")
    _, _, pos = read_handle(footer, 0)
    index_offset, index_size, _ = read_handle(footer, pos)
    for _, handle in block_entries(read_block(data, index_offset, index_size)):
        block_offset, block_size, _ = read_handle(handle, 0)
        for internal_key, value in block_entries(read_block(data, block_offset, block_size)):
            if len(internal_key) < 8:
                raise LevelDBError(f"{path.name} holds an internal key shorter than its tag")
            (tag,) = struct.unpack_from("<Q", internal_key, len(internal_key) - 8)
            yield internal_key[:-8], tag >> 8, tag & 0xFF, value
