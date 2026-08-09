#!/usr/bin/env python3
"""Compare two chart or raw-birth sources and write compatibility artifacts."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from bazi.artifacts import ArtifactError, validate_envelope, write_artifact_pair
from bazi.calendar import CalendarError
from bazi.compatibility import CompatibilityError, compare_charts
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
    source.add_argument("--request", type=Path, help="UTF-8 JSON comparison request")
    source.add_argument("--json", help="inline JSON comparison request")
    parser.add_argument("--out", type=Path, required=True, help="artifact output directory")
    parser.add_argument(
        "--relationship-type",
        choices=("romance", "marriage", "friendship", "family", "work"),
    )
    parser.add_argument("--ephemeris-path", help="optional Swiss Ephemeris data directory")
    args = parser.parse_args(argv)

    ephemeris = None

    def get_ephemeris():
        nonlocal ephemeris
        if ephemeris is None:
            ephemeris = ephemeris_factory(args.ephemeris_path)
        return ephemeris

    try:
        raw = args.request.read_text(encoding="utf-8") if args.request else args.json
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise CompatibilityError("request must be one JSON object")
        left = _load_source(payload.get("left"), get_ephemeris)
        right = _load_source(payload.get("right"), get_ephemeris)
        relationship_type = args.relationship_type or payload.get("relationship_type")
        envelope = compare_charts(left, right, relationship_type)
        json_path, markdown_path = write_artifact_pair(envelope, args.out, kind="compatibility")
    except (
        ArtifactError,
        BirthDataError,
        CalendarError,
        CompatibilityError,
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


def _load_source(source: Any, get_ephemeris: Callable[[], Any]) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise CompatibilityError("left and right must each be a chart or birth source object")
    if "chart_path" in source:
        path = Path(str(source["chart_path"]))
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise CompatibilityError(f"chart source {path} is not a JSON object")
        return validate_envelope(payload)
    if "birth" in source:
        birth = source["birth"]
        if not isinstance(birth, dict):
            raise CompatibilityError("birth source must be a JSON object")
        return build_chart(birth, get_ephemeris())
    if source.get("schema") == "chinese-metaphysics.bazi-chart":
        return validate_envelope(source)
    return build_chart(dict(source), get_ephemeris())


if __name__ == "__main__":
    raise SystemExit(main())
