#!/usr/bin/env python3
"""Reconcile Claude Code and Codex local conversation stores.

The reconciler is deliberately storage-light: transcripts are owned by their
original client, while generated transcripts and native imports are recorded in
an atomic state file.  Native Codex operations are injected so this module does
not know how Codex stores or serves tasks.
"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

try:
    from . import formats
    from .stores import SessionSource, discover_claude, discover_codex, publish_claude_index, semantic_digest
except ImportError:  # direct execution from the installed runner
    import formats  # type: ignore
    from stores import (  # type: ignore
        SessionSource,
        discover_claude,
        discover_codex,
        publish_claude_index,
        semantic_digest,
    )


@dataclass
class Paths:
    home: Path
    claude_projects: Path | None = None
    claude_desktop: Path | None = None
    codex_database: Path | None = None
    codex_sessions: Path | None = None
    state: Path | None = None
    lock: Path | None = None

    def __post_init__(self) -> None:
        self.home = Path(self.home)
        self.claude_projects = self.claude_projects or self.home / ".claude" / "projects"
        self.claude_desktop = (
            self.claude_desktop or self.home / "Library/Application Support/Claude/claude-code-sessions"
        )
        if self.codex_database is None:
            candidates = sorted((self.home / ".codex").glob("state_*.sqlite"))
            self.codex_database = candidates[-1] if candidates else self.home / ".codex" / "state_5.sqlite"
        self.codex_sessions = self.codex_sessions or self.home / ".codex" / "sessions"
        self.state = self.state or self.home / ".claude" / "handoff" / "sync-state.json"
        self.lock = self.lock or self.home / ".claude" / "handoff" / "sync-state.lock"


class Native(Protocol):
    def import_session(self, source: SessionSource) -> Any: ...
    def read_thread(self, thread_id: str) -> dict[str, Any]: ...
    def existing_imports(self) -> list[dict[str, Any]]: ...


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("sync_state_invalid")
        return value
    except FileNotFoundError:
        return {}


def _save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".sync-state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


def _source_key(kind: str, source: SessionSource) -> str:
    return f"{kind}:{source.session_id}"


def _result(result: Any) -> tuple[str | None, Path | None, bool]:
    if isinstance(result, dict):
        return (
            result.get("thread_id") or result.get("imported_thread_id"),
            Path(result["rollout_path"]) if result.get("rollout_path") else None,
            bool(result.get("changed", True)),
        )
    return (
        getattr(result, "thread_id", None),
        getattr(result, "rollout_path", None),
        bool(getattr(result, "changed", True)),
    )


def _write_lines(path: Path, lines: list[dict[str, Any]], append: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_APPEND if append else os.O_TRUNC)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "a" if append else "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def _snapshot(source: SessionSource, projects: Path, existing: str | None = None) -> SessionSource:
    sid = Path(existing).stem if existing else str(uuid.uuid4())
    destination = Path(existing) if existing else projects / "-handoff-imports" / f"{sid}.jsonl"
    staging_root = projects / "-handoff-imports"
    if staging_root.is_symlink():
        raise ValueError("invalid_snapshot_root")
    staging_root.resolve().relative_to(projects.resolve())
    destination.resolve().relative_to(staging_root.resolve())
    if destination.is_symlink() or not re.fullmatch(r"[a-f0-9-]{36}", destination.stem):
        raise ValueError("invalid_snapshot_path")
    records, _ = formats.read_jsonl(source.path)
    normalized = []
    working_directory = Path(source.cwd)
    while not working_directory.is_dir() and working_directory != working_directory.parent:
        working_directory = working_directory.parent
    for original in records:
        record = copy.deepcopy(original)
        if "sessionId" in record:
            record["sessionId"] = sid
        if "cwd" in record:
            record["cwd"] = str(working_directory)
        normalized.append(record)
    _write_lines(destination, normalized, append=False)
    return SessionSource("claude", sid, destination, str(working_directory), source.title, source.archived)


def _publish(source: SessionSource, paths: Paths, apply: bool) -> None:
    if apply:
        publish_claude_index(source, paths.claude_desktop)


def _digest(path: Path, kind: str, item: dict[str, Any]) -> str:
    """Reuse a digest when the complete file identity has not changed."""
    stat = path.stat()
    marker = [stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    if item.get("stat") == marker and isinstance(item.get("observed_digest"), str):
        return item["observed_digest"]
    value = semantic_digest(path, kind)
    item["stat"] = marker
    item["observed_digest"] = value
    return value


def _import_claude(
    source: SessionSource,
    paths: Paths,
    native: Native,
    item: dict[str, Any],
    apply: bool,
    owners: dict,
    checkpoint,
) -> dict[str, Any]:
    try:
        digest = _digest(source.path, "claude", item)
    except (OSError, ValueError) as exc:
        return {
            "status": "error",
            "direction": "claude_to_codex",
            "source": str(source.path),
            "error": str(exc),
        }
    old_digest = item.get("digest")
    item.update(path=str(source.path), title=source.title, archived=source.archived)
    if old_digest == digest and item.get("imported_thread_id"):
        _publish(source, paths, apply)
        return {"status": "unchanged", "direction": "claude_to_codex", "source": str(source.path)}
    if not apply:
        return {"status": "planned", "direction": "claude_to_codex", "source": str(source.path)}
    try:
        # An adopted registry record without its rollout cannot establish
        # whether the native task is still untouched; use a managed branch.
        import_source = source
        if item.get("force_snapshot") or (item.get("imported_thread_id") and not item.get("rollout_path")):
            if not item.get("snapshot_path"):
                item["snapshot_path"] = str(
                    paths.claude_projects / "-handoff-imports" / f"{uuid.uuid4()}.jsonl"
                )
            import_source = _snapshot(source, paths.claude_projects, item["snapshot_path"])
        checkpoint()
        thread, rollout, changed = _result(native.import_session(import_source))
        if not thread:
            raise RuntimeError("native import returned no thread id")
        native.read_thread(thread)
        if not changed:
            if not item.get("snapshot_path"):
                item["snapshot_path"] = str(
                    paths.claude_projects / "-handoff-imports" / f"{uuid.uuid4()}.jsonl"
                )
            checkpoint()
            managed = _snapshot(source, paths.claude_projects, item.get("snapshot_path"))
            import_source = managed
            thread, rollout, changed = _result(native.import_session(managed))
            if not changed and item.get("snapshot_imported"):
                # The managed snapshot itself may have been resumed. Preserve it
                # and retry this revision under a fresh immutable branch.
                item["snapshot_path"] = str(
                    paths.claude_projects / "-handoff-imports" / f"{uuid.uuid4()}.jsonl"
                )
                checkpoint()
                managed = _snapshot(source, paths.claude_projects, item["snapshot_path"])
                import_source = managed
                thread, rollout, changed = _result(native.import_session(managed))
                if not changed:
                    raise RuntimeError("managed native import remained resumed")
            if not thread:
                raise RuntimeError("managed native import returned no thread id")
            native.read_thread(thread)
            if managed.path.exists():
                item["snapshot_imported"] = True
            item["snapshot_path"] = str(managed.path)
        if not changed:
            registry_match = any(
                r.get("imported_thread_id") == thread
                and r.get("content_sha256") == hashlib.sha256(import_source.path.read_bytes()).hexdigest()
                for r in native.existing_imports()
            )
            if not registry_match:
                raise RuntimeError("native_revision_not_imported")
        if item.get("snapshot_path") == str(import_source.path):
            item["snapshot_imported"] = True
        if changed and rollout and rollout.is_file():
            owners[str(rollout)] = semantic_digest(rollout, "codex")
        item.update(
            imported_thread_id=thread,
            rollout_path=str(rollout) if rollout else None,
            rollout_digest=semantic_digest(rollout, "codex") if rollout and rollout.is_file() else None,
            digest=digest,
        )
        _publish(source, paths, apply)
        return {
            "status": "imported",
            "direction": "claude_to_codex",
            "source": str(source.path),
            "thread_id": thread,
        }
    except Exception as exc:  # isolate one source and retry next invocation
        return {
            "status": "error",
            "direction": "claude_to_codex",
            "source": str(source.path),
            "error": str(exc),
        }


def _codex_target(item: dict[str, Any], source: SessionSource, paths: Paths) -> Path:
    existing = item.get("target_path")
    slug = re.sub(r"[^a-zA-Z0-9]", "-", source.cwd)
    root = paths.claude_projects / slug
    if root.is_symlink():
        raise ValueError("invalid_target_root")
    root.resolve().relative_to(paths.claude_projects.resolve())
    if existing:
        target = Path(existing)
        target.resolve().relative_to(root.resolve())
        if target.is_symlink() or not re.fullmatch(r"[a-f0-9-]{36}", target.stem):
            raise ValueError("invalid_target_path")
        return target
    return root / f"{uuid.uuid4()}.jsonl"


def _reconcile_codex(
    source: SessionSource, paths: Paths, item: dict[str, Any], apply: bool, owners: dict, checkpoint
) -> dict[str, Any]:
    try:
        digest = _digest(source.path, "codex", item)
    except (OSError, ValueError) as exc:
        return {
            "status": "error",
            "direction": "codex_to_claude",
            "source": str(source.path),
            "error": str(exc),
        }
    target = _codex_target(item, source, paths)
    pending = item.get("pending")
    if pending and apply:
        stage = Path(pending["stage_path"]) if pending.get("stage_path") else None
        if stage and stage.exists():
            if (
                stage.is_symlink()
                or stage.parent.resolve() != target.parent.resolve()
                or not stage.name.startswith(".handoff-")
            ):
                raise ValueError("invalid_pending_stage")
            if semantic_digest(stage, "claude") != pending.get("generated_digest"):
                raise ValueError("invalid_pending_digest")
            expected = stage.read_bytes()
            current = target.read_bytes() if target.exists() else b""
            if expected.startswith(current):
                flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CREAT
                out = os.open(target, flags, 0o600)
                try:
                    if target.read_bytes() != current:
                        raise RuntimeError("target_changed_during_recovery")
                    with os.fdopen(out, "ab", closefd=False) as handle:
                        handle.write(expected[len(current) :])
                        handle.flush()
                        os.fsync(handle.fileno())
                finally:
                    os.close(out)
            else:
                # A user continued the interrupted copy. Keep it as a branch;
                # the original source gets a new target on this pass.
                item.pop("pending", None)
                item["force_branch"] = True
                stage.unlink(missing_ok=True)
                checkpoint()
        if target.is_file() and semantic_digest(target, "claude") == pending.get("generated_digest"):
            item.update(pending)
            owners[str(target)] = pending["generated_digest"]
            item.pop("pending", None)
            item.pop("stage_path", None)
            checkpoint()
            if stage:
                stage.unlink(missing_ok=True)
    old_digest = item.get("source_digest")
    generated_digest = item.get("generated_digest")
    try:
        continued = (
            target.is_file()
            and generated_digest
            and _digest(target, "claude", item.setdefault("target_observed", {})) != generated_digest
        )
    except (OSError, ValueError) as exc:
        return {
            "status": "error",
            "direction": "codex_to_claude",
            "source": str(source.path),
            "error": str(exc),
        }
    if old_digest == digest and item.get("target_path") and target.exists() and not item.get("force_branch"):
        target_source = SessionSource(
            "claude", item.get("target_session_id", ""), target, source.cwd, source.title, source.archived
        )
        _publish(target_source, paths, apply)
        return {"status": "unchanged", "direction": "codex_to_claude", "source": str(source.path)}
    records, _ = formats.read_jsonl(source.path)
    source_record_count = len(records)
    if not records:
        return {"status": "partial", "direction": "codex_to_claude", "source": str(source.path)}
    prefix_count = int(item.get("source_record_count", 0))
    prefix_hash = hashlib.sha256(json.dumps(records[:prefix_count], sort_keys=True).encode()).hexdigest()
    rewritten = prefix_count and (len(records) < prefix_count or item.get("source_prefix_sha") != prefix_hash)
    branched = bool(
        continued
        or item.get("force_branch")
        or rewritten
        or (target.exists() and old_digest and old_digest != digest and not generated_digest)
    )
    full_prefix_hash = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    if branched:
        target = _codex_target({}, source, paths)
        parent = None
        mode = False
        session_id = target.stem
    else:
        mode = target.exists()
        parent = item.get("tail") if mode else None
        records = records[int(item.get("source_record_count", 0)) :] if mode else records
    session_id = session_id if branched else (item.get("target_session_id") or target.stem)
    lines, tail = formats.codex_to_claude(records, session_id=session_id, cwd=source.cwd, parent=parent)
    if apply:
        before = target.read_bytes() if mode else b""
        if mode and generated_digest and semantic_digest(target, "claude") != generated_digest:
            raise RuntimeError("target_changed_during_sync")
        payload = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, stage_name = tempfile.mkstemp(prefix=".handoff-", dir=target.parent)
        stage = Path(stage_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(before + payload)
            generated = semantic_digest(stage, "claude")
            pending = dict(
                target_path=str(target),
                target_session_id=session_id,
                source_digest=digest,
                generated_digest=generated,
                tail=tail,
                source_record_count=source_record_count,
                source_prefix_sha=full_prefix_hash,
                title=source.title,
                archived=source.archived,
            )
            item["target_path"] = str(target)
            pending["stage_path"] = str(stage)
            item["pending"] = pending
            checkpoint()
            flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_APPEND if mode else os.O_CREAT | os.O_EXCL)
            out = os.open(target, flags, 0o600)
            try:
                if mode and target.read_bytes() != before:
                    raise RuntimeError("target_changed_during_sync")
                with os.fdopen(out, "ab", closefd=False) as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(out)
            owners[str(target)] = generated
            item.update(pending)
            item.pop("pending", None)
            item.pop("stage_path", None)
            item.pop("force_branch", None)
            checkpoint()
        finally:
            if not item.get("pending"):
                stage.unlink(missing_ok=True)
        _publish(
            SessionSource("claude", session_id, target, source.cwd, source.title, source.archived),
            paths,
            apply,
        )
    return {
        "status": "copied" if apply else "planned",
        "direction": "codex_to_claude",
        "source": str(source.path),
        "target": str(target),
        "lines": len(lines),
    }


def synchronize(paths: Paths, native: Native, apply: bool = False) -> dict[str, Any]:
    """Reconcile every visible top-level source under one process lock."""
    report: dict[str, Any] = {
        "apply": apply,
        "results": [],
        "errors": [],
        "counts": {"claude": 0, "codex": 0},
    }
    paths.lock.parent.mkdir(parents=True, exist_ok=True)
    with paths.lock.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = _load(paths.state)
            state.setdefault("claude", {})
            state.setdefault("codex", {})
            migrated = {}
            for old_key, item in state["claude"].items():
                key = old_key
                try:
                    identity = str(uuid.UUID(Path(item["path"]).stem))
                    key = "claude:" + identity
                except (KeyError, ValueError):
                    pass
                if key in migrated and migrated[key].get("path") != item.get("path"):
                    raise ValueError("duplicate_source_identity")
                migrated[key] = item
            state["claude"] = migrated
            owners_claude = state.setdefault("owned_claude", {})
            owners_codex = state.setdefault("owned_codex", {})
            owned_stats = state.setdefault("owned_stats", {})

            def checkpoint():
                if apply:
                    _save(paths.state, _jsonable(state))

            adopted = {
                str(r["source_path"]): r
                for r in native.existing_imports()
                if r.get("source_path") and r.get("imported_thread_id")
            }
            for item in state["claude"].values():
                registered_snapshot = adopted.get(item.get("snapshot_path"))
                if registered_snapshot and registered_snapshot.get("imported_thread_id") == item.get(
                    "imported_thread_id"
                ):
                    item["snapshot_imported"] = True
            claude = discover_claude(paths.claude_projects, paths.claude_desktop)
            codex = discover_codex(paths.codex_database)
            legacy = _load(paths.home / ".claude" / "handoff-state.json")
            obsolete = {
                str(pair.get("codex_rollout"))
                for pair in (legacy.get("pairs", {}) or {}).values()
                if isinstance(pair, dict) and pair.get("codex_rollout")
            }
            # Stage removed-worktree histories together, before the one native
            # discovery scan. Native detection excludes non-existing directories.
            if hasattr(native, "begin_pass"):
                native.begin_pass()
            if apply:
                for source in claude:
                    if Path(source.cwd).is_dir() or "-handoff-imports" in source.path.parts:
                        continue
                    item = state["claude"].setdefault(_source_key("claude", source), {})
                    if item.get("digest") == _digest(source.path, "claude", item):
                        continue
                    item["force_snapshot"] = True
                    item.setdefault(
                        "snapshot_path",
                        str(paths.claude_projects / "-handoff-imports" / f"{uuid.uuid4()}.jsonl"),
                    )
                    checkpoint()
                    _snapshot(source, paths.claude_projects, item["snapshot_path"])
            pending_targets = {v.get("target_path") for v in state["codex"].values() if v.get("pending")}
            for source in claude:
                if str(source.path) in pending_targets:
                    continue
                if "-handoff-imports" in source.path.parts:
                    continue
                if str(source.path) in owners_claude and owners_claude[str(source.path)] == _digest(
                    source.path, "claude", owned_stats.setdefault(str(source.path), {})
                ):
                    _publish(source, paths, apply)
                    continue
                report["counts"]["claude"] += 1
                key = _source_key("claude", source)
                item = state["claude"].setdefault(key, {})
                if not item.get("imported_thread_id") and str(source.path) in adopted:
                    imported = adopted[str(source.path)]
                    try:
                        thread = native.read_thread(imported["imported_thread_id"])
                        item["imported_thread_id"] = imported["imported_thread_id"]
                        item["rollout_path"] = thread["path"]
                        if hashlib.sha256(source.path.read_bytes()).hexdigest() == imported.get(
                            "content_sha256"
                        ):
                            item["digest"] = semantic_digest(source.path, "claude")
                        else:
                            item["force_snapshot"] = True
                    except Exception:
                        # A stale registry entry is not evidence of a usable task.
                        item.clear()
                outcome = _import_claude(source, paths, native, item, apply, owners_codex, checkpoint)
                checkpoint()
                if apply:
                    with contextlib.suppress(OSError, ValueError):
                        _publish(source, paths, apply)
                report["results"].append(outcome)
                if outcome.get("status") == "error":
                    report["errors"].append(outcome)
            for source in codex:
                if str(source.path) in obsolete:
                    continue
                if str(source.path) in owners_codex and owners_codex[str(source.path)] == _digest(
                    source.path, "codex", owned_stats.setdefault(str(source.path), {})
                ):
                    continue
                report["counts"]["codex"] += 1
                key = _source_key("codex", source)
                try:
                    outcome = _reconcile_codex(
                        source, paths, state["codex"].setdefault(key, {}), apply, owners_claude, checkpoint
                    )
                except Exception as exc:
                    outcome = {
                        "status": "error",
                        "direction": "codex_to_claude",
                        "source": str(source.path),
                        "error": type(exc).__name__,
                    }
                checkpoint()
                report["results"].append(outcome)
                if outcome.get("status") == "error":
                    report["errors"].append(outcome)
            report["unfinished"] = [
                r for r in report["results"] if r.get("status") in ("planned", "partial", "error")
            ]
            if apply:
                _save(paths.state, _jsonable(state))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return _jsonable(report)
