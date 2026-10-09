#!/usr/bin/env python3
"""Validate a BaZi chart before this reading writes a sentence about it.

A checksum says the file is the one the calculator wrote. A reading needs more
than that: a chart assembled by hand hashes as cleanly as a computed one, and a
missing hour pillar or an empty score ledger reaches prose as a confident
paragraph about evidence that was never there.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.gate import cli_main
from bazi.validation import CHART

ROUTE_TO = "bazi-chart"


def main(argv: list[str] | None = None) -> int:
    return cli_main(
        CHART,
        route_to=ROUTE_TO,
        description=__doc__,
        source_help="the chart artifact .json, or - for a JSON object on stdin",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
