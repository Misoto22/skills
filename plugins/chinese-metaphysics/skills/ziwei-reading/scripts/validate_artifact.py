#!/usr/bin/env python3
"""Validate a Zi Wei chart before this reading interprets a single palace.

Eleven palaces, two life palaces, a 化忌 landing on a star that sits nowhere,
decade ranges that reverse halfway: each of those hashes perfectly, and each
becomes a paragraph about structure the chart does not have.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.gate import cli_main
from bazi.validation import ZIWEI

ROUTE_TO = "ziwei-chart"


def main(argv: list[str] | None = None) -> int:
    return cli_main(
        ZIWEI,
        route_to=ROUTE_TO,
        description=__doc__,
        source_help="the Zi Wei artifact .json, or - for a JSON object on stdin",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
