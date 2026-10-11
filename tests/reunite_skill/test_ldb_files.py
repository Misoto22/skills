"""LevelDB's log and table formats, read and written against a database real LevelDB produced.

The fixture under fixtures/leveldb-sidebar/ was written by Node's classic-level (LevelDB
with Snappy) and compacted, so its table blocks are Snappy-compressed and a few later
writes sit only in the write-ahead log; fixtures/README.md records how. Every test works
on a temporary copy.
"""

from __future__ import annotations

import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import ldb_log
import ldb_store
import ldb_table
from ldb_codec import LevelDBError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "leveldb-sidebar"
ORIGIN = b"_https://claude.ai\x00\x01"
DFRAME = ORIGIN + b"dframe-store"
BLOCK = ldb_log.BLOCK_SIZE


def fragment_types(data: bytes) -> list[int]:
    """The type byte of every fragment header, walking the blocks the way a reader does."""
    kinds, pos = [], 0
    while pos < len(data):
        if BLOCK - pos % BLOCK < ldb_log.HEADER_SIZE:
            pos += BLOCK - pos % BLOCK
            continue
        _, length, kind = struct.unpack_from("<IHB", data, pos)
        kinds.append(kind)
        pos += ldb_log.HEADER_SIZE + length
    return kinds


class LogRecordTests(unittest.TestCase):
    def test_a_small_record_is_one_full_fragment(self) -> None:
        data = ldb_log.encode_record(b"hello", 0)
        self.assertEqual(fragment_types(data), [ldb_log.FULL])
        self.assertEqual(ldb_log.read_records(data), ldb_log.LogScan([b"hello"], True))

    def test_a_value_over_one_block_is_fragmented_across_blocks(self) -> None:
        payload = bytes(range(256)) * 300  # 76,800 bytes: three blocks
        data = ldb_log.encode_record(payload, 0)
        self.assertEqual(fragment_types(data), [ldb_log.FIRST, ldb_log.MIDDLE, ldb_log.LAST])
        self.assertEqual(data[BLOCK + 6], ldb_log.MIDDLE)
        self.assertEqual(ldb_log.read_records(data).records, [payload])

    def test_a_block_tail_shorter_than_a_header_is_zero_filled(self) -> None:
        first = ldb_log.encode_record(b"a" * (BLOCK - 3 - ldb_log.HEADER_SIZE), 0)
        self.assertEqual(len(first), BLOCK - 3)
        second = ldb_log.encode_record(b"next", len(first))
        self.assertEqual(second[:3], b"\x00\x00\x00")
        scan = ldb_log.read_records(first + second)
        self.assertEqual(scan.records[1], b"next")
        self.assertTrue(scan.clean_end)

    def test_a_tail_of_exactly_one_header_starts_with_an_empty_first_fragment(self) -> None:
        first = ldb_log.encode_record(b"a" * (BLOCK - 2 * ldb_log.HEADER_SIZE), 0)
        second = ldb_log.encode_record(b"spill", len(first))
        self.assertEqual(fragment_types(first + second), [ldb_log.FULL, ldb_log.FIRST, ldb_log.LAST])
        self.assertEqual(ldb_log.read_records(first + second).records[1], b"spill")

    def test_a_torn_tail_is_reported_and_dropped(self) -> None:
        data = ldb_log.encode_record(b"kept", 0) + ldb_log.encode_record(b"torn", 11)
        scan = ldb_log.read_records(data[:-1])
        self.assertEqual(scan, ldb_log.LogScan([b"kept"], False))
        unfinished = ldb_log.encode_record(b"x" * BLOCK, 0)[:BLOCK]
        self.assertFalse(ldb_log.read_records(unfinished).clean_end)

    def test_a_checksum_mismatch_is_an_error(self) -> None:
        data = bytearray(ldb_log.encode_record(b"hello", 0))
        data[-1] ^= 0xFF
        with self.assertRaises(LevelDBError):
            ldb_log.read_records(bytes(data))

    def test_a_fragment_out_of_sequence_is_an_error(self) -> None:
        payload = b"x" * BLOCK
        last_only = ldb_log.encode_record(payload, 0)[BLOCK:]
        with self.assertRaises(LevelDBError):
            ldb_log.read_records(last_only)

    def test_append_record_writes_at_the_end_of_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "000001.log"
            path.write_bytes(ldb_log.encode_record(b"one", 0))
            ldb_log.append_record(path, b"two" * 20_000)
            self.assertEqual(ldb_log.read_records(path.read_bytes()).records, [b"one", b"two" * 20_000])


class WriteBatchTests(unittest.TestCase):
    def test_a_put_round_trips(self) -> None:
        batch = ldb_log.encode_batch(41, b"key", b"value")
        self.assertEqual(ldb_log.decode_batch(batch), [(41, ldb_log.TYPE_VALUE, b"key", b"value")])

    def test_deletes_and_sequences_within_one_batch(self) -> None:
        batch = struct.pack("<QI", 7, 2) + b"\x00\x01a" + b"\x01\x01b\x01c"
        self.assertEqual(ldb_log.decode_batch(batch), [(7, 0, b"a", None), (8, 1, b"b", b"c")])

    def test_malformed_batches_are_errors(self) -> None:
        for batch in (
            b"short",
            struct.pack("<QI", 1, 2) + b"\x01\x01a\x01b",
            struct.pack("<QI", 1, 1) + b"\x07\x01a",
            struct.pack("<QI", 1, 1) + b"\x01\x01a\x01bEXTRA",
        ):
            with self.subTest(batch=batch), self.assertRaises(LevelDBError):
                ldb_log.decode_batch(batch)


class FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "leveldb"
        shutil.copytree(FIXTURE, self.db)


