#!/usr/bin/env python3
"""Resolve, verify, and move the CLI versions CI installs.

A pin is what makes a CI result reproducible. It is also what goes quietly two
years stale, because nothing fails while it is pinned. `.ci-pins.json` is the
one place a version is written down: workflows ask for a spec by id, and `check`
refuses any literal occurrence the file does not account for.

  python3 scripts/ci-pins.py spec claude-code    Print <package>@<version>
  python3 scripts/ci-pins.py check               Fail on drift, or an undeclared occurrence
  python3 scripts/ci-pins.py bump ruff 0.15.0    Move one pin everywhere it is written

`CI_CHANNEL=latest` makes `spec` resolve to `@latest`. That is how the canary
run reaches the same install routes as the pinned run without a second copy of
them, and it is why a workflow must never write a version down itself: a literal
cannot be overridden by a channel.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".ci-pins.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SCAN_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".sh", ".toml"}
VERSION_GROUP = r"(?P<version>\d+\.\d+\.\d+)"


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def find_pin(config: dict, pin_id: str) -> dict:
    for pin in config["pins"]:
        if pin["id"] == pin_id:
            return pin
    known = ", ".join(pin["id"] for pin in config["pins"])
    raise SystemExit(f"error: unknown pin {pin_id!r}; known ids are {known}")


def spec(pin: dict, channel: str) -> str:
    """Return the installable spec, or the floating one when asked for latest."""

    return f"{pin['package']}@{'latest' if channel == 'latest' else pin['version']}"


def _matcher(pin: dict) -> re.Pattern[str]:
    """Match this pin written out literally, whatever version it names."""

    template = pin.get("match") or f"{re.escape(pin['package'])}@{{version}}"
    return re.compile(template.replace("{version}", VERSION_GROUP))


def occurrences(config: dict, pin: dict) -> list[tuple[str, str]]:
    """Return (path, version) for every literal occurrence of this pin in the tree."""

    pattern = _matcher(pin)
    excluded = tuple(config["scan"]["exclude"])
    found: list[tuple[str, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative == CONFIG.name or _excluded(relative, excluded):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        found.extend((relative, match.group("version")) for match in pattern.finditer(text))
    return found


def _excluded(relative: str, excluded: tuple[str, ...]) -> bool:
    """Exclude a path or a directory, never a string prefix: `.git` is not `.github`."""

    return any(relative == entry or relative.startswith(f"{entry}/") for entry in excluded)


def check(config: dict) -> list[str]:
    """Return one line per drifted, undeclared, or vanished occurrence."""

    errors: list[str] = []
    for pin in config["pins"]:
        declared = pin["version"]
        if not SEMVER.match(declared):
            errors.append(f"{pin['id']}: {declared!r} is not a semantic version")
        found = occurrences(config, pin)
        documented = set(pin.get("documented_in", []))

        for relative, version in found:
            if version != declared:
                errors.append(
                    f"{relative}: names {pin['id']} {version}, but .ci-pins.json declares {declared}"
                )
            if relative not in documented:
                errors.append(
                    f"{relative}: writes the {pin['id']} version down. Ask for it with"
                    f" `python3 scripts/ci-pins.py spec {pin['id']}`, or add the file to"
                    " documented_in if it cannot."
                )
        for relative in sorted(documented - {relative for relative, _ in found}):
            errors.append(f"{relative}: declared as naming {pin['id']}, but no version is there")
    return errors


def bump(config: dict, pin: dict, new: str) -> list[str]:
    changed: list[str] = []
    pattern = _matcher(pin)
    for relative in pin.get("documented_in", []):
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        updated = pattern.sub(lambda match: match.group(0).replace(match.group("version"), new), text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(relative)

    pin["version"] = new
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    changed.append(CONFIG.name)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("spec", help="print the installable spec for one pin")
    resolve.add_argument("id")
    commands.add_parser("check", help="fail on drift or an undeclared occurrence")
    move = commands.add_parser("bump", help="move one pin everywhere it is written")
    move.add_argument("id")
    move.add_argument("version")
    args = parser.parse_args()

    config = load_config()

    if args.command == "spec":
        print(spec(find_pin(config, args.id), os.environ.get("CI_CHANNEL", "pinned")))
        return 0

    if args.command == "check":
        errors = check(config)
        if errors:
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            return 1
        for pin in config["pins"]:
            print(f"{pin['id']:<12} {pin['version']}")
        return 0

    pin = find_pin(config, args.id)
    if not SEMVER.match(args.version):
        print(f"error: {args.version!r} is not a semantic version", file=sys.stderr)
        return 1
    if args.version == pin["version"]:
        print(f"error: {pin['id']} is already at {pin['version']}", file=sys.stderr)
        return 1

    current = pin["version"]
    for relative in bump(config, pin, args.version):
        print(f"{current} → {args.version}  {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
