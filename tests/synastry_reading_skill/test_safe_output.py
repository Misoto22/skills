"""Direct tests of the synastry-reading file-safety helpers.

The validators and the reading session reach these through their own CLIs, and
those suites cover the races. These pin the contract each caller relies on: an
atomic install, an existing file never overwritten unless asked, the durability
flush, and the platform exchange primitive on each OS that has one.
"""

from __future__ import annotations

import errno
import io
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
sys.path.insert(0, str(SKILL / "scripts"))

import file_identity  # type: ignore[import-not-found]
import safe_output  # type: ignore[import-not-found]


class _Operation:
    """Stand-in for a ctypes foreign function: records its call, returns a fixed result."""

    def __init__(self, result: int = 0) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []
        self.argtypes: list[object] = []
        self.restype: object = None

    def __call__(self, *arguments: object) -> int:
        self.calls.append(arguments)
        return self.result


class _Library:
    def __init__(self, **operations: _Operation) -> None:
        for name, operation in operations.items():
            setattr(self, name, operation)


def _identity(path: Path) -> tuple[int, int]:
    status = os.lstat(path)
    return status.st_dev, status.st_ino


def _exchange_supported() -> bool:
    return sys.platform == "darwin" or sys.platform.startswith("linux")


class SafeOutputTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary.name)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def leftovers(self) -> list[str]:
        return sorted(path.name for path in self.directory.iterdir() if path.name.startswith("."))


class AtomicInstallTests(SafeOutputTestCase):
    def test_a_new_destination_receives_exactly_the_payload_as_a_private_file(self) -> None:
        destination = self.directory / "nested" / "ledger.json"

        result = safe_output.write_atomic_bytes(
            b"payload\n", destination, overwrite=False, temporary_prefix="probe"
        )

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes(), b"payload\n")
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertEqual(sorted(path.name for path in destination.parent.iterdir()), ["ledger.json"])

    def test_an_existing_mismatching_file_is_never_overwritten_without_permission(self) -> None:
        destination = self.directory / "ledger.json"
        destination.write_bytes(b"previous\n")
        before = _identity(destination)

        with self.assertRaises(safe_output.OutputExistsError):
            safe_output.write_atomic_bytes(b"new\n", destination, overwrite=False, temporary_prefix="probe")

        self.assertEqual(destination.read_bytes(), b"previous\n")
        self.assertEqual(_identity(destination), before)
        self.assertEqual(self.leftovers(), [])

    def test_accept_identical_returns_an_existing_private_copy_and_refuses_a_different_one(self) -> None:
        destination = self.directory / "reading.md"
        destination.write_bytes(b"same\n")
        destination.chmod(0o600)

        result = safe_output.write_atomic_bytes(
            b"same\n", destination, overwrite=False, temporary_prefix="probe", accept_identical=True
        )
        self.assertEqual(result, destination)

        with self.assertRaises(safe_output.OutputExistsError):
            safe_output.write_atomic_bytes(
                b"other\n", destination, overwrite=False, temporary_prefix="probe", accept_identical=True
            )
        self.assertEqual(destination.read_bytes(), b"same\n")
        self.assertEqual(self.leftovers(), [])

    def test_a_forbidden_identity_is_never_replaced_even_with_overwrite(self) -> None:
        source = self.directory / "source.json"
        source.write_bytes(b"source\n")
        destination = self.directory / "alias.json"
        destination.hardlink_to(source)

        for overwrite in (False, True):
            with self.subTest(overwrite=overwrite), self.assertRaises(safe_output.SourceIdentityError):
                safe_output.write_atomic_bytes(
                    b"new\n",
                    destination,
                    overwrite=overwrite,
                    temporary_prefix="probe",
                    forbidden_identity=_identity(source),
                )

        self.assertEqual(source.read_bytes(), b"source\n")
        self.assertTrue(destination.samefile(source))
        self.assertEqual(self.leftovers(), [])

    @unittest.skipUnless(_exchange_supported(), "atomic overwrite needs renameatx_np or renameat2")
    def test_overwrite_replaces_an_existing_file_atomically(self) -> None:
        destination = self.directory / "ledger.json"
        destination.write_bytes(b"previous\n")

        safe_output.write_atomic_bytes(
            b"replacement\n", destination, overwrite=True, temporary_prefix="probe"
        )

        self.assertEqual(destination.read_bytes(), b"replacement\n")
        self.assertEqual(self.leftovers(), [])

    def test_overwrite_without_an_exchange_primitive_leaves_the_destination_alone(self) -> None:
        destination = self.directory / "ledger.json"
        destination.write_bytes(b"previous\n")

        with patch.object(safe_output.sys, "platform", "plan9"), self.assertRaises(OSError) as raised:
            safe_output.write_atomic_bytes(b"new\n", destination, overwrite=True, temporary_prefix="probe")

        self.assertEqual(raised.exception.errno, errno.ENOTSUP)
        self.assertEqual(destination.read_bytes(), b"previous\n")
        self.assertEqual(self.leftovers(), [])