class TableTests(FixtureCase):
    def test_reads_every_entry_of_a_snappy_table(self) -> None:
        entries = sorted(ldb_table.table_entries(self.db / "000005.ldb"), key=lambda entry: entry[1])
        by_key = {key: (kind, value) for key, _, kind, value in entries}
        versions = [kind for key, _, kind, _ in entries if key == DFRAME]
        # Older versions survive in the table; only the highest sequence is the value.
        self.assertEqual(versions, [ldb_log.TYPE_VALUE, ldb_log.TYPE_DELETION, ldb_log.TYPE_VALUE])
        self.assertEqual(by_key[DFRAME][0], ldb_log.TYPE_VALUE)
        self.assertIn(b'"codeSidebarByScope"', by_key[DFRAME][1])
        self.assertEqual(by_key[ORIGIN + b"filler-039"][0], ldb_log.TYPE_DELETION)
        self.assertEqual(sum(1 for key in by_key if key.startswith(ORIGIN + b"filler-")), 40)

    def test_the_fixture_really_holds_snappy_blocks(self) -> None:
        data = (self.db / "000005.ldb").read_bytes()
        footer = data[-ldb_table.FOOTER_SIZE :]
        _, _, pos = ldb_table.read_handle(footer, 0)
        index_offset, index_size, _ = ldb_table.read_handle(footer, pos)
        kinds = set()
        for _, handle in ldb_table.block_entries(ldb_table.read_block(data, index_offset, index_size)):
            offset, size, _ = ldb_table.read_handle(handle, 0)
            kinds.add(data[offset + size])
        self.assertIn(ldb_table.SNAPPY_COMPRESSION, kinds)

    def test_a_damaged_block_is_an_error(self) -> None:
        path = self.db / "000005.ldb"
        data = bytearray(path.read_bytes())
        data[10] ^= 0xFF
        path.write_bytes(bytes(data))
        with self.assertRaises(LevelDBError):
            list(ldb_table.table_entries(path))

    def test_a_file_without_the_footer_magic_is_refused(self) -> None:
        path = self.db / "000005.ldb"
        path.write_bytes(path.read_bytes()[:-1] + b"\x00")
        with self.assertRaises(LevelDBError):
            list(ldb_table.table_entries(path))
        path.write_bytes(b"tiny")
        with self.assertRaises(LevelDBError):
            list(ldb_table.table_entries(path))


class StoreTests(FixtureCase):
    def test_reads_the_value_compacted_into_the_table(self) -> None:
        value = ldb_store.read(self.db, DFRAME)
        self.assertEqual(value[:1], b"\x01")
        state = json.loads(value[1:].decode("latin-1"))["state"]
        self.assertEqual(len(state["codeSidebarByScope"]), 2)

    def test_the_log_overrides_the_table_and_a_deletion_hides_a_put(self) -> None:
        self.assertEqual(ldb_store.read(self.db, ORIGIN + b"filler-000"), b'\x01{"n":0,"rewritten":true}')
        self.assertEqual(ldb_store.read(self.db, ORIGIN + b"after-compaction"), b"\x01log-only")
        self.assertIsNone(ldb_store.read(self.db, ORIGIN + b"filler-039"))
        self.assertIsNone(ldb_store.read(self.db, ORIGIN + b"never-written"))

    def test_put_appends_a_value_the_reader_then_returns(self) -> None:
        before = ldb_store.find(self.db, DFRAME)
        table = (self.db / "000005.ldb").read_bytes()
        large = b"\x01" + json.dumps({"state": {"pad": "y" * 70_000}, "version": 0}).encode("latin-1")

        sequence = ldb_store.put(self.db, DFRAME, large)

        self.assertEqual(sequence, before.max_sequence + 1)
        self.assertEqual(ldb_store.read(self.db, DFRAME), large)
        self.assertEqual((self.db / "000005.ldb").read_bytes(), table)
        self.assertEqual(ldb_store.put(self.db, DFRAME, b"\x01{}"), sequence + 1)
        self.assertEqual(ldb_store.read(self.db, DFRAME), b"\x01{}")
        self.assertEqual(ldb_store.read(self.db, ORIGIN + b"after-compaction"), b"\x01log-only")

    def test_put_refuses_a_log_that_ends_inside_a_record(self) -> None:
        log = self.db / "000004.log"
        log.write_bytes(log.read_bytes()[:-2])
        with self.assertRaises(LevelDBError):
            ldb_store.put(self.db, DFRAME, b"\x01{}")

    def test_put_refuses_a_database_without_a_live_log(self) -> None:
        (self.db / "000004.log").unlink()
        with self.assertRaises(LevelDBError):
            ldb_store.put(self.db, DFRAME, b"\x01{}")

    def test_a_table_the_manifest_lists_must_exist(self) -> None:
        (self.db / "000005.ldb").unlink()
        with self.assertRaises(LevelDBError):
            ldb_store.read(self.db, DFRAME)

    def test_current_must_name_a_readable_manifest(self) -> None:
        (self.db / "CURRENT").write_text("garbage\n")
        with self.assertRaises(LevelDBError):
            ldb_store.read_version(self.db)
        (self.db / "CURRENT").write_text("MANIFEST-000099\n")
        with self.assertRaises(LevelDBError):
            ldb_store.read_version(self.db)
        (self.db / "CURRENT").unlink()
        with self.assertRaises(LevelDBError):
            ldb_store.read_version(self.db)

    def test_an_unknown_manifest_tag_is_an_error(self) -> None:
        manifest = self.db / "MANIFEST-000002"
        manifest.write_bytes(ldb_log.encode_record(b"\x08\x00", 0))
        with self.assertRaises(LevelDBError):
            ldb_store.read_version(self.db)


if __name__ == "__main__":
    unittest.main()
