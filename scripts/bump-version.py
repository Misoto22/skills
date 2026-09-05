#!/usr/bin/env python3
"""Move every declared version string to a new release, and find the ones nobody declared.

The version appears in two plugin manifests, three SKILL.md frontmatters, a
constant in the validator, and several test assertions. Editing that by hand is
how a tag ends up describing artefacts that disagree with it.

  python3 scripts/bump-version.py --check      Report the current version, and any drift
  python3 scripts/bump-version.py --audit      Also grep the repository for stragglers
  python3 scripts/bump-version.py <version>    Rewrite every declared occurrence

`--audit` is the half that matters: declaring a file is easy to forget, so the
grep runs over everything not explicitly excluded and reports what the declared
list missed.

The other way a version goes stale is a declared file that stopped carrying it.
A bump moves a version by replacing the string it finds, so such a file is left
alone and says nothing — which is what a merge resolution does when it takes the
older side of one manifest. Both halves of that are reported here, before
anything is written.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".version-bump.json"
REGISTRY = ROOT / "registry.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
AUDIT_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".sh", ".toml"}


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def current_versions(config: dict) -> dict[str, str]:
    """Return every declared JSON version field, keyed by 'path:field'."""

    found: dict[str, str] = {}
    for entry in config["json"]:
        data = json.loads((ROOT / entry["path"]).read_text(encoding="utf-8"))
        value = data
        for part in entry["field"].split("."):
            value = value[int(part)] if part.isdigit() else value[part]
        found[f"{entry['path']}:{entry['field']}"] = value
    return found


def resolve_current(config: dict) -> tuple[str | None, list[str]]:
    """Return the agreed current version, plus a line per disagreement."""

    found = current_versions(config)
    drift = [f"{key} = {value}" for key, value in found.items()]
    distinct = set(found.values())
    if len(distinct) == 1:
        return distinct.pop(), []
    return None, drift


def declared_paths(config: dict) -> list[str]:
    """Return every path the bumper is responsible for, JSON and text alike."""

    return [entry["path"] for entry in config["json"]] + list(config["text"])


def stranded(config: dict, current: str) -> list[str]:
    """Return every declared file that no longer carries the current version.

    `bump` rewrites by replacing the string it finds, so a file holding a
    different version is skipped without a word. A merge that resolves one
    manifest to the older side strands it exactly that way, and every later bump
    walks past it — the drift surfaces only when `validate-repository.py` runs,
    by which time it is committed.
    """

    return [
        relative
        for relative in declared_paths(config)
        if current not in (ROOT / relative).read_text(encoding="utf-8")
    ]


def bump(config: dict, current: str, new: str) -> list[str]:
    changed: list[str] = []
    for entry in config["json"]:
        path = ROOT / entry["path"]
        text = path.read_text(encoding="utf-8")
        # Rewrite in place rather than re-serialising, so formatting survives.
        updated = text.replace(f'"{current}"', f'"{new}"')
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(entry["path"])

    for relative in config["text"]:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        updated = text.replace(current, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(relative)
    return changed


def audit(config: dict, current: str) -> list[str]:
    """Return every file still naming `current` that the declared list does not cover."""

    declared = {entry["path"] for entry in config["json"]} | set(config["text"])
    excluded = tuple(config["audit"]["exclude"])
    nested = _nested_checkouts()
    stragglers: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in AUDIT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in declared or _excluded(relative, excluded) or _excluded(relative, nested):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        hits = text.count(current)
        if hits:
            stragglers.append(f"{relative} ({hits} occurrences)")
    return stragglers


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


def report_stranded(current: str, behind: list[str]) -> None:
    """Name the declared files a bump would silently walk past."""

    print(f"error: declared files no longer carry {current}:", file=sys.stderr)
    for relative in behind:
        print(f"  {relative}", file=sys.stderr)
    print(
        "Set each back to the version the rest of the repository declares, then bump.",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="the new version, e.g. 1.4.0")
    group.add_argument("--check", action="store_true", help="report the current version and any drift")
    group.add_argument("--audit", action="store_true", help="--check, plus grep for undeclared occurrences")
    args = parser.parse_args()

    config = load_config()
    current, drift = resolve_current(config)
    if current is None:
        print("error: declared versions disagree:", file=sys.stderr)
        for line in drift:
            print(f"  {line}", file=sys.stderr)
        return 1

    behind = stranded(config, current)

    if args.check or args.audit:
        print(f"current version: {current}")
        if behind:
            report_stranded(current, behind)
            return 1
        if args.audit:
            stragglers = audit(config, current)
            if stragglers:
                print("undeclared occurrences — add them to .version-bump.json:", file=sys.stderr)
                for line in stragglers:
                    print(f"  {line}", file=sys.stderr)
                return 1
            print("no undeclared occurrences")
        return 0

    if not SEMVER.match(args.version):
        print(f"error: {args.version!r} is not a semantic version", file=sys.stderr)
        return 1
    if args.version == current:
        print(f"error: already at {current}", file=sys.stderr)
        return 1
    # Before anything is written: a bump that half-applies leaves the repository
    # in the state this check exists to catch, and one already committed.
    if behind:
        report_stranded(current, behind)
        return 1

    changed = bump(config, current, args.version)
    # registry.json restates the version fifteen times but is generated rather
    # than declared — which is why the audit excludes it. Rebuilding here rather
    # than leaving it to CI keeps a bump from landing a catalogue that still
    # advertises the version before it.
    changed.extend(rebuild_registry())
    for relative, count in sorted(Counter(changed).items()):
        print(f"{current} → {args.version}  {relative}" + (f" ({count} occurrences)" if count > 1 else ""))
    print(f"\n{len(set(changed))} files updated. Next: update CHANGELOG.md, then tag v{args.version}.")
    return 0


def rebuild_registry() -> list[str]:
    """Regenerate registry.json, and name it if it changed."""

    before = REGISTRY.read_bytes() if REGISTRY.is_file() else b""
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build-registry.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [] if REGISTRY.read_bytes() == before else ["registry.json"]


if __name__ == "__main__":
    raise SystemExit(main())