class ExistingFileTests(SafeOutputTestCase):
    def test_it_compares_bytes_of_a_private_regular_file(self) -> None:
        destination = self.directory / "reading.md"
        destination.write_bytes(b"bytes\n")
        destination.chmod(0o600)

        self.assertTrue(
            safe_output.existing_regular_file_matches(destination, b"bytes\n", forbidden_identity=None)
        )
        self.assertFalse(
            safe_output.existing_regular_file_matches(destination, b"other\n", forbidden_identity=None)
        )

    def test_a_readable_copy_with_loose_permissions_does_not_count_as_a_match(self) -> None:
        destination = self.directory / "reading.md"
        destination.write_bytes(b"bytes\n")
        destination.chmod(0o644)

        self.assertFalse(
            safe_output.existing_regular_file_matches(destination, b"bytes\n", forbidden_identity=None)
        )

    def test_a_symlink_or_the_forbidden_file_is_refused(self) -> None:
        target = self.directory / "target.md"
        target.write_bytes(b"bytes\n")
        target.chmod(0o600)
        link = self.directory / "link.md"
        link.symlink_to(target)

        with self.assertRaises(OSError):
            safe_output.existing_regular_file_matches(link, b"bytes\n", forbidden_identity=None)
        with self.assertRaises(safe_output.SourceIdentityError):
            safe_output.existing_regular_file_matches(
                target, b"bytes\n", forbidden_identity=_identity(target)
            )

    def test_a_missing_file_is_no_match_only_for_the_post_publication_check(self) -> None:
        missing = self.directory / "missing.md"

        with self.assertRaises(FileNotFoundError):
            safe_output.existing_regular_file_matches(missing, b"x", forbidden_identity=None)
        self.assertFalse(file_identity.published_output_matches(missing, b"x", forbidden_identity=None))

    def test_identity_is_read_from_regular_files_only(self) -> None:
        regular = self.directory / "regular"
        regular.write_bytes(b"")
        link = self.directory / "link"
        link.symlink_to(regular)

        self.assertEqual(safe_output.path_identity(regular), _identity(regular))
        self.assertIsNone(safe_output.path_identity(self.directory / "absent"))
        with self.assertRaises(OSError):
            safe_output.path_identity(link)
        self.assertTrue(safe_output.matches_identity(regular, _identity(regular)))
        self.assertFalse(safe_output.matches_identity(regular, None))
        self.assertFalse(safe_output.matches_identity(self.directory / "absent", _identity(regular)))


class FsyncDirectoryTests(SafeOutputTestCase):
    def test_it_flushes_one_descriptor_on_the_directory_and_closes_it(self) -> None:
        flushed: list[int] = []
        original_fsync = os.fsync

        def record(descriptor: int) -> None:
            flushed.append(descriptor)
            self.assertTrue(stat.S_ISDIR(os.fstat(descriptor).st_mode))
            original_fsync(descriptor)

        with patch.object(safe_output.os, "fsync", record):
            safe_output.fsync_directory(self.directory)

        self.assertEqual(len(flushed), 1)
        with self.assertRaises(OSError) as closed:
            os.fstat(flushed[0])
        self.assertEqual(closed.exception.errno, errno.EBADF)

    def test_the_descriptor_is_closed_when_the_flush_fails(self) -> None:
        opened: list[int] = []
        original_open = os.open

        def record_open(path: object, flags: int, *arguments: object) -> int:
            descriptor = original_open(path, flags, *arguments)  # type: ignore[arg-type]
            opened.append(descriptor)
            return descriptor

        with (
            patch.object(safe_output.os, "open", record_open),
            patch.object(safe_output.os, "fsync", side_effect=OSError(errno.EIO, "injected")),
            self.assertRaises(OSError),
        ):
            safe_output.fsync_directory(self.directory)

        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0])

    def test_a_missing_directory_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            safe_output.fsync_directory(self.directory / "absent")


