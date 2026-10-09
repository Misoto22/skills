"""Small, dependency-free adapters for discovering and publishing local sessions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import uuid
from collections import OrderedDict
from contextlib import closing, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SessionSource:
    kind: str
    session_id: str
    path: Path
    cwd: str
    title: str
    archived: bool = False


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CLAUDE_CACHE: OrderedDict[str, tuple[tuple[int, int, int, int], tuple[str, str, str] | None]] = OrderedDict()
_CLAUDE_CACHE_LIMIT = 2048
_INDEX_STATE: dict[str, Path | None] = {"root": None}
_INDEX_ALIASES: dict[str, list[Path]] = {}
_INDEX_DETAILS: dict[Path, dict[str, Any]] = {}


def _records(path: Path, *, tolerate_malformed: bool = True) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"session transcript does not exist: {path}")
    result: list[dict[str, Any]] = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read session transcript {path}: {exc}") from exc
    end = raw.rfind(b"\n")
    if end < 0:
        return []
    for line in raw[: end + 1].splitlines():
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if not tolerate_malformed:
                raise ValueError(f"malformed JSON in session transcript {path}") from exc
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _text(value.get("text") or value.get("content") or value.get("thinking") or "")
    if isinstance(value, list):
        return "\n".join(x for x in (_text(item) for item in value) if x)
    return ""


def _user_title(record: dict[str, Any]) -> str:
    message = record.get("message")
    if not isinstance(message, dict) or record.get("type") != "user":
        return ""
    content = message.get("content")
    if isinstance(content, list):
        content = [block for block in content if isinstance(block, dict) and block.get("type") == "text"]
    return " ".join(_text(content).split()).strip()


def _desktop_entries(desktop: Path) -> dict[str, list[tuple[float, dict[str, Any]]]]:
    _INDEX_STATE["root"] = desktop.resolve()
    _INDEX_ALIASES.clear()
    _INDEX_DETAILS.clear()
    found: dict[str, list[tuple[float, dict[str, Any]]]] = {}
    if not desktop.is_dir():
        return found
    for account in sorted(
        (p for p in desktop.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name
    ):
        for org in sorted(
            (p for p in account.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name
        ):
            for entry in sorted(org.glob("local_*.json")):
                if entry.is_symlink():
                    continue
                try:
                    data = json.loads(entry.read_text())
                except (OSError, ValueError):
                    continue
                if not isinstance(data, dict) or data.get("handoffDuplicateOf"):
                    continue
                sid = data.get("cliSessionId") or data.get("sessionId")
                if not isinstance(sid, str) or not sid:
                    continue
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                found.setdefault(sid, []).append((mtime, data))
                _INDEX_ALIASES.setdefault(sid, []).append(entry)
                _INDEX_DETAILS[entry] = data
    return found


def discover_claude(projects: Path, desktop: Path) -> list[SessionSource]:
    """Discover direct project transcripts, tolerating incomplete or bad files."""
    entries = _desktop_entries(desktop)
    result: list[SessionSource] = []
    if not projects.is_dir():
        return result
    for project in sorted(
        (p for p in projects.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name
    ):
        for path in sorted((p for p in project.glob("*.jsonl") if not p.is_symlink()), key=lambda p: p.name):
            try:
                stat = path.stat()
                marker = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            except OSError:
                continue
            key = str(path)
            cached = _CLAUDE_CACHE.get(key)
            if cached is not None and cached[0] == marker:
                metadata = cached[1]
                _CLAUDE_CACHE.move_to_end(key)
            else:
                try:
                    records = [r for r in _records(path) if r.get("isSidechain") is not True]
                except ValueError:
                    continue
                metadata = None
                if records and any(
                    r.get("type") in ("user", "assistant")
                    and isinstance(r.get("message"), dict)
                    and r["message"].get("content")
                    for r in records
                ):
                    first = next(
                        (
                            r
                            for r in records
                            if isinstance(r.get("sessionId"), str) and _ID.fullmatch(r["sessionId"])
                        ),
                        {},
                    )
                    sid = first.get("sessionId") or path.stem
                    # Forks retain parent session ids in their inherited prefix.
                    # Claude opens the UUID named by the transcript filename.
                    with suppress(ValueError):
                        sid = str(uuid.UUID(path.stem))
                    cwd = next(
                        (r.get("cwd") for r in records if isinstance(r.get("cwd"), str) and r.get("cwd")), ""
                    )
                    fallback = next((_user_title(r) for r in records if _user_title(r)), "")
                    if _ID.fullmatch(str(sid)) and cwd:
                        metadata = (str(sid), cwd, fallback or path.stem)
                _CLAUDE_CACHE[key] = (marker, metadata)
                _CLAUDE_CACHE.move_to_end(key)
                while len(_CLAUDE_CACHE) > _CLAUDE_CACHE_LIMIT:
                    _CLAUDE_CACHE.popitem(last=False)
            if metadata is None:
                continue
            sid, cwd, fallback = metadata
            latest = entries.get(sid, [])
            indexed = max(latest, key=lambda pair: pair[0], default=(0, {}))[1]
            title = indexed.get("title") if isinstance(indexed.get("title"), str) else ""
            if not title:
                title = fallback
            result.append(
                SessionSource(
                    "claude", str(sid), path, cwd, title or path.stem, bool(indexed.get("isArchived", False))
                )
            )
    return result


def discover_codex(database: Path) -> list[SessionSource]:
    """Read human, local Codex threads from SQLite without opening it writable."""
    if not database.is_file():
        return []
    uri = f"file:{database.resolve()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(threads)")}
            required = {"id", "title", "cwd", "rollout_path"}
            if not required <= columns:
                raise ValueError("Codex database has no usable threads table")
            selected = [
                name
                for name in ("id", "name", "title", "cwd", "rollout_path", "archived", "source", "agent_path")
                if name in columns
            ]
            rows = conn.execute(f"SELECT {', '.join(selected)} FROM threads").fetchall()
    except ValueError:
        raise
    except (sqlite3.Error, OSError) as exc:
        raise ValueError(f"Codex database cannot be read: {database}") from exc
    result = []
    for row in rows:
        data = dict(zip(selected, row, strict=True))
        source = data.get("source")
        if source not in (None, "", "codex", "cli", "vscode", "exec") or data.get("agent_path"):
            continue
        path = Path(str(data["rollout_path"]))
        if not path.is_absolute() or not path.is_file():
            continue
        try:
            path.resolve().relative_to(database.resolve().parent)
        except ValueError:
            continue
        sid = data.get("id")
        if not isinstance(sid, str) or not sid:
            continue
        result.append(
            SessionSource(
                "codex",
                sid,
                path,
                str(data.get("cwd") or ""),
                str(data.get("name") or data.get("title") or sid),
                bool(data.get("archived", False)),
            )
        )
    return result


def _canonical_conversation(records: list[dict[str, Any]], kind: str) -> list[Any]:
    output = []
    if kind == "claude":
        for record in records:
            if record.get("type") not in ("user", "assistant"):
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            blocks = (
                message.get("content")
                if isinstance(message.get("content"), list)
                else [message.get("content")]
            )
            for block in blocks:
                if isinstance(block, str):
                    output.append([record["type"], "text", block])
                elif isinstance(block, dict):
                    typ = block.get("type")
                    if typ in ("text", "thinking"):
                        output.append([record["type"], typ, _text(block)])
                    elif typ == "tool_use":
                        output.append(["tool", "call", block.get("name", ""), block.get("input", {})])
                    elif typ == "tool_result":
                        output.append(["tool", "result", _text(block.get("content"))])
    else:
        for record in records:
            if record.get("type") != "response_item" or not isinstance(record.get("payload"), dict):
                continue
            payload = record["payload"]
            typ = payload.get("type")
            if typ == "message" and payload.get("role") in ("user", "assistant"):
                output.append([payload["role"], "text", _text(payload.get("content"))])
            elif typ in ("function_call", "custom_tool_call"):
                output.append(
                    [
                        "tool",
                        "call",
                        payload.get("name", ""),
                        _json_value(payload.get("arguments", payload.get("input", {}))),
                    ]
                )
            elif typ in ("function_call_output", "custom_tool_call_output"):
                output.append(["tool", "result", _text(payload.get("output"))])
    return output


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def semantic_digest(path: Path, kind: str) -> str:
    if kind not in ("claude", "codex"):
        raise ValueError(f"unsupported session kind: {kind}")
    content = _canonical_conversation(_records(path, tolerate_malformed=False), kind)
    payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _write_index(target: Path, data: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".handoff-index-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary)
    _INDEX_DETAILS[target] = data


def publish_claude_index(source: SessionSource, desktop: Path) -> int:
    """Create or update one local index entry in every existing account."""
    if not _ID.fullmatch(source.session_id):
        raise ValueError(f"unsafe session id: {source.session_id!r}")
    if not source.path.is_file():
        raise ValueError(f"source transcript does not exist: {source.path}")
    accounts = (
        sorted((p for p in desktop.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name)
        if desktop.is_dir()
        else []
    )
    if not accounts:
        return 0
    if desktop.resolve() != _INDEX_STATE["root"]:
        _desktop_entries(desktop)
    aliases = [
        p
        for p in _INDEX_ALIASES.get(source.session_id, [])
        if p.is_file() and not p.is_symlink() and not _INDEX_DETAILS.get(p, {}).get("handoffDuplicateOf")
    ]
    generated_name = f"local_{source.session_id}"

    def preference(path: Path):
        return (
            not _INDEX_DETAILS.get(path, {}).get("handoffGeneratedIndex"),
            path.stem != generated_name,
            path.stat().st_mtime_ns,
        )

    canonical = max(aliases, key=preference, default=None)
    index_name = canonical.stem if canonical else generated_name
    stamp = int(source.path.stat().st_mtime * 1000)
    changed = 0
    for account in accounts:
        orgs = sorted(
            (p for p in account.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name
        )
        matching = [p for p in aliases if p.parent.parent == account]

        def activity(org: Path) -> int:
            values = []
            for entry in org.glob("local_*.json"):
                if entry.is_symlink():
                    continue
                try:
                    values.append(int(json.loads(entry.read_text()).get("lastActivityAt") or 0))
                except (OSError, TypeError, ValueError):
                    continue
            return max(values, default=0)

        target = (
            max(matching, key=preference)
            if matching
            else (orgs[0] if len(orgs) == 1 else max(orgs, key=activity, default=None))
        )
        if target is None:
            continue
        if target.is_dir():
            target = target / (index_name + ".json")
        try:
            target.resolve().relative_to(desktop.resolve())
        except ValueError as exc:
            raise ValueError(f"desktop index path escapes store: {target}") from exc
        try:
            data = json.loads(target.read_text()) if target.is_file() else {}
        except (OSError, ValueError):
            data = {}
        old = dict(data)
        if not target.is_file():
            data["handoffGeneratedIndex"] = True
        data.update(
            {
                "sessionId": target.stem,
                "cliSessionId": source.session_id,
                "cwd": source.cwd,
                "originCwd": source.cwd,
                "title": source.title,
                "createdAt": data.get("createdAt", stamp),
                "lastActivityAt": stamp,
            }
        )
        if target not in matching or "isArchived" not in data:
            data["isArchived"] = source.archived
        target.parent.mkdir(parents=True, exist_ok=True)
        if data != old:
            _write_index(target, data)
            if target not in _INDEX_ALIASES.setdefault(source.session_id, []):
                _INDEX_ALIASES[source.session_id].append(target)
            changed += 1
        # A desktop session can finish creating its index after our first scan.
        # Archive only an alias explicitly created by this runtime, preserving
        # its prior archive value so that the operation remains reversible.
        for alias in matching:
            if alias == target or not _INDEX_DETAILS.get(alias, {}).get("handoffGeneratedIndex"):
                continue
            duplicate = json.loads(alias.read_text())
            if duplicate.get("handoffDuplicateOf") or not duplicate.get("handoffGeneratedIndex"):
                continue
            duplicate["handoffPreviousArchived"] = duplicate.get("isArchived")
            duplicate["handoffDuplicateOf"] = target.stem
            duplicate["isArchived"] = True
            _write_index(alias, duplicate)
            changed += 1
    return changed
