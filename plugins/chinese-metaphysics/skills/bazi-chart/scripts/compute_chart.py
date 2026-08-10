#!/usr/bin/env python3
"""Calculate one BaZi chart and write canonical JSON plus data-only Markdown."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.artifacts import ArtifactError, write_artifact_pair
from bazi.calendar import CalendarError
from bazi.engine import build_chart
from bazi.ephemeris import EphemerisUnavailable, SwissEphemeris
from bazi.models import BirthDataError


def main(
    argv: list[str] | None = None,
    *,
    ephemeris_factory: Callable[[str | None], Any] = SwissEphemeris,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", type=Path, help="UTF-8 JSON request file")
    source.add_argument("--json", help="inline JSON request object")
    parser.add_argument("--out", type=Path, required=True, help="artifact output directory")
    parser.add_argument("--language", choices=("en", "zh"), default="zh")
    parser.add_argument("--ephemeris-path", help="optional Swiss Ephemeris data directory")
    args = parser.parse_args(argv)

    try:
        raw = args.request.read_text(encoding="utf-8") if args.request else args.json
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise BirthDataError(["request: expected one JSON object"])
        ephemeris = ephemeris_factory(args.ephemeris_path)
        envelope = build_chart(payload, ephemeris)
        json_path, markdown_path = write_artifact_pair(envelope, args.out, kind="chart")
    except (
        ArtifactError,
        BirthDataError,
        CalendarError,
        EphemerisUnavailable,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