class ExchangePathsTests(SafeOutputTestCase):
    def make_pair(self) -> tuple[Path, Path]:
        first = self.directory / "first"
        second = self.directory / "second"
        first.write_bytes(b"first\n")
        second.write_bytes(b"second\n")
        return first, second

    @unittest.skipUnless(sys.platform == "darwin", "renameatx_np exists only on darwin")
    def test_darwin_exchanges_two_entries_in_place(self) -> None:
        first, second = self.make_pair()

        safe_output.exchange_paths(first, second)

        self.assertEqual((first.read_bytes(), second.read_bytes()), (b"second\n", b"first\n"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "renameat2 exists only on linux")
    def test_linux_exchanges_two_entries_in_place(self) -> None:
        first, second = self.make_pair()

        try:
            safe_output.exchange_paths(first, second)
        except OSError as error:
            if error.errno in (errno.ENOTSUP, errno.EINVAL, errno.ENOSYS):
                self.skipTest(f"this libc or filesystem has no RENAME_EXCHANGE: {error}")
            raise

        self.assertEqual((first.read_bytes(), second.read_bytes()), (b"second\n", b"first\n"))

    def test_each_platform_calls_its_primitive_with_the_exchange_flag(self) -> None:
        cases = (
            ("darwin", "renameatx_np", -2),
            ("linux", "renameat2", -100),
        )
        for platform, name, current_directory in cases:
            with self.subTest(platform=platform):
                operation = _Operation()
                with (
                    patch.object(safe_output.sys, "platform", platform),
                    patch.object(safe_output.ctypes, "CDLL", return_value=_Library(**{name: operation})),
                ):
                    safe_output.exchange_paths(Path("a"), Path("b"))

                self.assertEqual(operation.calls, [(current_directory, b"a", current_directory, b"b", 2)])

    def test_a_failed_exchange_raises_the_os_error(self) -> None:
        with (
            patch.object(safe_output.sys, "platform", "linux"),
            patch.object(safe_output.ctypes, "CDLL", return_value=_Library(renameat2=_Operation(result=-1))),
            patch.object(safe_output.ctypes, "get_errno", return_value=errno.EXDEV),
            self.assertRaises(OSError) as raised,
        ):
            safe_output.exchange_paths(Path("a"), Path("b"))

        self.assertEqual(raised.exception.errno, errno.EXDEV)

    def test_a_platform_or_libc_without_the_primitive_is_refused(self) -> None:
        cases = (("plan9", _Library()), ("darwin", _Library()), ("linux", _Library()))
        for platform, library in cases:
            with (
                self.subTest(platform=platform),
                patch.object(safe_output.sys, "platform", platform),
                patch.object(safe_output.ctypes, "CDLL", return_value=library),
                self.assertRaises(OSError) as raised,
            ):
                safe_output.exchange_paths(Path("a"), Path("b"))
            self.assertEqual(raised.exception.errno, errno.ENOTSUP)


class StdoutTests(unittest.TestCase):
    def test_a_failed_write_quarantines_stdout_and_reports_false(self) -> None:
        class BrokenPipe(io.StringIO):
            def write(self, text: str) -> int:
                raise BrokenPipeError(errno.EPIPE, "closed")

        with (
            patch.object(safe_output.sys, "stdout", BrokenPipe()),
            patch.object(safe_output, "quarantine_stdout") as quarantine,
        ):
            self.assertFalse(safe_output.write_stdout(b"payload\n"))
        quarantine.assert_called_once_with()

    def test_a_successful_write_reports_true(self) -> None:
        captured = io.StringIO()

        with patch.object(safe_output.sys, "stdout", captured):
            self.assertTrue(safe_output.write_stdout(b"payload\n"))
        self.assertEqual(captured.getvalue(), "payload\n")


if __name__ == "__main__":
    unittest.main()
