"""Replace a file in one step, so nothing ever reads half of it.

The desktop app reads and writes the same files this script does, and the script may
be killed part-way. Writing in place leaves a window in which the file holds some of
the new bytes and none of the rest; a reader then sees broken JSON, and a crash keeps
it that way. Writing beside it and renaming over it leaves only the old file or the
new one: a rename within one directory is atomic on every local filesystem.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

NEW_FILE_MODE = 0o600


def write_bytes(path: Path, content: bytes, mtime: float | None = None, mode: int | None = None) -> None:
    """Make ``path`` hold exactly ``content``, renamed into place from a sibling temporary.

    The file keeps its permission bits; a new one takes ``mode``, private by default
    like every file the app keeps beside it. ``mtime`` is set on the temporary before
    the rename, so the file never shows the moment of writing as its timestamp. The
    temporary's name starts with a dot and ends in ``.tmp``, so no reader that globs
    for the app's own names mistakes a leftover one for an entry.
    """
    if mode is None:
        try:
            mode = path.stat().st_mode & 0o7777
        except FileNotFoundError:
            mode = NEW_FILE_MODE
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if mtime is not None:
            os.utime(temporary, (mtime, mtime))
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
