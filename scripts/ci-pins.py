#!/usr/bin/env python3
"""Resolve, verify, and move every version CI depends on.

A pin is what makes a CI result reproducible. It is also what goes quietly two
years stale, because nothing fails while it is pinned. `.ci-pins.json` is the
one place a version is written down: workflows ask for a spec by id, and `check`
refuses any literal occurrence the file does not account for.

  python3 scripts/ci-pins.py spec claude-code    Print <package>@<version>
  python3 scripts/ci-pins.py check               Fail on drift, or an undeclared occurrence
  python3 scripts/ci-pins.py bump ruff 0.15.0    Move one pin everywhere it is written

Not only npm and pip packages. A runtime is asked for as `3.13` or `22`, and the
model an unattended evaluation bills against is not a version at all — both used
to sit as literals in four workflows and a script, where nothing compared them.
A pin declares its own `version_pattern` when the default semver does not fit.

`CI_CHANNEL=latest` makes `spec` resolve to the floating form, which is how the
canary reaches the same install routes as the pinned run without a second copy
of them. A pin that cannot float says so by declaring a `spec_latest` that
resolves to the version it already holds — a runtime is chosen, not upgraded to.
That is also why a workflow must never write a version down itself: a literal
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
SCAN_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".sh", ".toml"}
# What a version looks like, for the pins that are npm or pip packages. A pin
# may override it with `version_pattern`: a runtime is asked for as `3.13` or
# `22`, and the model an unattended run bills against is not a version at all.
# Holding those to semver would have meant either leaving them written into four
# workflows or inventing a third digit nobody could install.
DEFAULT_VERSION_PATTERN = r"\d+\.\d+\.\d+"


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def find_pin(config: dict, pin_id: str) -> dict:
    for pin in config["pins"]:
        if pin["id"] == pin_id:
            return pin
    known = ", ".join(pin["id"] for pin in config["pins"])
    raise SystemExit(f"error: unknown pin {pin_id!r}; known ids are {known}")


def spec(pin: dict, channel: str) -> str:
    """Return the installable spec, or the floating one when asked for latest.

    npm and pip spell a pin differently, so a pin may carry its own template
    rather than the npm form every other one uses. Both templates see both
    fields: a pin that cannot float — a runtime, or the model an eval bills
    against — says so by resolving `latest` to the version it already declares.
    """

    template = (
        pin.get("spec_latest", "{package}@latest")
        if channel == "latest"
        else pin.get("spec", "{package}@{version}")
    )
    return template.format(package=pin["package"], version=pin["version"])


def _version_pattern(pin: dict) -> re.Pattern[str]:
    """Return what a version of this pin is allowed to look like."""

    return re.compile(f"\\A{pin.get('version_pattern', DEFAULT_VERSION_PATTERN)}\\Z")


def _matcher(pin: dict) -> re.Pattern[str]:
    """Match this pin written out literally, whatever version it names."""

    template = pin.get("match") or f"{re.escape(pin['package'])}@{{version}}"
    group = f"(?P<version>{pin.get('version_pattern', DEFAULT_VERSION_PATTERN)})"
    return re.compile(template.replace("{version}", group))


def occurrences(config: dict, pin: dict) -> list[tuple[str, str]]:
    """Return (path, version) for every literal occurrence of this pin in the tree."""

    pattern = _matcher(pin)
    excluded = tuple(config["scan"]["exclude"])
    nested = _nested_checkouts()
    found: list[tuple[str, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative == CONFIG.name or _excluded(relative, excluded) or _excluded(relative, nested):
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


def _nested_checkouts() -> tuple[str, ...]:
    """Return every directory below ROOT that is its own checkout.

    A `git worktree`, a submodule, or a stray clone carries a `.git` entry of its
    own and holds a second copy of every manifest, README and workflow. Both
    scanners recurse from the repository root, so without this they report files
    nobody in this checkout wrote. Excluding by configured path only ever covered
    the one location someone thought of; excluding by `.git` covers all of them.
    """

    roots: list[str] = []
    for marker in ROOT.rglob(".git"):
        relative = marker.parent.relative_to(ROOT).as_posix()
        if relative != ".":
            roots.append(relative)
    return tuple(sorted(roots))


def check(config: dict) -> list[str]:
    """Return one line per drifted, undeclared, or vanished occurrence."""

    errors: list[str] = []
    for pin in config["pins"]:
        declared = pin["version"]
        if not _version_pattern(pin).match(declared):
            errors.append(f"{pin['id']}: {declared!r} does not match the shape this pin declares")
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
    if not _version_pattern(pin).match(args.version):
        shape = pin.get("version_pattern", DEFAULT_VERSION_PATTERN)
        print(f"error: {args.version!r} does not match {pin['id']}'s shape, {shape}", file=sys.stderr)
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
