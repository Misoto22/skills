from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
HELPER = SKILL / "scripts" / "reading_session.py"
FIXTURE = Path(__file__).parent / "fixtures" / "neutral.json"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

from synastry_schema import attach_integrity  # type: ignore[import-not-found]
from validate_synastry import load_ledger  # type: ignore[import-not-found]

UNIVERSAL_HEADINGS = (
    "Basis, provenance, and limitations",
    "Repeated interaction patterns",
    "Reciprocity and asymmetry",
    "Communication and coordination",
    "Tension, boundaries, and repair",
    "Growth and shared direction",
    "Requested or context-specific domains",
    "Overall synthesis",
    "Evidence index",
)


def source_with(*, label: str = "private-display-name", warning_size: int = 0) -> dict[str, object]:
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source["subjects"][0]["display_name"] = label
    if warning_size:
        source["provenance"]["warnings"] = ["x" * warning_size]
    return attach_integrity(source)


def valid_report(source: dict[str, object]) -> str:
    evidence = load_ledger(source).evidence[0].citation
    lines = ["# Synastry reading"]
    for heading in UNIVERSAL_HEADINGS:
        lines.extend((f"## {heading}", evidence))
    return "\n\n".join(lines) + "\n"


def ledger_bytes(status: dict[str, object]) -> bytes:
    pages = Path(str(status["pages_path"]))
    return b"".join((pages / f"{index:06d}.part").read_bytes() for index in range(int(status["page_count"])))


class ReadingSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.session_root = self.directory / "sessions"
        self.environment = os.environ | {
            "SYNASTRY_READING_SESSION_ROOT": str(self.session_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_helper(
        self, arguments: list[str], *, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HELPER), *arguments],
            cwd=SKILL,
            env=self.environment,
            input=input_text,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )

    def start_pasted(
        self, source: dict[str, object], *, ttl_seconds: int = 60
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = self.run_helper(
            ["start", "-", "--ttl-seconds", str(ttl_seconds)],
            input_text=json.dumps(source),
        )
        status = json.loads(completed.stdout) if completed.stdout else {}
        return completed, status

    def test_large_ledger_is_private_complete_and_page_readable(self) -> None:
        secret = "private-display-name"
        completed, status = self.start_pasted(source_with(label=secret, warning_size=220_000))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertLess(len(completed.stdout.encode("utf-8")), 1024)
        self.assertNotIn(secret, completed.stdout + completed.stderr)
        self.assertIn("pages_path", status)
        pages_path = Path(str(status["pages_path"]))
        self.assertGreater(int(status["ledger_bytes"]), 200_000)
        self.assertLessEqual(int(status["page_bytes"]), 65_536)
        self.assertGreater(int(status["page_bytes"]), 0)
        self.assertNotIn("ledger_path", status)
        self.assertEqual(stat.S_IMODE(pages_path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(pages_path.stat().st_mode), 0o700)
        page_files = sorted(pages_path.iterdir())
        self.assertEqual(len(page_files), int(status["page_count"]))
        for page in page_files:
            self.assertEqual(stat.S_IMODE(page.stat().st_mode), 0o600)
            self.assertLessEqual(page.stat().st_size, int(status["page_bytes"]))
            page.read_text(encoding="utf-8")
        for artifact in pages_path.parent.iterdir():
            if artifact.is_file():
                self.assertEqual(stat.S_IMODE(artifact.stat().st_mode), 0o600)

        reconstructed = ledger_bytes(status)

        self.assertEqual(len(reconstructed), int(status["ledger_bytes"]))
        ledger = json.loads(reconstructed)
        self.assertEqual(ledger["chart_id"], "abc123def456")
        self.assertEqual(ledger["subjects"], [{"id": "subject-a"}, {"id": "subject-b"}])
        self.assertNotIn("display_name", reconstructed.decode("utf-8"))
        self.assertNotIn("source_path", reconstructed.decode("utf-8"))

    def test_unbounded_session_lifetime_is_rejected_without_artifacts(self) -> None:
        rejected, _ = self.start_pasted(source_with(), ttl_seconds=3_601)

        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(rejected.stdout, "")
        self.assertEqual(rejected.stderr, "error: session operation failed\n")
        self.assertFalse(self.session_root.exists())

    def test_attached_and_pasted_status_never_echoes_source_or_display_name(self) -> None:
        secret = "private-display-name"
        source = source_with(label=secret)
        attached = self.directory / "private-source-path.json"
        attached.write_text(json.dumps(source), encoding="utf-8")

        attached_result = self.run_helper(["start", str(attached)])
        pasted_result, _ = self.start_pasted(source)

        self.assertEqual((attached_result.returncode, pasted_result.returncode), (0, 0))
        combined = (
            attached_result.stdout + attached_result.stderr + pasted_result.stdout + pasted_result.stderr
        )
        self.assertNotIn(secret, combined)
        self.assertNotIn(str(attached), combined)
        for payload in (json.loads(attached_result.stdout), json.loads(pasted_result.stdout)):
            self.assertRegex(str(payload["token"]), r"\A[0-9a-f]{32}\Z")
            self.assertEqual(Path(str(payload["pages_path"])).name, "ledger-pages")

    def test_watchdog_expires_an_interrupted_session(self) -> None:
        completed, status = self.start_pasted(source_with(), ttl_seconds=1)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        pages_path = Path(str(status["pages_path"]))
        deadline = time.monotonic() + 5

        while pages_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)

        self.assertFalse(pages_path.exists())
        self.assertFalse(pages_path.parent.exists())

    def test_invalid_finalization_cleans_and_retry_uses_a_fresh_session(self) -> None:
        source = source_with()
        first, first_status = self.start_pasted(source)
        destination = self.directory / "synastry_reading_abc123def456.md"
        self.assertEqual(first.returncode, 0, first.stderr)

        failed = self.run_helper(
            ["finalize", str(first_status["token"]), "--out", str(destination)],
            input_text="# Invalid",
        )

        self.assertEqual(failed.returncode, 2)
        self.assertEqual(failed.stdout, "")
        self.assertEqual(failed.stderr, "error: session operation failed\n")
        self.assertFalse(Path(str(first_status["pages_path"])).parent.exists())
        self.assertFalse(destination.exists())

        second, second_status = self.start_pasted(source)
        self.assertEqual(second.returncode, 0, second.stderr)
        succeeded = self.run_helper(
            ["finalize", str(second_status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertNotEqual(first_status["token"], second_status["token"])
        self.assertEqual(succeeded.returncode, 0, succeeded.stderr)
        self.assertTrue(destination.is_file())
        self.assertFalse(Path(str(second_status["pages_path"])).parent.exists())
        self.assertEqual(list(self.session_root.glob("*")) if self.session_root.exists() else [], [])
        self.assertEqual(list(self.directory.iterdir()), [destination])

    def test_attached_source_is_revalidated_and_success_leaves_only_final_markdown(self) -> None:
        source = source_with()
        attached = self.directory / "source.json"
        attached.write_text(json.dumps(source), encoding="utf-8")
        started = self.run_helper(["start", str(attached)])
        self.assertEqual(started.returncode, 0, started.stderr)
        status = json.loads(started.stdout)
        destination = self.directory / "synastry_reading_abc123def456.md"

        finalized = self.run_helper(
            ["finalize", str(status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        self.assertEqual(json.loads(finalized.stdout), {"status": "complete"})
        self.assertTrue(destination.is_file())
        self.assertFalse(Path(str(status["pages_path"])).parent.exists())
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)

    def test_changed_attached_source_fails_closed_and_cleans_session(self) -> None:
        source = source_with()
        attached = self.directory / "source.json"
        attached.write_text(json.dumps(source), encoding="utf-8")
        started = self.run_helper(["start", str(attached)])
        self.assertEqual(started.returncode, 0, started.stderr)
        status = json.loads(started.stdout)
        changed = source_with(label="changed-private-name")
        attached.write_text(json.dumps(changed), encoding="utf-8")
        destination = self.directory / "synastry_reading_abc123def456.md"

        finalized = self.run_helper(
            ["finalize", str(status["token"]), "--out", str(destination)],
            input_text=valid_report(source),
        )

        self.assertEqual(finalized.returncode, 2)
        self.assertFalse(destination.exists())
        self.assertFalse(Path(str(status["pages_path"])).parent.exists())
        self.assertNotIn("changed-private-name", finalized.stdout + finalized.stderr)


if __name__ == "__main__":
    unittest.main()
