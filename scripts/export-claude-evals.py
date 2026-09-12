#!/usr/bin/env python3
"""Export one behavior split to Claude plugin eval's verified bare format."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.anthropic_export import export_suite

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill")
    parser.add_argument("--split", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--section", choices=("behaviors",), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / "evals" / args.skill / "evals.json"
    if not source.is_file():
        parser.error(f"no evaluation suite for {args.skill!r}")
    try:
        manifest = export_suite(source, args.output.resolve(), split=args.split, section=args.section)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"exported {len(manifest['cases'])} {args.split} {args.section} cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
