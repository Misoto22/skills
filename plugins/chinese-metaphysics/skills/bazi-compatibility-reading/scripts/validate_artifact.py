#!/usr/bin/env python3
"""Validate a comparison before this reading interprets a single score.

The defects that matter here are arithmetic, and they are exactly the ones a
reader cannot see: five weights that no longer sum to a hundred, a general score
its own dimensions do not produce, a contextual score with no profile to audit
it against. Each survives a checksum, and each makes the report wrong.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.gate import cli_main
from bazi.validation import COMPATIBILITY

ROUTE_TO = "bazi-compatibility"


def main(argv: list[str] | None = None) -> int:
    return cli_main(
        COMPATIBILITY,
        route_to=ROUTE_TO,
        description=__doc__,
        source_help="the compatibility artifact .json, or - for a JSON object on stdin",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
