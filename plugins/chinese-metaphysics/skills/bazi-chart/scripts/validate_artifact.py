#!/usr/bin/env python3
"""Verify the chart this run just wrote before handing it to `bazi-reading`.

The hand-off is automatic, so nobody looks at the file in between. What the
calculator printed is read back off disk here — the envelope it claims to be,
and every pillar, ledger and score the reading is about to cite.
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.gate import cli_main
from bazi.validation import CHART

HANDS_OFF_TO = "bazi-reading"


def main(argv: list[str] | None = None) -> int:
    return cli_main(
        CHART,
        hands_off_to=HANDS_OFF_TO,
        description=__doc__,
        source_help="the chart artifact this run just wrote, or - for a JSON object on stdin",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
