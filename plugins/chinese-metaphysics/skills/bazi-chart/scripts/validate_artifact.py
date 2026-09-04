#!/usr/bin/env python3
"""Verify the chart this run just wrote before handing it to `bazi-reading`.

The hand-off is automatic, so nobody looks at the file in between. What the
calculator printed is read back off disk here — the envelope it claims to be,
and every pillar, ledger and score the reading is about to cite.
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

HANDS_OFF_TO = "bazi-reading"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", help="the chart artifact this run just wrote, or - for a JSON object on stdin"
    )
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
        print(
            f"stop: do not invoke `{HANDS_OFF_TO}` and do not repair the artifact by hand",
            file=sys.stderr,
        )
        return 2

    print(f"valid: {_subject(validated)}, checksum {validated['checksum']}")
    return 0


def _subject(envelope: dict) -> str:
    return envelope["input"]["name"]


if __name__ == "__main__":
    raise SystemExit(main())
