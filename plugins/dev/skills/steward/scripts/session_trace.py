"""One trace a session left behind, in the shape every inventory source reduces to.

Each source the inventory reads — transcripts, the CLI's agent list, Codex's catalogue,
the desktop app's index — produces these, and the report prints them the same way.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


def iso(timestamp: float) -> str:
    """A timestamp as the report prints it: local time, with its offset."""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(timestamp))


@dataclass
class Session:
    """One trace of a session: which client, where it ran, and when it last moved."""

    client: str
    id: str
    cwd: str
    last_activity: float
    live: bool = False
    kind: str | None = None
    # Listed, unarchived, in the desktop app's sidebar: it holds its worktree however idle.
    open: bool = False

    def as_json(self) -> dict:
        return {
            "client": self.client,
            "id": self.id,
            "cwd": self.cwd,
            "last_activity": iso(self.last_activity),
            "live": self.live,
            "kind": self.kind,
            "open": self.open,
        }
