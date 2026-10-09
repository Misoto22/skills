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

The second pass copies the whole plugin shared/ unless the skill declares what it
uses in a shared.json beside its SKILL.md, as {"include": [...]}. Each entry is a
file or a directory relative to the plugin's shared/. A skill that declares a list
receives exactly those files, and a vendored file outside it is an orphan: a
written run deletes it and --check reports it. An empty list vendors nothing.
Without the file a skill receives everything, so a new skill works before anyone
has decided what it needs.

  python3 scripts/sync-shared.py           # write the copies
  python3 scripts/sync-shared.py --check   # fail if a copy is stale or orphaned
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
SHARED_ROOT = ROOT / "shared"
COMPONENTS_MANIFEST = SHARED_ROOT / "components.json"
VENDORED_DIRNAME = "shared"
SKILL_MANIFEST = "shared.json"
SKILL_MANIFEST_KEYS = {"$comment", "include"}
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class ManifestError(ValueError):
    """shared/components.json or a skill's shared.json cannot be synced as written."""


class Pair(NamedTuple):
    """One source directory and the copy written from it.

    `include` is None when every file is vendored, otherwise the entries a
    skill's shared.json names.
    """

    source: Path
    destination: Path
    include: tuple[Path, ...] | None = None


def sync(*, check_only: bool) -> list[str]:
    """Return the paths that are missing, stale or orphaned; fix them unless check_only."""

    stale: list[str] = []
    for pair in _pairs():
        expected = _expected_files(pair)
        for relative in sorted(expected):
            target = pair.destination / relative
            origin = pair.source / relative
            if target.is_file() and filecmp.cmp(origin, target, shallow=False):
                continue
            stale.append(str(target.relative_to(ROOT)))
            if not check_only:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, target)

        available = _relative_files(pair.source)
        for relative in sorted(_relative_files(pair.destination) - expected):
            orphan = pair.destination / relative
            stale.append(f"{orphan.relative_to(ROOT)} ({_orphan_reason(relative, available)})")
            if not check_only:
                orphan.unlink()
        if not check_only:
            _remove_empty_directories(pair.destination)
    return stale


def _orphan_reason(relative: Path, available: set[Path]) -> str:
    if relative in available:
        return f"not in the skill's {SKILL_MANIFEST}"
    return "not in the plugin's shared/"


def _pairs() -> list[Pair]:
    """Return every source-to-copy directory pair, repository components first.

    Order matters: a component lands in the plugin before that plugin is copied
    down into its skills, so one run reaches every skill.
    """

    pairs: list[Pair] = list(_component_pairs())
    for plugin_manifest in sorted(PLUGINS_ROOT.glob("*/.claude-plugin/plugin.json")):
        plugin_root = plugin_manifest.parent.parent
        source = plugin_root / VENDORED_DIRNAME
        for skill_file in sorted(plugin_root.glob("skills/*/SKILL.md")):
            # Read even when the plugin has no shared/, so a list naming files
            # that do not exist fails rather than being ignored.
            include = skill_include(skill_file.parent, source)
            if source.is_dir():
                pairs.append(Pair(source, skill_file.parent / VENDORED_DIRNAME, include))
    return pairs


def skill_include(skill: Path, source: Path) -> tuple[Path, ...] | None:
    """Return the shared/ entries a skill's shared.json names, or None without one.

    Every entry must exist under the plugin's shared/, so a renamed module fails
    the sync instead of silently leaving the skill without it.
    """

    manifest_path = skill / SKILL_MANIFEST
    if not manifest_path.is_file():
        return None
    label = f"{skill.name}/{SKILL_MANIFEST}"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ManifestError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("include"), list):
        raise ManifestError(f"{label} needs an 'include' list")
    unknown = sorted(set(manifest) - SKILL_MANIFEST_KEYS)
    if unknown:
        raise ManifestError(f"{label} has unknown keys {unknown}")

    entries: list[Path] = []
    for entry in manifest["include"]:
        relative = _include_entry(entry, label)
        if not (source / relative).exists():
            raise ManifestError(f"{label} includes {entry!r}, which is not in the plugin's shared/")
        if relative in entries:
            raise ManifestError(f"{label} includes {entry!r} twice")
        entries.append(relative)
    return tuple(entries)


def _include_entry(entry: object, label: str) -> Path:
    if not isinstance(entry, str) or not entry or "\\" in entry:
        raise ManifestError(f"{label} include entries must be non-empty POSIX paths; found {entry!r}")
    posix = PurePosixPath(entry)
    if posix.is_absolute() or ".." in posix.parts or posix.as_posix() != entry:
        raise ManifestError(f"{label} include entry {entry!r} must be a plain relative path in shared/")
    return Path(*posix.parts)


def _expected_files(pair: Pair) -> set[Path]:
    available = _relative_files(pair.source)
    if pair.include is None:
        return available
    return {
        relative
        for relative in available
        if any(relative == entry or entry in relative.parents for entry in pair.include)
    }


def _component_pairs() -> list[Pair]:
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

    pairs: list[Pair] = []
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
            pairs.append(Pair(source, plugin_root / VENDORED_DIRNAME / component))
    return pairs


def _relative_files(directory: Path) -> set[Path]:
    if not directory.is_dir():
        return set()
    return {
        relative
        for path in directory.rglob("*")
        if path.is_file() and not _excluded(relative := path.relative_to(directory))
    }


def _remove_empty_directories(directory: Path) -> None:
    """Drop the directories a prune emptied, the vendored root included, deepest first."""

    if not directory.is_dir():
        return
    nested = sorted(directory.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in [*nested, directory]:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def _excluded(relative: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in relative.parts) or relative.suffix in EXCLUDED_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale or orphaned copies and exit nonzero instead of fixing them",
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
