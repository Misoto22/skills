#!/usr/bin/env python3
"""Inventory the repositories a person has been working in, from the agent's own records.

The steward sweeps every active repository, and "active" is not a question git can
answer: a repository is active because a session was open in it. So the list comes from
where sessions leave traces — Claude Code's transcripts and its running sessions, Codex's
thread catalogue — plus any directory the caller names. Each trace resolves to the
worktree it sits in, each worktree to the primary checkout it belongs to, and the result
is one JSON document the sweep reads before it touches anything.

Nothing here writes, and nothing here needs the network. The only subprocesses are
read-only `git` queries and, when a binary is given, `claude agents --json`.

  inventory.py                            # last 14 days, every source found
  inventory.py --since 30 --roots ~/src   # wider window, plus every repository under ~/src
  inventory.py --no-live                  # do not ask the CLI for running sessions

Standard library only, for the reason the retitle hook is: a skill lands on whatever
machine installed it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_SINCE_DAYS = 14.0
DEFAULT_OCCUPIED_HOURS = 24.0
# How far into a transcript to look for its working directory. Nearly every entry
# carries one, but the first lines of a resumed session can be bookkeeping records.
TRANSCRIPT_HEAD_LINES = 200
SUBPROCESS_TIMEOUT_SECONDS = 20


@dataclass
class Session:
    """One trace of a session: which client, where it ran, and when it last moved."""

    client: str
    id: str
    cwd: str
    last_activity: float
    live: bool = False
    kind: str | None = None

    def as_json(self) -> dict:
        return {
            "client": self.client,
            "id": self.id,
            "cwd": self.cwd,
            "last_activity": _iso(self.last_activity),
            "live": self.live,
            "kind": self.kind,
        }


@dataclass
class Skipped:
    """Traces that resolved to nothing sweepable. Counted and reported, never raised."""

    temporary: int = 0
    missing: int = 0
    not_git: int = 0
    unresolved: int = 0


def _iso(timestamp: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(timestamp))


def claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def codex_home_dir() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def default_ignored() -> list[str]:
    """Where scratch checkouts and agent sandboxes live: not the person's to sweep."""

    return sorted({os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp")})


def claude_transcripts(config_dir: Path, cutoff: float, skipped: Skipped) -> list[Session]:
    """Every transcript written since the cutoff, with the directory its session ran in."""

    found: list[Session] = []
    projects = config_dir / "projects"
    if not projects.is_dir():
        return found
    for transcript in sorted(projects.glob("*/*.jsonl")):
        try:
            modified = transcript.stat().st_mtime
        except OSError:
            continue
        if modified < cutoff:
            continue
        cwd = _transcript_cwd(transcript)
        if cwd is None:
            skipped.unresolved += 1
            continue
        found.append(Session("claude-code", transcript.stem, cwd, modified))
    return found


def _transcript_cwd(transcript: Path) -> str | None:
    """The first working directory a transcript records, or None.

    The directory name above the file encodes the path too, but lossily: `/`, ` ` and
    `-` all become `-`, so it cannot be turned back into one. The entries can.
    """

    try:
        with transcript.open(encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle):
                if index >= TRANSCRIPT_HEAD_LINES:
                    break
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # A torn write at the tail of a live session; the next line is whole.
                    continue
                cwd = entry.get("cwd") if isinstance(entry, dict) else None
                if isinstance(cwd, str) and cwd:
                    return cwd
    except OSError:
        return None
    return None


def claude_live_sessions(binary: str, now: float, cutoff: float) -> list[Session] | None:
    """Sessions the CLI knows about; None when it cannot be asked.

    A session with a process attached is live and occupies its directory now. One the
    CLI still lists but has no process — a stopped background session — is a plain trace
    dated from when it started, and falls out of the window like any other.
    """

    try:
        result = subprocess.run(
            [binary, "agents", "--json"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        listed = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if not isinstance(listed, list):
        return None
    found: list[Session] = []
    for agent in listed:
        if not isinstance(agent, dict) or not isinstance(agent.get("cwd"), str):
            continue
        live = bool(agent.get("pid"))
        started = agent.get("startedAt")
        last = now if live else (float(started) / 1000 if isinstance(started, (int, float)) else now)
        if last < cutoff:
            continue
        identifier = str(agent.get("sessionId") or agent.get("id") or "")
        found.append(
            Session("claude-code", identifier, agent["cwd"], last, live=live, kind=agent.get("kind"))
        )
    return found


def codex_threads(codex_home: Path, cutoff: float) -> list[Session] | None:
    """Local Codex threads updated since the cutoff; None when there is no catalogue.

    The turn-summaries database beside the catalogue carries no threads and is skipped
    by name. Rows under a cloud host are a mirror of the cloud catalogue, and a thread
    the scanner can no longer find is on its way out; neither says where work is.
    """

    databases = [
        path for path in sorted((codex_home / "sqlite").glob("codex*.db")) if "summaries" not in path.name
    ]
    if not databases:
        return None
    found: list[Session] = []
    for database in databases:
        found.extend(_codex_rows(database, cutoff))
    return found


def _codex_rows(database: Path, cutoff: float) -> list[Session]:
    query = """
        SELECT thread_id, cwd, source_updated_at
        FROM local_thread_catalog
        WHERE host_id = 'local' AND missing_candidate = 0 AND cwd IS NOT NULL
          AND source_updated_at >= ?
    """
    try:
        connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
        try:
            rows = connection.execute(query, (cutoff,)).fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return []
    return [Session("codex", str(thread), str(cwd), float(updated)) for thread, cwd, updated in rows]


def root_repositories(roots: list[Path]) -> list[str]:
    """Each root that is a repository, and every child directory that is one."""

    found: list[str] = []
    for given in roots:
        root = given.expanduser()
        if (root / ".git").exists():
            found.append(str(root))
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / ".git").exists():
                found.append(str(child))
    return found


def _git(directory: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", directory, *args],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def resolve_checkout(directory: str) -> tuple[str, str] | None:
    """(worktree root, primary checkout) for a directory inside a repository, else None."""

    out = _git(directory, "rev-parse", "--show-toplevel", "--git-common-dir")
    if out is None:
        return None
    lines = out.splitlines()
    if len(lines) < 2:
        return None
    toplevel = os.path.realpath(lines[0])
    # The common dir is printed relative to the directory queried. A linked worktree's is
    # `<primary>/.git`; a submodule's is `<super>/.git/modules/<name>`, and for that the
    # submodule's own toplevel is the closest thing to a primary.
    common = Path(directory, lines[1]).resolve()
    primary = str(common.parent) if common.name == ".git" else toplevel
    return toplevel, primary


def worktrees_of(primary: str) -> list[dict]:
    out = _git(primary, "worktree", "list", "--porcelain")
    if out is None:
        return []
    found: list[dict] = []
    current: dict = {}
    for line in out.splitlines():
        if not line:
            if current:
                found.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = {"path": value, "branch": None, "head": None, "detached": False, "prunable": False}
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key in ("detached", "prunable"):
            current[key] = True
    if current:
        found.append(current)
    return found


def dirty_count(path: str) -> int | None:
    out = _git(path, "status", "--porcelain")
    return None if out is None else len(out.splitlines())


def _is_under(real: str, roots: list[str]) -> bool:
    return any(real == root or real.startswith(root + os.sep) for root in roots)


def _group_by_primary(
    sessions: list[Session], ignored: list[str], skipped: Skipped
) -> dict[str, dict[str, list[Session]]]:
    """{primary checkout: {worktree root: sessions}}, counting every trace that fits nowhere."""

    grouped: dict[str, dict[str, list[Session]]] = {}
    for session in sessions:
        # Temporary before missing: a sandbox that has already been deleted is still a
        # sandbox, and "missing" should mean a checkout of the person's own is gone.
        if _is_under(os.path.realpath(session.cwd), ignored):
            skipped.temporary += 1
            continue
        if not os.path.isdir(session.cwd):
            skipped.missing += 1
            continue
        resolved = resolve_checkout(session.cwd)
        if resolved is None:
            skipped.not_git += 1
            continue
        toplevel, primary = resolved
        grouped.setdefault(primary, {}).setdefault(toplevel, []).append(session)
    return grouped


def _worktree_entry(
    worktree: dict, sessions: list[Session], occupied_after: float
) -> tuple[float | None, dict]:
    sessions = sorted(sessions, key=lambda session: -session.last_activity)
    last = max((session.last_activity for session in sessions), default=None)
    occupied = any(session.live for session in sessions) or (last is not None and last >= occupied_after)
    exists = os.path.isdir(worktree["path"])
    entry = {
        **worktree,
        "exists": exists,
        "dirty": dirty_count(worktree["path"]) if exists else None,
        "sessions": [session.as_json() for session in sessions],
        "last_activity": _iso(last) if last is not None else None,
        "occupied": occupied,
    }
    return last, entry


def _repository(
    primary: str, by_worktree: dict[str, list[Session]], occupied_after: float
) -> tuple[float | None, dict]:
    listed = worktrees_of(primary) or [
        {"path": primary, "branch": None, "head": None, "detached": False, "prunable": False}
    ]
    entries: list[tuple[float | None, dict]] = []
    for worktree in listed:
        real = os.path.realpath(worktree["path"])
        entries.append(_worktree_entry(worktree, by_worktree.get(real, []), occupied_after))
    primary_real = os.path.realpath(primary)
    # The primary checkout first, then by how recently a session touched each.
    entries.sort(key=lambda item: (os.path.realpath(item[1]["path"]) != primary_real, -(item[0] or 0)))
    latest = max((last for last, _ in entries if last is not None), default=None)
    repository = {
        "primary": primary,
        "last_activity": _iso(latest) if latest is not None else None,
        "worktrees": [entry for _, entry in entries],
    }
    return latest, repository


def inventory(
    *,
    claude_config: Path,
    codex_home: Path,
    roots: list[Path],
    since_days: float,
    occupied_hours: float,
    ignored: list[str],
    claude_binary: str | None,
    now: float | None = None,
) -> dict:
    """The whole inventory as one JSON-ready document. Reads everything, writes nothing."""

    now = time.time() if now is None else now
    cutoff = now - since_days * 86400
    skipped = Skipped()
    transcripts = claude_transcripts(claude_config, cutoff, skipped)
    live = claude_live_sessions(claude_binary, now, cutoff) if claude_binary else None
    threads = codex_threads(codex_home, cutoff)
    sessions = transcripts + (live or []) + (threads or [])

    ignored_real = [os.path.realpath(path) for path in ignored]
    grouped = _group_by_primary(sessions, ignored_real, skipped)
    for repository in root_repositories(roots):
        resolved = resolve_checkout(repository)
        if resolved is not None:
            grouped.setdefault(resolved[1], {})

    occupied_after = now - occupied_hours * 3600
    repositories = [
        _repository(primary, by_worktree, occupied_after) for primary, by_worktree in grouped.items()
    ]
    repositories.sort(key=lambda item: -(item[0] or 0))
    return {
        "generated_at": _iso(now),
        "since_days": since_days,
        "occupied_hours": occupied_hours,
        "sources": {
            "claude_code": {
                "transcripts": len(transcripts),
                "live": "unavailable" if live is None else len(live),
            },
            "codex": {"threads": "unavailable" if threads is None else len(threads)},
            "roots": [str(root) for root in roots],
            "ignored_under": ignored_real,
        },
        "repositories": [repository for _, repository in repositories],
        "skipped": asdict(skipped),
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--since",
        type=float,
        default=DEFAULT_SINCE_DAYS,
        metavar="DAYS",
        help="activity window that makes a repository active (default %(default)s)",
    )
    parser.add_argument(
        "--occupied-hours",
        type=float,
        default=DEFAULT_OCCUPIED_HOURS,
        metavar="HOURS",
        help="how recent a session must be for its worktree to count as occupied (default %(default)s)",
    )
    parser.add_argument(
        "--roots",
        action="append",
        default=[],
        metavar="DIR[,DIR...]",
        help="directories whose child repositories join the inventory; repeatable",
    )
    parser.add_argument(
        "--ignore-under",
        action="append",
        default=None,
        metavar="DIR",
        help="treat checkouts under DIR as temporary; repeatable. Default: the system temp directory",
    )
    parser.add_argument(
        "--no-live", action="store_true", help="do not ask the CLI which sessions are running"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = inventory(
        claude_config=claude_config_dir(),
        codex_home=codex_home_dir(),
        roots=[Path(part) for arg in args.roots for part in arg.split(",") if part],
        since_days=args.since,
        occupied_hours=args.occupied_hours,
        ignored=args.ignore_under if args.ignore_under else default_ignored(),
        claude_binary=None if args.no_live else shutil.which("claude"),
    )
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
