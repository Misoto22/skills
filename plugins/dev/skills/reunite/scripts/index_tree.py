"""Read the desktop app's per-account conversation index, and the facts around it.

The index sits under ``<root>/<account>/<org>/local_*.json``; identity is the directory
path, and nothing inside a file names an account. The transcripts it points at live in
the CLI's projects directory, keyed by working directory, with no account at all.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import lifecycle

SESSIONS_ROOT_ENV = "CLAUDE_DESKTOP_SESSIONS_DIR"
CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
DEFAULT_ROOT = "~/Library/Application Support/Claude/claude-code-sessions"
DESKTOP_CONFIG = "~/Library/Application Support/Claude/config.json"


@dataclass(frozen=True)
class Entry:
    """One `local_*.json` index file — the sidebar's record of a conversation."""

    path: Path
    session_id: str
    cli_session_id: str | None
    last_activity: int
    mtime: float
    archived: bool = False


def sessions_root() -> Path:
    """Locate the desktop app's index directory, or exit saying it is not there."""
    root = Path(os.environ.get(SESSIONS_ROOT_ENV, DEFAULT_ROOT)).expanduser()
    if not root.is_dir():
        sys.exit(
            f"No desktop session index at {root}\n"
            f"  Set {SESSIONS_ROOT_ENV} if the app stores it elsewhere on this platform."
        )
    return root


def read_entry(path: Path) -> Entry | None:
    """Parse one index file. Returns None for the non-session JSON the app keeps here."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    session_id = data.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        return None
    return Entry(
        path=path,
        session_id=session_id,
        cli_session_id=data.get("cliSessionId"),
        last_activity=data.get("lastActivityAt") or 0,
        mtime=path.stat().st_mtime,
        archived=bool(data.get(lifecycle.ARCHIVE_FIELD)),
    )


def scan(root: Path) -> dict[str, dict[str, list[Entry]]]:
    """Map account -> org -> entries, skipping this script's own dot-directories."""
    tree: dict[str, dict[str, list[Entry]]] = {}
    for account in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        orgs: dict[str, list[Entry]] = {}
        for org in sorted(p for p in account.iterdir() if p.is_dir()):
            entries = [e for e in (read_entry(f) for f in org.glob("local_*.json")) if e]
            orgs[org.name] = entries
        if orgs:
            tree[account.name] = orgs
    return tree


def flatten(tree: dict[str, dict[str, list[Entry]]]) -> list[Entry]:
    """Every entry under every account and org."""
    return [e for orgs in tree.values() for entries in orgs.values() for e in entries]


def transcripts_dir() -> Path:
    """Where the CLI keeps transcripts: CLAUDE_CONFIG_DIR's projects/, else ~/.claude/projects/."""
    return Path(os.environ.get(CONFIG_DIR_ENV) or Path.home() / ".claude") / "projects"


def transcript_ids(projects: Path) -> set[str]:
    """Every CLI session id that still has a transcript under the projects directory."""
    if not projects.is_dir():
        return set()
    found: set[str] = set()
    for project in projects.iterdir():
        if not project.is_dir():
            continue
        try:
            found.update(f.stem for f in project.glob("*.jsonl"))
        except OSError:
            continue
    return found


def landing_org(orgs: dict[str, list[Entry]]) -> str | None:
    """The org subdirectory this account last worked in — where the app will look."""
    active = {name: entries for name, entries in orgs.items() if entries}
    if not active:
        return next(iter(orgs), None)
    return max(active, key=lambda name: max(e.last_activity for e in active[name]))


def scopes_of(tree: dict[str, dict[str, list[Entry]]]) -> dict[str, str]:
    """Each account's sidebar scope key: ``<account>/<the org reunite lands its conversations in>``."""
    return {a: f"{a}/{org}" for a, orgs in tree.items() if (org := landing_org(orgs)) is not None}


def signed_in_account() -> str | None:
    """The account whose index the desktop app is writing, or None if it cannot be read.

    The desktop app and the `claude` CLI hold their own logins and are routinely on
    different accounts, so `~/.claude.json` answers a different question: it names the
    account the CLI authenticates as, not the one whose sidebar is on screen. The app
    records its own in `config.json` as `lastKnownAccountUuid`, and that is the index a
    rename lands in. Fall back to the CLI's only when the app has recorded nothing.
    """
    for path, read in (
        (DESKTOP_CONFIG, lambda d: d.get("lastKnownAccountUuid")),
        ("~/.claude.json", lambda d: (d.get("oauthAccount") or {}).get("accountUuid")),
    ):
        try:
            account = read(json.loads(Path(path).expanduser().read_text()))
        except (OSError, ValueError):
            continue
        if isinstance(account, str) and account:
            return account
    return None
