from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry"
sys.path.insert(0, str(SKILL / "scripts"))

from request_schema import RequestError, parse_request


class RequestBoundaryTests(unittest.TestCase):
    def test_legacy_flat_person_records_are_not_a_v2_request(self) -> None:
        legacy = {
            "people": [
                {"name": "Alex", "date": "1990-03-14", "time": "07:42"},
                {"name": "Morgan", "date": "1992-06-08", "time": "12:15"},
            ]
        }

        with self.assertRaises(RequestError):
            parse_request(legacy)


if __name__ == "__main__":
    unittest.main()
