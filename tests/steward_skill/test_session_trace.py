"""The session record every inventory source reduces to, as the report prints it."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "dev" / "skills" / "steward" / "scripts"))

from session_trace import Session, iso


class SessionTraceTests(unittest.TestCase):
    def test_the_json_carries_every_field_the_report_reads(self) -> None:
        session = Session("claude-desktop", "s1", "/w", 0.0, open=True)

        self.assertEqual(
            session.as_json(),
            {
                "client": "claude-desktop",
                "id": "s1",
                "cwd": "/w",
                "last_activity": iso(0.0),
                "live": False,
                "kind": None,
                "open": True,
            },
        )

    def test_timestamps_print_in_local_time_with_their_offset(self) -> None:
        self.assertEqual(iso(0.0), time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(0.0)))
        self.assertRegex(iso(time.time()), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}$")


if __name__ == "__main__":
    unittest.main()
