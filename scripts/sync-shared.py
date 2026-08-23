#!/usr/bin/env python3
"""Vendor shared code down to every skill that ships it.

Agent installers copy a skill directory and nothing above it. A reference that
climbs out of the skill resolves only in the Claude Code plugin cache and
silently dangles everywhere else, so each skill carries its own copy of
shared/. Copying runs in two passes:

  shared/<component>/        -> plugins/<plugin>/shared/<component>/
  plugins/<plugin>/shared/   -> plugins/<plugin>/skills/<skill>/shared/

The first pass exists because a component such as the ink-wash report belongs to
several subject plugins at once, and a plugin has to stay installable on its
own. shared/components.json declares which plugins vendor which component.
Only the repository-level source and each plugin's own shared/ are edited by
hand; everything below them is rewritten.

  python3 scripts/sync-shared.py           # write the copies
  python3 scripts/sync-shared.py --check   # fail if a copy is stale
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
SHARED_ROOT = ROOT / "shared"
COMPONENTS_MANIFEST = SHARED_ROOT / "components.json"
VENDORED_DIRNAME = "shared"
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class ManifestError(ValueError):
    """shared/components.json does not describe a syncable component set."""


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
    """Return every source-to-copy directory pair, repository components first.

    Order matters: a component lands in the plugin before that plugin is copied
    down into its skills, so one run reaches every skill.
    """

    pairs: list[tuple[Path, Path]] = list(_component_pairs())
    for plugin_manifest in sorted(PLUGINS_ROOT.glob("*/.claude-plugin/plugin.json")):
        plugin_root = plugin_manifest.parent.parent
        source = plugin_root / VENDORED_DIRNAME
        if not source.is_dir():
            continue
        for skill_file in sorted(plugin_root.glob("skills/*/SKILL.md")):
            pairs.append((source, skill_file.parent / VENDORED_DIRNAME))
    return pairs


def _component_pairs() -> list[tuple[Path, Path]]:
    """Return every (repository component, plugin copy) pair the manifest declares."""

    if not COMPONENTS_MANIFEST.is_file():
        return []
    try:
        manifest = json.loads(COMPONENTS_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ManifestError(f"{COMPONENTS_MANIFEST.name} is not valid JSON: {error}") from error

    components = manifest.get("components")
    if not isinstance(components, dict):
        raise ManifestError(f"{COMPONENTS_MANIFEST.name} needs a 'components' object")

    pairs: list[tuple[Path, Path]] = []
    for component, plugins in sorted(components.items()):
        source = SHARED_ROOT / component
        if not source.is_dir():
            raise ManifestError(f"component {component!r} has no directory at shared/{component}")
        if not isinstance(plugins, list) or not plugins:
            raise ManifestError(f"component {component!r} must list at least one plugin")
        for plugin in sorted(plugins):
            plugin_root = PLUGINS_ROOT / str(plugin)
            if not (plugin_root / ".claude-plugin" / "plugin.json").is_file():
                raise ManifestError(f"component {component!r} names unknown plugin {plugin!r}")
            pairs.append((source, plugin_root / VENDORED_DIRNAME / component))
    return pairs


def _relative_files(directory: Path) -> set[Path]:
    if not directory.is_dir():
        return set()
    return {
        relative
        for path in directory.rglob("*")
        if path.is_file() and not _excluded(relative := path.relative_to(directory))
    }


def _excluded(relative: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in relative.parts) or relative.suffix in EXCLUDED_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale copies and exit nonzero instead of writing them",
    )
    args = parser.parse_args()

    try:
        stale = sync(check_only=args.check)
    except ManifestError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
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
