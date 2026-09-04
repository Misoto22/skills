#!/usr/bin/env python3
"""Validate a comparison before this reading interprets a single score.

The defects that matter here are arithmetic, and they are exactly the ones a
reader cannot see: five weights that no longer sum to a hundred, a general score
its own dimensions do not produce, a contextual score with no profile to audit
it against. Each survives a checksum, and each makes the report wrong.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.validation import COMPATIBILITY, ArtifactDefect, validate

ROUTE_TO = "bazi-compatibility"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="the compatibility artifact .json, or - for a JSON object on stdin")
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
        validated = validate(envelope, COMPATIBILITY)
    except (ArtifactDefect, json.JSONDecodeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        print(f"stop: name this defect and route the source back to `{ROUTE_TO}`", file=sys.stderr)
        return 2

    print(f"valid: {_subject(validated)}, checksum {validated['checksum']}")
    return 0


def _subject(envelope: dict) -> str:
    return f"{envelope['people']['left']['name']} and {envelope['people']['right']['name']}"


if __name__ == "__main__":
    raise SystemExit(main())
