#!/usr/bin/env python3
"""Compute one canonical natal chart and write JSON plus data-only Markdown."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from astro.ephemeris import EphemerisError, ResolvedChart, resolve_subject, set_ephemeris_path
from astro.request_schema import CalculationOptions, RequestError, Subject, parse_request
from natal_artifact import NatalArtifactError, build_artifact, write_artifact_pair

Resolver = Callable[[Subject, CalculationOptions], ResolvedChart]


# A natal chart is one person. The shared parser describes a pair, because that
# is the shape the plugin already validates to the same standard — historical
# zones, bounded windows, coordinate ranges. Rather than write a second parser
# that would drift from it, one record is presented to it twice and the second
# copy is discarded. The duplicate is an implementation detail and never reaches
# the artifact.
def _as_pair(person: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "people": [
            {"id": "subject", "birth": person},
            {"id": "unused", "birth": person},
        ],
        "options": options,
        "relationship_context": {"description": "unspecified", "requested_domains": []},
    }


DEFAULT_OPTIONS = {
    "language": "en",
    "house_system": "whole-sign",
    "major_orb": 8.0,
    "minor_orb": 3.0,
    "ephemeris_policy": "swiss-only",
    "calculation_profile": "western-tropical-v1",
    "aspect_profile": "ptolemaic-minor-v1",
    "include_derived": False,
    "privacy": "minimal",
}


def main(argv: list[str] | None = None, *, resolver: Resolver = resolve_subject) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", type=Path, help="UTF-8 JSON natal request file")
    source.add_argument("--json", help="inline JSON natal request object")
    parser.add_argument("--out", type=Path, required=True, help="artifact output directory")
    parser.add_argument("--ephemeris-path", help="directory holding Swiss Ephemeris data files")
    arguments = parser.parse_args(argv)

    try:
        raw = arguments.request.read_text(encoding="utf-8") if arguments.request else arguments.json
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RequestError(["request: expected one JSON object"])

        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RequestError(["name: required, and used only as the artifact's display identity"])
        birth = payload.get("birth")
        if not isinstance(birth, dict):
            raise RequestError(["birth: required object describing one birth record"])

        options = DEFAULT_OPTIONS | dict(payload.get("options") or {})
        if arguments.ephemeris_path:
            set_ephemeris_path(arguments.ephemeris_path)

        parsed = parse_request(_as_pair(birth, options))
        chart = resolver(parsed.people[0], parsed.options)
        envelope = build_artifact(
            chart,
            display_name=name.strip(),
            house_system=options["house_system"],
            major_orb=float(options["major_orb"]),
            minor_orb=float(options["minor_orb"]),
        )
        json_path, markdown_path = write_artifact_pair(envelope, arguments.out)
    except (
        EphemerisError,
        NatalArtifactError,
        RequestError,
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
