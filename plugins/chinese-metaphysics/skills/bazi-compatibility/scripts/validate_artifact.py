#!/usr/bin/env python3
"""Verify the comparison this run just wrote before the reading is invoked.

The hand-off is automatic, so this is the last point anything looks at the
artifact: the five weights, the arithmetic that produced the displayed score,
and the sensitivity range that score has to sit inside.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.gate import cli_main
from bazi.validation import COMPATIBILITY

HANDS_OFF_TO = "bazi-compatibility-reading"


def main(argv: list[str] | None = None) -> int:
    return cli_main(
        COMPATIBILITY,
        hands_off_to=HANDS_OFF_TO,
        description=__doc__,
        source_help="the comparison artifact this run just wrote, or - for a JSON object on stdin",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
