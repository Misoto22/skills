"""The byte-level encodings every LevelDB file is built from: varints and masked CRC32C.

The desktop app keeps its sidebar layout in Chromium's Local Storage, which is a LevelDB
database. Reading and appending to one without a native library means speaking its
on-disk format directly, and these are the primitives every part of that format uses.
"""

from __future__ import annotations


class LevelDBError(Exception):
    """The files on disk are not in the shape this reader understands, or are damaged."""


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Decode a little-endian base-128 varint at ``offset``; return (value, next offset)."""
    value = shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            break
    raise LevelDBError("truncated or overlong varint")


def encode_varint(value: int) -> bytes:
    """Encode a non-negative integer as a little-endian base-128 varint."""
    if value < 0:
        raise ValueError("varints encode non-negative integers only")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def read_slice(data: bytes, offset: int) -> tuple[bytes, int]:
    """Decode a varint length followed by that many bytes."""
    length, offset = read_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise LevelDBError("length-prefixed field runs past the end of its record")
    return data[offset:end], end


def _crc_table() -> list[int]:
    table = []
    for byte in range(256):
        crc = byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x82F63B78 if crc & 1 else crc >> 1
        table.append(crc)
    return table


_TABLE = _crc_table()
_MASK_DELTA = 0xA282EAD8


def crc32c(data: bytes, crc: int = 0) -> int:
    """CRC-32C (Castagnoli), extending ``crc`` — LevelDB's checksum for logs and tables."""
    crc ^= 0xFFFFFFFF
    table = _TABLE
    for byte in data:
        crc = table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def mask_crc(crc: int) -> int:
    """LevelDB stores a rotated CRC, so a CRC computed over data holding CRCs stays meaningful."""
    return ((((crc >> 15) | (crc << 17)) & 0xFFFFFFFF) + _MASK_DELTA) & 0xFFFFFFFF


def unmask_crc(masked: int) -> int:
    """Invert ``mask_crc``."""
    rotated = (masked - _MASK_DELTA) & 0xFFFFFFFF
    return ((rotated >> 17) | (rotated << 15)) & 0xFFFFFFFF
