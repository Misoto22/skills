#!/usr/bin/env python3
"""Validate a natal chart artifact and emit the evidence ledger a reading cites.

The reading skill's whole discipline rests on the artifact being what it claims.
This runs before a single sentence is written: a mismatched checksum, a body with
no house, or an aspect naming something absent all stop here, where the defect
can be named, rather than in prose where it cannot.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "shared"))

from astro.natal_envelope import SCHEMA, SCHEMA_VERSION, NatalEnvelopeError, validate_envelope


class ValidationError(ValueError):
    """The artifact cannot be read as a natal chart."""


def validate(envelope: dict[str, Any]) -> list[str]:
    """Return every independent defect, so one run reports the whole picture."""

    problems: list[str] = []
    if envelope.get("schema") != SCHEMA:
        problems.append(f"schema: expected {SCHEMA!r}, got {envelope.get('schema')!r}")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version: expected {SCHEMA_VERSION}, got {envelope.get('schema_version')!r}")

    cusps = (envelope.get("houses") or {}).get("cusps")
    if not isinstance(cusps, list) or len(cusps) != 12:
        problems.append("houses.cusps: a natal chart has twelve house cusps")

    angles = {angle.get("name") for angle in envelope.get("angles") or []}
    for required in ("ascendant", "medium_coeli"):
        if required not in angles:
            problems.append(f"angles: {required} is required for a natal reading")

    bodies: set[str] = set()
    for index, position in enumerate(envelope.get("positions") or []):
        bodies.add(str(position.get("body")))
        for field in ("body", "sign", "house", "retrograde", "critical_degree", "dignities"):
            if field not in position:
                problems.append(f"positions[{index}].{field}: required")
    if not bodies:
        problems.append("positions: a chart with no bodies is not a chart")

    seen: set[tuple[str, str]] = set()
    for index, aspect in enumerate(envelope.get("aspects") or []):
        left, right = str(aspect.get("left")), str(aspect.get("right"))
        if left == right:
            problems.append(f"aspects[{index}]: {left} aspects itself")
        for side in (left, right):
            if side not in bodies:
                problems.append(f"aspects[{index}]: names {side!r}, which has no position")
        pair = (*sorted((left, right)), str(aspect.get("kind")))
        if pair in seen:
            problems.append(f"aspects[{index}]: {left}-{right} recorded twice")
        seen.add(pair)
        if not isinstance(aspect.get("orb"), (int, float)):
            problems.append(f"aspects[{index}].orb: required, and a reading weights by it")

    sect = envelope.get("sect") or {}
    if "diurnal" not in sect or not str(sect.get("basis") or "").strip():
        problems.append("sect: a reading states the sect and the basis it rests on")

    lots = envelope.get("lots")
    if lots is None or not isinstance(lots, list):
        problems.append("lots: expected a list, empty when a required body was unavailable")

    if "limitations" not in envelope:
        problems.append("limitations: required, empty when nothing was unavailable")

    return problems


def ledger(envelope: dict[str, Any]) -> dict[str, Any]:
    """Build the id-keyed evidence a reading is allowed to cite."""

    return {
        "source_checksum": envelope["checksum"],
        "backend": (envelope.get("provenance") or {}).get("actual_backend"),
        "evidence": {
            **{f"[B-{p['body']}]": p for p in envelope.get("positions") or []},
            **{f"[A-{a['name']}]": a for a in envelope.get("angles") or []},
            **{f"[X-{a['left']}-{a['kind']}-{a['right']}]": a for a in envelope.get("aspects") or []},
            **{f"[L-{lot['name']}]": lot for lot in envelope.get("lots") or []},
            "[S-sect]": envelope.get("sect"),
            **{f"[LIM-{item['code']}]": item for item in envelope.get("limitations") or []},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="natal artifact .json, or - for a JSON object on stdin")
    parser.add_argument("--out", type=Path, help="write the evidence ledger to this JSON path")
    arguments = parser.parse_args(argv)

    try:
        raw = (
            sys.stdin.read()
            if arguments.source == "-"
            else Path(arguments.source).read_text(encoding="utf-8")
        )
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ValidationError("expected one JSON object")

        problems = validate(envelope)
        if problems:
            raise ValidationError("; ".join(problems))

        # Checksum last: a structural defect is more useful to report than a hash.
        try:
            validate_envelope(envelope)
        except NatalEnvelopeError as error:
            raise ValidationError(str(error)) from error

        built = ledger(envelope)
    except (ValidationError, json.JSONDecodeError, OSError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if arguments.out:
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(
            json.dumps(built, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        print(arguments.out.resolve())
    else:
        print(f"valid: {len(built['evidence'])} evidence entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
