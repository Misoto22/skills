"""The record `--undo` reads: every file a merge created, and the original of every file
it overwrote or removed.

The manifest sits beside the account directories and survives app updates, manual
edits and interrupted runs, so every path read back from it is treated as untrusted:
it may name only an actual ``<account>/<organisation>/local_*.json`` entry in the
selected session tree. An original is kept gzipped under ``BACKUP_DIR`` at the same
relative path, so its location is derived from a validated path, never read from disk.

A copy of the desktop app's Local Storage, taken before the sidebar layout is written,
is recorded by its directory name under ``BACKUP_DIR`` and the store it was taken from;
only a name in the shape this script writes is accepted back.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
from pathlib import Path

MANIFEST_NAME = ".session-merge-manifest.json"
BACKUP_DIR = ".session-merge-backup"
LOCAL_STORAGE_KEY = "localStorage"
_LOCAL_STORAGE_BACKUP = re.compile(r"local-storage-\d{8}T\d{6}Z(-\d+)?")


def index_path(root: Path, raw_path: object) -> Path | None:
    """Resolve a manifest entry only when it names a session index below ``root``.

    Older manifests stored absolute paths, so accept those only after resolving them
    back into the same root.
    """
    if not isinstance(raw_path, str) or not raw_path:
        return None
    resolved_root = root.resolve()
    candidate = Path(raw_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (resolved_root / candidate).resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError:
        return None
    if len(relative.parts) != 3 or not relative.name.startswith("local_") or relative.suffix != ".json":
        return None
    return resolved


def manifest_path(root: Path, raw_path: object) -> str | None:
    """The portable root-relative form for one validated index path."""
    resolved = index_path(root, raw_path)
    if resolved is None:
        return None
    return resolved.relative_to(root.resolve()).as_posix()


def field_record(root: Path, record: object) -> dict[str, object] | None:
    """Keep a recovery record only when its path belongs to this session tree."""
    if not isinstance(record, dict):
        return None
    path = manifest_path(root, record.get("path"))
    if path is None:
        return None
    return {**record, "path": path}


def _valid(root: Path, items: object, keep) -> list:
    """Keep the items ``keep`` accepts for this root; anything that is not a list holds none."""
    if not isinstance(items, list):
        return []
    return [kept for item in items if (kept := keep(root, item)) is not None]


def _merge_records(held: list[dict[str, object]], new: list[dict[str, object]]) -> list[dict[str, object]]:
    # The earliest original is the one to restore, so a path already recorded keeps its record.
    recorded = {entry["path"] for entry in held}
    return held + [entry for entry in new if entry["path"] not in recorded]


def local_storage_record(_root: Path, record: object) -> dict[str, str] | None:
    """Keep a Local Storage backup record only when its name is one this script writes."""
    if not isinstance(record, dict):
        return None
    name, store = record.get("backup"), record.get("store")
    if not isinstance(name, str) or not _LOCAL_STORAGE_BACKUP.fullmatch(name) or not isinstance(store, str):
        return None
    return {"backup": name, "store": store}


def local_storage_records(root: Path) -> list[dict[str, str]]:
    """Every Local Storage backup recorded so far, earliest first."""
    try:
        data = json.loads((root / MANIFEST_NAME).read_text())
    except (OSError, ValueError):
        return []
    return _valid(root, data.get(LOCAL_STORAGE_KEY), local_storage_record) if isinstance(data, dict) else []


def write_manifest(
    root: Path,
    copied: list[str],
    backups: list[dict[str, object]],
    local_storage: dict[str, str] | None = None,
) -> Path:
    """Merge this run's record into the manifest --undo reads."""
    manifest = root / MANIFEST_NAME
    held_copied, held_titles, held_backups = read_manifest(root, manifest)
    stores = local_storage_records(root) + _valid(root, [local_storage], local_storage_record)
    payload: dict[str, object] = {
        "copied": sorted(set(held_copied) | set(_valid(root, copied, manifest_path))),
        "backups": _merge_records(held_backups, _valid(root, backups, field_record)),
    }
    if held_titles:
        payload["titles"] = held_titles
    if stores:
        payload[LOCAL_STORAGE_KEY] = stores
    manifest.write_text(json.dumps(payload, indent=2))
    return manifest


def read_manifest(
    root: Path, manifest: Path
) -> tuple[list[str], list[dict[str, object]], list[dict[str, object]]]:
    """What previous runs wrote: created paths, legacy title records, and backed-up originals.

    A manifest written before titles were reconciled is a bare list of paths, and one
    written before whole files were mirrored records titles field by field. Both are
    still read, so an older merge stays undoable.
    """
    try:
        data = json.loads(manifest.read_text())
    except (OSError, ValueError):
        return [], [], []
    if isinstance(data, list):
        return _valid(root, data, manifest_path), [], []
    if not isinstance(data, dict):
        return [], [], []
    return (
        _valid(root, data.get("copied"), manifest_path),
        _valid(root, data.get("titles"), field_record),
        _valid(root, data.get("backups"), field_record),
    )


def _backup_file(root: Path, relative: str) -> Path:
    return root / BACKUP_DIR / f"{relative}.gz"


def save_backup(root: Path, path: Path) -> dict[str, object] | None:
    """Keep the original of an index file about to be overwritten or removed.

    Only the first original is kept: a later run overwriting the same file again must
    not replace what --undo restores with something this script wrote itself.
    """
    relative = manifest_path(root, str(path))
    if relative is None:
        return None
    backup = _backup_file(root, relative)
    if backup.exists():
        return None
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(gzip.compress(path.read_bytes()))
    return {"path": relative, "mtime": path.stat().st_mtime}


def restore_backups(root: Path, records: list[dict[str, object]], skip: set[str]) -> int:
    """Put every backed-up original back, then drop the backup directory.

    A path in ``skip`` is one this script created, which --undo removes instead.
    """
    restored = 0
    for record in records:
        path = index_path(root, record.get("path"))
        if path is None or record["path"] in skip:
            continue
        backup = _backup_file(root, str(record["path"]))
        try:
            content = gzip.decompress(backup.read_bytes())
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        mtime = record.get("mtime")
        if isinstance(mtime, (int, float)):
            os.utime(path, (mtime, mtime))
        restored += 1
    shutil.rmtree(root / BACKUP_DIR, ignore_errors=True)
    return restored
