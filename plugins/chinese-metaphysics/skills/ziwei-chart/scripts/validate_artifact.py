#!/usr/bin/env python3
"""Verify the chart this run just placed before handing it to `ziwei-reading`.

The hand-off is automatic, so nobody looks at the file in between. Twelve
palaces, one life palace and one body palace, every transformation landing on a star
that is actually placed, and twelve decade ranges running one way are checked here.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.gate import cli_main
from bazi.validation import ZIWEI

HANDS_OFF_TO = "ziwei-reading"


def main(argv: list[str] | None = None) -> int:
    return cli_main(
        ZIWEI,
        hands_off_to=HANDS_OFF_TO,
        description=__doc__,
        source_help="the Zi Wei artifact this run just placed, or - for a JSON object on stdin",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
