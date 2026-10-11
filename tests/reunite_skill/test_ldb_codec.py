"""The byte-level primitives LevelDB's files are built from: varints, CRC32C, and Snappy blocks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import ldb_codec
import ldb_snappy


class VarintTests(unittest.TestCase):
    def test_round_trips_across_byte_boundaries(self) -> None:
        for value in (0, 1, 127, 128, 300, 16_383, 16_384, 2**32 - 1, 2**63):
            encoded = ldb_codec.encode_varint(value)
            self.assertEqual(ldb_codec.read_varint(encoded + b"tail", 0), (value, len(encoded)))

    def test_known_encoding(self) -> None:
        self.assertEqual(ldb_codec.encode_varint(300), b"\xac\x02")

    def test_truncated_varint_is_an_error(self) -> None:
        with self.assertRaises(ldb_codec.LevelDBError):
            ldb_codec.read_varint(b"\x80\x80", 0)

    def test_negative_value_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ldb_codec.encode_varint(-1)

    def test_length_prefixed_slice(self) -> None:
        self.assertEqual(ldb_codec.read_slice(b"\x03abcd", 0), (b"abc", 4))
        with self.assertRaises(ldb_codec.LevelDBError):
            ldb_codec.read_slice(b"\x05ab", 0)


class Crc32cTests(unittest.TestCase):
    def test_castagnoli_check_value(self) -> None:
        self.assertEqual(ldb_codec.crc32c(b"123456789"), 0xE3069283)

    def test_rfc3720_vectors(self) -> None:
        self.assertEqual(ldb_codec.crc32c(b""), 0)
        self.assertEqual(ldb_codec.crc32c(bytes(32)), 0x8A9136AA)
        self.assertEqual(ldb_codec.crc32c(b"\xff" * 32), 0x62A8AB43)
        self.assertEqual(ldb_codec.crc32c(bytes(range(32))), 0x46DD794E)

    def test_extending_equals_one_pass(self) -> None:
        self.assertEqual(ldb_codec.crc32c(b"6789", ldb_codec.crc32c(b"12345")), 0xE3069283)

    def test_mask_is_reversible_and_changes_the_value(self) -> None:
        crc = ldb_codec.crc32c(b"foo")
        self.assertNotEqual(ldb_codec.mask_crc(crc), crc)
        self.assertEqual(ldb_codec.unmask_crc(ldb_codec.mask_crc(crc)), crc)
        self.assertEqual(ldb_codec.mask_crc(0), 0xA282EAD8)


class SnappyTests(unittest.TestCase):
    def test_literal_only(self) -> None:
        self.assertEqual(ldb_snappy.decompress(b"\x05\x10hello"), b"hello")

    def test_one_byte_offset_copy_overlaps_its_own_output(self) -> None:
        # literal "abc", then copy 9 bytes from 3 back: the copy reads bytes it is writing.
        self.assertEqual(ldb_snappy.decompress(b"\x0c\x08abc\x15\x03"), b"abc" * 4)

    def test_two_and_four_byte_offset_copies(self) -> None:
        two = b"\x08\x0cabcd" + bytes([0x02 | (3 << 2)]) + (4).to_bytes(2, "little")
        self.assertEqual(ldb_snappy.decompress(two), b"abcdabcd")
        four = b"\x08\x0cabcd" + bytes([0x03 | (3 << 2)]) + (4).to_bytes(4, "little")
        self.assertEqual(ldb_snappy.decompress(four), b"abcdabcd")

    def test_long_literal_lengths(self) -> None:
        payload = bytes(range(256)) * 2
        block = ldb_codec.encode_varint(len(payload)) + bytes([61 << 2]) + (511).to_bytes(2, "little")
        self.assertEqual(ldb_snappy.decompress(block + payload), payload)
        one = b"x" * 70
        block = ldb_codec.encode_varint(70) + bytes([60 << 2, 69]) + one
        self.assertEqual(ldb_snappy.decompress(block), one)

    def test_malformed_blocks_are_errors(self) -> None:
        for block in (
            b"\x05\x10hel",  # literal runs past the input
            b"\x04\x05\x00",  # copy with offset 0
            b"\x08\x00a\x15\x05",  # copy reaches before the output starts
            b"\x09\x10hello",  # declared length disagrees with the output
            b"\x0c\x08abc\x15",  # copy tag with its offset byte missing
        ):
            with self.subTest(block=block), self.assertRaises(ldb_codec.LevelDBError):
                ldb_snappy.decompress(block)


if __name__ == "__main__":
    unittest.main()
