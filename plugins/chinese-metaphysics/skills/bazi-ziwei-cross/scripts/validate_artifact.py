#!/usr/bin/env python3
"""Validate both charts a cross-reading compares, and that they are one person's.

Two intact charts are not enough here, and this is the one gate where that gap is
invisible: each artifact validates perfectly alone, and a BaZi chart cast for one
moment against a Zi Wei chart placed for another produces a comparison that reads
as authoritative and means nothing. Nothing inside either file can notice, so the
pairing is checked here or nowhere.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.validation import CHART, ZIWEI, ArtifactDefect, pairing_defects, validate

ROUTE_TO = {"bazi": "bazi-chart", "ziwei": "ziwei-chart"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bazi", help="the chinese-metaphysics.bazi-chart artifact .json")
    parser.add_argument("ziwei", help="the chinese-metaphysics.ziwei-chart artifact .json")
    arguments = parser.parse_args(argv)

    charts: dict[str, dict] = {}
    for side, source, kind in (("bazi", arguments.bazi, CHART), ("ziwei", arguments.ziwei, ZIWEI)):
        try:
            envelope = json.loads(Path(source).read_text(encoding="utf-8"))
            if not isinstance(envelope, dict):
                raise ArtifactDefect("expected one JSON object")
            validated = validate(envelope, kind)
        except (ArtifactDefect, json.JSONDecodeError, OSError) as error:
            print(f"error: {side} source: {error}", file=sys.stderr)
            print(f"stop: name this defect and route it back to `{ROUTE_TO[side]}`", file=sys.stderr)
            return 2
        charts[side] = validated

    # Only once both stand on their own: a pairing report over a chart that is
    # already broken names the wrong problem.
    problems = pairing_defects(charts["bazi"], charts["ziwei"])
    if problems:
        print(f"error: {'; '.join(problems)}", file=sys.stderr)
        print("stop: these two charts are not one person at one moment", file=sys.stderr)
        return 2

    print(
        f"valid: {charts['bazi']['input']['name']}, "
        f"bazi checksum {charts['bazi']['checksum']}, "
        f"ziwei checksum {charts['ziwei']['checksum']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
