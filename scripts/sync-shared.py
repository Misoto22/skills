#!/usr/bin/env python3
"""Vendor each plugin's shared/ directory into every skill that plugin ships.

Agent installers copy a skill directory and nothing above it. A reference that
climbs out of the skill resolves only in the Claude Code plugin cache and
silently dangles everywhere else, so each skill carries its own copy of
shared/. The plugin-level directory stays the only file anyone edits.

  python3 scripts/sync-shared.py           # write the copies
  python3 scripts/sync-shared.py --check   # fail if a copy is stale
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
VENDORED_DIRNAME = "shared"


def sync(*, check_only: bool) -> list[str]:
    """Return the paths that are missing or stale; write them unless check_only."""

    stale: list[str] = []
    for source, destination in _pairs():
        for relative in sorted(_relative_files(source)):
            target = destination / relative
            origin = source / relative
            if target.is_file() and filecmp.cmp(origin, target, shallow=False):
                continue
            stale.append(str(target.relative_to(ROOT)))
            if not check_only:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, target)

        expected = _relative_files(source)
        for relative in sorted(_relative_files(destination) - expected):
            orphan = destination / relative
            stale.append(f"{orphan.relative_to(ROOT)} (not in the plugin's shared/)")
            if not check_only:
                orphan.unlink()
    return stale


def _pairs() -> list[tuple[Path, Path]]:
    """Return every (plugin shared/, skill shared/) directory pair to keep in sync."""

    pairs: list[tuple[Path, Path]] = []
    for plugin_manifest in sorted(PLUGINS_ROOT.glob("*/.claude-plugin/plugin.json")):
        plugin_root = plugin_manifest.parent.parent
        source = plugin_root / VENDORED_DIRNAME
        if not source.is_dir():
            continue
        for skill_file in sorted(plugin_root.glob("skills/*/SKILL.md")):
            pairs.append((source, skill_file.parent / VENDORED_DIRNAME))
    return pairs


def _relative_files(directory: Path) -> set[Path]:
    if not directory.is_dir():
        return set()
    return {path.relative_to(directory) for path in directory.rglob("*") if path.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale copies and exit nonzero instead of writing them",
    )
    args = parser.parse_args()

    stale = sync(check_only=args.check)
    if args.check and stale:
        for path in stale:
            print(f"error: stale vendored copy: {path}", file=sys.stderr)
        print("run: python3 scripts/sync-shared.py", file=sys.stderr)
        return 1
    if stale:
        for path in stale:
            print(f"synced {path}")
    else:
        print("vendored shared/ copies are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
