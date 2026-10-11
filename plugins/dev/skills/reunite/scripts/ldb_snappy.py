"""Decode a raw Snappy block, the compression LevelDB applies to table blocks.

Only decompression is needed: this tool appends to LevelDB's write-ahead log, which is
never compressed, and reads tables, whose blocks may be.
"""

from __future__ import annotations

from ldb_codec import LevelDBError, read_varint

_LITERAL, _COPY_1, _COPY_2, _COPY_4 = 0, 1, 2, 3


def _literal(block: bytes, tag: int, pos: int) -> tuple[bytes, int]:
    length = tag >> 2
    if length >= 60:
        width = length - 59
        if pos + width > len(block):
            raise LevelDBError("snappy literal length runs past the block")
        length = int.from_bytes(block[pos : pos + width], "little")
        pos += width
    end = pos + length + 1
    if end > len(block):
        raise LevelDBError("snappy literal runs past the block")
    return block[pos:end], end


def _copy(block: bytes, tag: int, kind: int, pos: int) -> tuple[int, int, int]:
    """Return (length, offset, next position) for one copy element."""
    if kind == _COPY_1:
        if pos + 1 > len(block):
            raise LevelDBError("snappy copy runs past the block")
        return ((tag >> 2) & 0x7) + 4, ((tag >> 5) << 8) | block[pos], pos + 1
    width = 2 if kind == _COPY_2 else 4
    if pos + width > len(block):
        raise LevelDBError("snappy copy runs past the block")
    return (tag >> 2) + 1, int.from_bytes(block[pos : pos + width], "little"), pos + width


def decompress(block: bytes) -> bytes:
    """Expand one Snappy block, refusing anything malformed rather than guessing."""
    expected, pos = read_varint(block, 0)
    out = bytearray()
    while pos < len(block):
        tag = block[pos]
        pos += 1
        kind = tag & 0x3
        if kind == _LITERAL:
            literal, pos = _literal(block, tag, pos)
            out += literal
            continue
        length, offset, pos = _copy(block, tag, kind, pos)
        if offset == 0 or offset > len(out):
            raise LevelDBError("snappy copy offset outside the decoded output")
        start = len(out) - offset
        if offset >= length:
            out += out[start : start + length]
        else:
            for index in range(length):
                out.append(out[start + index])
    if len(out) != expected:
        raise LevelDBError(f"snappy block decoded to {len(out)} bytes, header says {expected}")
    return bytes(out)
