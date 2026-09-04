#!/usr/bin/env python3
"""Validate a BaZi chart before this reading writes a sentence about it.

A checksum says the file is the one the calculator wrote. A reading needs more
than that: a chart assembled by hand hashes as cleanly as a computed one, and a
missing hour pillar or an empty score ledger reaches prose as a confident
paragraph about evidence that was never there.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.validation import CHART, ArtifactDefect, validate

ROUTE_TO = "bazi-chart"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="the chart artifact .json, or - for a JSON object on stdin")
    arguments = parser.parse_args(argv)

    try:
        raw = (
            sys.stdin.read()
            if arguments.source == "-"
            else Path(arguments.source).read_text(encoding="utf-8")
        )
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ArtifactDefect("expected one JSON object")
        validated = validate(envelope, CHART)
    except (ArtifactDefect, json.JSONDecodeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        print(f"stop: name this defect and route the source back to `{ROUTE_TO}`", file=sys.stderr)
        return 2

    print(f"valid: {_subject(validated)}, checksum {validated['checksum']}")
    return 0


def _subject(envelope: dict) -> str:
    return envelope["input"]["name"]


if __name__ == "__main__":
    raise SystemExit(main())
