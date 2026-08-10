#!/usr/bin/env python3
"""Compute and atomically write one canonical synastry v2 JSON artifact."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact import ArtifactExistsError, build_artifact, write_artifact
from ephemeris import EphemerisError, ResolvedChart, resolve_subject, set_ephemeris_path
from request_schema import CalculationOptions, RequestError, Subject, parse_request
from synastry_schema import SchemaError

Resolver = Callable[[Subject, CalculationOptions], ResolvedChart]


class _LegacyTxtError(ValueError):
    """A legacy text path was supplied where v2 JSON is required."""


def main(argv: list[str] | None = None, resolver: Resolver = resolve_subject) -> int:
    """Run the JSON-only calculator and return a process exit code."""

    parser = argparse.ArgumentParser(description="Compute a canonical synastry v2 JSON artifact.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", help="path to a v2 JSON request; '-' reads standard input")
    source.add_argument("--json", help="the v2 JSON request inline")
    parser.add_argument("--out", default=".", help="directory to write the artifact into")
    parser.add_argument(
        "--ephemeris-path",
        help="directory holding Swiss Ephemeris data files; omitted resets the binding default",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="atomically replace the deterministic output path if it already exists",
    )
    arguments = parser.parse_args(argv)

    try:
        request = parse_request(_load_payload(arguments))
        set_ephemeris_path(arguments.ephemeris_path)
        charts = tuple(resolver(subject, request.options) for subject in request.people)
        document = build_artifact(request, charts)
        written = write_artifact(document, arguments.out, overwrite=arguments.overwrite)
    except _LegacyTxtError:
        print("error: legacy TXT input is not supported; provide a synastry v2 JSON request", file=sys.stderr)
        return 2
    except RequestError:
        print("error: invalid synastry v2 request", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, UnicodeError):
        print("error: request is not valid UTF-8 JSON", file=sys.stderr)
        return 2
    except EphemerisError as error:
        print(f"error: {_safe_ephemeris_message(error)}", file=sys.stderr)
        return 2
    except SchemaError:
        print("error: calculated artifact failed schema validation", file=sys.stderr)
        return 2
    except ArtifactExistsError:
        print("error: output already exists; pass --overwrite to replace it", file=sys.stderr)
        return 2
    except OSError:
        print("error: filesystem operation failed", file=sys.stderr)
        return 2

    print(f"wrote {written}")
    return 0


def _load_payload(arguments: argparse.Namespace) -> Any:
    if arguments.json is not None:
        return json.loads(arguments.json)
    if arguments.request == "-":
        return json.loads(sys.stdin.read())
    request_path = Path(arguments.request).expanduser()
    if request_path.suffix.casefold() == ".txt":
        raise _LegacyTxtError
    return json.loads(request_path.read_text(encoding="utf-8"))


def _safe_ephemeris_message(error: EphemerisError) -> str:
    message = str(error).casefold()
    if "whole-sign" in message or "equal houses" in message:
        return "house calculation failed; choose whole-sign or equal houses explicitly"
    if "moshier" in message:
        return (
            "Swiss Ephemeris data was unavailable; provide --ephemeris-path "
            "or explicitly choose allow-moshier"
        )
    return "ephemeris calculation failed"


if __name__ == "__main__":
    raise SystemExit(main())
