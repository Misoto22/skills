"""The command line every single-artifact gate runs before a reading or a hand-off.

Six skills each carried the same forty lines: read a path or stdin, refuse a
non-object, validate, and on any defect print it with one stop instruction and
exit 2. The copies differed only in the artifact kind, which skill the stop line
names, and the help text, so those are what a skill's script still declares and
everything else lives here, where one fix reaches every gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .validation import COMPATIBILITY, ArtifactDefect, validate

EXIT_DEFECT = 2


def cli_main(
    kind: str,
    *,
    description: str | None,
    source_help: str,
    hands_off_to: str | None = None,
    route_to: str | None = None,
    argv: list[str] | None = None,
) -> int:
    """Validate one artifact from a path or stdin; return 0 when sound, 2 otherwise.

    A calculator's gate names the skill it `hands_off_to`, which must not run on
    a defective artifact. A reading's gate names the skill to `route_to`, which
    can produce a sound one. Exactly one of the two is required.
    """

    stop = _stop_instruction(hands_off_to, route_to)
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("source", help=source_help)
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
        validated = validate(envelope, kind)
    except (ArtifactDefect, json.JSONDecodeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        print(f"stop: {stop}", file=sys.stderr)
        return EXIT_DEFECT

    print(f"valid: {_subject(validated, kind)}, checksum {validated['checksum']}")
    return 0


def _stop_instruction(hands_off_to: str | None, route_to: str | None) -> str:
    if (hands_off_to is None) == (route_to is None):
        raise ValueError("a gate names exactly one of hands_off_to or route_to")
    if hands_off_to is not None:
        return f"do not invoke `{hands_off_to}` and do not repair the artifact by hand"
    return f"name this defect and route the source back to `{route_to}`"


def _subject(envelope: Mapping[str, Any], kind: str) -> str:
    if kind == COMPATIBILITY:
        return f"{envelope['people']['left']['name']} and {envelope['people']['right']['name']}"
    return envelope["input"]["name"]
