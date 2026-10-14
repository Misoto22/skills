"""``--undo``: put back everything previous runs changed, as the manifest records it."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import environments_sync
import lifecycle
import sidebar_sync
from manifest import (
    MANIFEST_NAME,
    environments_records,
    index_path,
    local_storage_records,
    read_manifest,
    restore_backups,
)

TITLE_FIELDS = ("title", "titleSource", "previousTitles")


def undo(root: Path) -> int:
    """Remove the files previous runs created and restore every original they replaced."""
    manifest = root / MANIFEST_NAME
    copied, titles, backups = read_manifest(root, manifest)
    stores = local_storage_records(root)
    presets = environments_records(root)
    if not copied and not titles and not backups and not stores and not presets:
        print(f"Nothing to undo — no {MANIFEST_NAME} under {root}")
        return 0
    # These two exit when they cannot restore, so they run before anything else is undone.
    environments_sync.check_undo(root, presets)
    if stores:
        sidebar_sync.undo(root, stores)
    if presets:
        # Before restore_backups, which drops the backup directory this one is read from.
        environments_sync.undo(root, presets)
    removed = 0
    for path in copied:
        target = index_path(root, path)
        if target is None:
            continue
        try:
            target.unlink()
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as error:
            print(f"  could not remove {path}: {error}", file=sys.stderr)
    restored = restore_backups(root, backups, set(copied))
    retitled = restore_titles(root, titles)
    (root / lifecycle.BASELINE_NAME).unlink(missing_ok=True)
    manifest.unlink(missing_ok=True)
    print(f"Removed {removed} of {len(copied)} created entries.")
    print(f"Restored {restored} of {len(backups)} originals.")
    if titles:
        print(f"Restored {retitled} of {len(titles)} replaced titles.")
    print("Restart the desktop app.")
    return 0


def restore_titles(root: Path, titles: list[dict[str, object]]) -> int:
    """Put back titles recorded by a run from before whole files were mirrored."""
    restored = 0
    for record in titles:
        path = index_path(root, record.get("path"))
        if path is None or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for field in TITLE_FIELDS:
            if record.get(field) is None:
                data.pop(field, None)
            else:
                data[field] = record[field]
        stat = path.stat()
        path.write_text(json.dumps(data, separators=(",", ":")))
        os.utime(path, (stat.st_atime, stat.st_mtime))
        restored += 1
    return restored
