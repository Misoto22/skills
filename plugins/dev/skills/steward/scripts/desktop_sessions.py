"""The desktop app's session index, read for the worktrees its open conversations hold.

`claude agents --json` lists background agents only, so a desktop or terminal session
left open and idle has no process the CLI reports. The sidebar index still lists it, and
an unarchived conversation there is one the person can go back to — its worktree is
occupied. This only marks occupancy: it never adds a repository to the inventory, or
every conversation left unarchived for months would widen the sweep past its window.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from session_trace import Session

# The same root and override reunite reads: one index file per conversation per account.
SESSIONS_ROOT_ENV = "CLAUDE_DESKTOP_SESSIONS_DIR"
DEFAULT_ROOT = "~/Library/Application Support/Claude/claude-code-sessions"


def sessions_root() -> Path:
    """Where the index lives: the override when set, else the app's default on macOS."""
    return Path(os.environ.get(SESSIONS_ROOT_ENV) or DEFAULT_ROOT).expanduser()


def open_sessions(root: Path) -> list[Session] | None:
    """Every unarchived conversation in the index; None when there is no index.

    Each account keeps its own copy of a conversation, so one is read once per
    conversation and path, and both `worktreePath` and `cwd` count.
    """
    if not root.is_dir():
        return None
    found: dict[tuple[str, str], Session] = {}
    for path in sorted(root.glob("*/*/local_*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            modified = path.stat().st_mtime
        except (OSError, ValueError):
            continue
        if not isinstance(entry, dict) or entry.get("isArchived"):
            continue
        identifier = str(entry.get("sessionId") or path.stem.removeprefix("local_"))
        stamp = entry.get("lastActivityAt")
        last = float(stamp) / 1000 if isinstance(stamp, (int, float)) and stamp else modified
        for cwd in (entry.get("worktreePath"), entry.get("cwd")):
            if isinstance(cwd, str) and cwd and (identifier, cwd) not in found:
                found[(identifier, cwd)] = Session("claude-desktop", identifier, cwd, last, open=True)
    return list(found.values())


def held_by_worktree(sessions: list[Session], worktrees: list[str]) -> dict[str, list[Session]]:
    """{worktree real path: the open conversations inside it}, one entry per conversation.

    A path belongs to the deepest worktree containing it, since a linked worktree can sit
    inside its primary's directory. A conversation's `worktreePath` and `cwd` usually
    land in the same worktree, and it is listed there once.
    """
    held: dict[str, dict[str, Session]] = {}
    for session in sessions:
        real = os.path.realpath(session.cwd)
        containing = [root for root in worktrees if real == root or real.startswith(root + os.sep)]
        owner = max(containing, key=len, default=None)
        if owner is not None:
            held.setdefault(owner, {}).setdefault(session.id, session)
    return {owner: list(by_id.values()) for owner, by_id in held.items()}
