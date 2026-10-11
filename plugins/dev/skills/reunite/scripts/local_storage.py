"""Where the desktop app's Local Storage lives, and the guards around writing to it.

The app holds its Local Storage LevelDB open the whole time it runs and writes the
sidebar layout back from memory, so a value appended while it runs is either refused
by the lock or overwritten on its next save. Nothing here writes unless the app is
fully quit: no process named ``Claude``, and LevelDB's ``LOCK`` file free.

Every write is preceded by a copy of the whole directory, which is what a failed
verification and ``--undo`` restore.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

STORE_ENV = "CLAUDE_DESKTOP_LOCAL_STORAGE_DIR"
DEFAULT_STORE = "~/Library/Application Support/Claude/Local Storage/leveldb"
APP_PROCESS = "Claude"
BACKUP_PREFIX = "local-storage-"
REPLACED_DIR = ".session-merge-replaced"
QUIT_FIRST = "Quit Claude completely first (Cmd-Q, not just closing the window), then rerun."


def store_dir() -> Path:
    """Locate the Local Storage LevelDB directory, or exit saying it is not there."""
    store = Path(os.environ.get(STORE_ENV, DEFAULT_STORE)).expanduser()
    if not (store / "CURRENT").is_file():
        sys.exit(
            f"No Local Storage database at {store}\n"
            f"  Set {STORE_ENV} if the app keeps it elsewhere on this platform."
        )
    return store


def app_running() -> bool:
    """Whether a process named exactly ``Claude`` is running, where pgrep can tell.

    macOS pgrep leaves out its own ancestors unless given ``-a``, and a run started from
    the app's own terminal or Code tab is a descendant of the app — the one case where
    the check matters most. Linux pgrep reads ``-a`` as "print the command line", which
    does not change the exit status this reads.
    """
    try:
        found = subprocess.run(["pgrep", "-a", "-x", APP_PROCESS], capture_output=True, check=False)
    except FileNotFoundError:
        return False
    return found.returncode == 0


@contextmanager
def exclusive(store: Path) -> Iterator[None]:
    """Hold LevelDB's own lock on ``store`` for the duration, or exit if anything else has it.

    LevelDB locks ``LOCK`` with fcntl; some builds use flock, so that is probed too and
    released before the fcntl lock is taken, since on BSD the two can conflict even
    within one process.
    """
    if app_running():
        sys.exit(f"Claude is running, and it holds the sidebar layout in memory. {QUIT_FIRST}")
    with (store / "LOCK").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
            fcntl.lockf(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit(f"Another process holds the Local Storage database at {store}. {QUIT_FIRST}")
        try:
            yield
        finally:
            fcntl.lockf(handle, fcntl.LOCK_UN)


def _stamped(parent: Path, prefix: str) -> Path:
    """A fresh ``<prefix><UTC timestamp>`` directory path under ``parent``."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = parent / f"{prefix}{stamp}"
    suffix = 2
    while path.exists():
        path = parent / f"{prefix}{stamp}-{suffix}"
        suffix += 1
    return path


def backup(store: Path, backup_root: Path) -> Path:
    """Copy the whole LevelDB directory to a new timestamped directory under ``backup_root``."""
    backup_root.mkdir(parents=True, exist_ok=True)
    destination = _stamped(backup_root, BACKUP_PREFIX)
    shutil.copytree(store, destination)
    return destination


def restore(saved: Path, store: Path, keep_root: Path | None = None) -> Path | None:
    """Replace ``store`` with the copy at ``saved``; keep what it replaced under ``keep_root``.

    The copy is staged beside the store and renamed into place, so an interrupted
    restore leaves either the old directory or the new one, never half of each.
    """
    kept = None
    if keep_root is not None:
        keep_root.mkdir(parents=True, exist_ok=True)
        kept = _stamped(keep_root, BACKUP_PREFIX)
        shutil.copytree(store, kept)
    staging = store.with_name(f"{store.name}.reunite-restore")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(saved, staging)
    shutil.rmtree(store)
    staging.rename(store)
    return kept
