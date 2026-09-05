#!/usr/bin/env python3
"""Mirror a live conversation into the other agent's history, as it happens.

Claude Code and Codex both fire hooks on the same events under the same schema,
and both append their history as JSON lines. So each side can watch its own
transcript grow and write the same exchange into the other side's format, which
is what lets you close one tool, open the other, and find the conversation there.

A mirror is always a NEW conversation on the receiving side. Appending into a
history the other tool has open would race its own writer, and a corrupted
transcript costs more than a duplicated one. The mirror keeps its own id, and
the pairing plus a byte watermark per side lives in the state file, so a hook
that fires two hundred times writes each exchange once.

    handoff.py mirror --from=claude   # hook entrypoint; never fails the parent
    handoff.py mirror --from=codex
    handoff.py install                # register the hooks on both sides
    handoff.py status                 # what is paired, and how far each has got
    handoff.py uninstall
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats

STATE_PATH = Path("~/.claude/handoff-state.json").expanduser()
CODEX_SESSIONS = Path("~/.codex/sessions").expanduser()
CLAUDE_PROJECTS = Path("~/.claude/projects").expanduser()
CLAUDE_HOOKS = Path("~/.claude/settings.json").expanduser()
CODEX_HOOKS = Path("~/.codex/hooks.json").expanduser()
DESKTOP_SESSIONS = Path("~/Library/Application Support/Claude/claude-code-sessions").expanduser()
DESKTOP_CONFIG = Path("~/Library/Application Support/Claude/config.json").expanduser()
HOOK_EVENTS = ("PostToolUse", "Stop")


def load_state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {"pairs": {}}
    return data if isinstance(data, dict) and "pairs" in data else {"pairs": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_PATH)


def hook_payload() -> dict[str, Any]:
    """What the hook was told, from stdin JSON with an environment fallback.

    Both tools pass a JSON object on stdin. A hook invoked by hand, or by a
    version that only sets environment variables, still has to work, so an empty
    or unparseable stdin is a missing field rather than a crash.
    """
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except OSError:
            raw = ""
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    for key, env in (("session_id", "CLAUDE_SESSION_ID"), ("cwd", "CLAUDE_PROJECT_DIR")):
        payload.setdefault(key, os.environ.get(env) or "")
    return payload


def slug_for(cwd: str) -> str:
    """Claude Code files a transcript under a slug of its working directory."""
    return "-" + cwd.strip("/").replace("/", "-").replace(".", "-").replace("_", "-")


def rollout_path(thread_id: str, when: datetime) -> Path:
    stamp = when.strftime("%Y-%m-%dT%H-%M-%S")
    directory = CODEX_SESSIONS / when.strftime("%Y/%m/%d")
    return directory / f"rollout-{stamp}-{thread_id}.jsonl"


def append_lines(path: Path, lines: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def pair_for(state: dict[str, Any], key: str, cwd: str) -> dict[str, Any]:
    """The mirror record for one conversation, created on first sight."""
    pairs = state["pairs"]
    if key not in pairs:
        pairs[key] = {
            "cwd": cwd,
            "codex_thread": str(uuid.uuid4()),
            "claude_session": str(uuid.uuid4()),
            "source_offset": 0,
            "claude_tail": None,
            "started": datetime.now().isoformat(timespec="seconds"),
        }
    return pairs[key]


def mirror_from_claude(payload: dict[str, Any], state: dict[str, Any]) -> str:
    """Append this Claude conversation's new lines to its Codex mirror."""
    transcript = payload.get("transcript_path") or ""
    session = payload.get("session_id") or ""
    cwd = payload.get("cwd") or ""
    if not transcript or not Path(transcript).is_file():
        return "no transcript in the hook payload"
    pair = pair_for(state, f"claude:{session}", cwd)
    records, offset = formats.read_jsonl(transcript, pair["source_offset"])
    if not records:
        return "nothing new"
    target = Path(pair.get("codex_rollout") or "")
    if not target.name:
        target = rollout_path(pair["codex_thread"], datetime.now())
        pair["codex_rollout"] = str(target)
        append_lines(target, [formats.codex_session_meta(pair["codex_thread"], cwd, "Claude Code")])
    lines = list(formats.claude_to_codex(records, turn_id=pair["codex_thread"]))
    append_lines(target, lines)
    pair["source_offset"] = offset
    return f"{len(lines)} items -> {target.name}"


def mirror_from_codex(payload: dict[str, Any], state: dict[str, Any]) -> str:
    """Append this Codex thread's new lines to its Claude mirror."""
    cwd = payload.get("cwd") or ""
    source = payload.get("rollout_path") or newest_rollout(cwd)
    if not source or not Path(source).is_file():
        return "no rollout to read"
    pair = pair_for(state, f"codex:{Path(source).name}", cwd)
    records, offset = formats.read_jsonl(source, pair["source_offset"])
    if not records:
        return "nothing new"
    target = CLAUDE_PROJECTS / slug_for(cwd) / f"{pair['claude_session']}.jsonl"
    lines, tail = formats.codex_to_claude(
        records, session_id=pair["claude_session"], cwd=cwd, parent=pair["claude_tail"]
    )
    if lines:
        append_lines(target, lines)
        write_index_entry(pair, cwd)
    pair["source_offset"] = offset
    pair["claude_tail"] = tail
    return f"{len(lines)} lines -> {target.name}"


def newest_rollout(cwd: str) -> str | None:
    """The rollout Codex is most likely writing right now.

    The hook payload does not name it, so this falls back to the most recently
    modified rollout that declares this working directory. It is a guess, and a
    wrong guess mirrors the wrong conversation — which is why the pairing is
    keyed by the file it actually read, not by the directory.
    """
    best: tuple[float, str] | None = None
    for path in CODEX_SESSIONS.rglob("rollout-*.jsonl"):
        try:
            head = json.loads(path.open().readline())
        except (OSError, ValueError):
            continue
        if (head.get("payload") or {}).get("cwd") != cwd:
            continue
        stamp = path.stat().st_mtime
        if best is None or stamp > best[0]:
            best = (stamp, str(path))
    return best[1] if best else None


def write_index_entry(pair: dict[str, Any], cwd: str) -> None:
    """Put the mirror in the desktop sidebar, which reads its own index.

    Writing the transcript alone is what the existing converters do, and it is
    why their output never appears: the app lists conversations from this index,
    not from ~/.claude/projects. The entry is refreshed on every mirror so the
    conversation sorts by when it was last active.
    """
    account = desktop_account()
    if account is None:
        return
    entry = account / f"local_{pair['claude_session']}.json"
    now = int(datetime.now().timestamp() * 1000)
    body = {
        "sessionId": f"local_{pair['claude_session']}",
        "cliSessionId": pair["claude_session"],
        "cwd": cwd,
        "originCwd": cwd,
        "createdAt": pair.get("index_created") or now,
        "lastActivityAt": now,
        "isArchived": False,
        "title": pair.get("title") or f"Codex · {Path(cwd).name}",
        "titleSource": "tool",
        "previousTitles": [],
    }
    pair["index_created"] = body["createdAt"]
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(json.dumps(body, separators=(",", ":")))


def desktop_account() -> Path | None:
    """The account and org directory the desktop app is currently writing."""
    try:
        account = json.loads(DESKTOP_CONFIG.read_text()).get("lastKnownAccountUuid")
    except (OSError, ValueError):
        return None
    root = DESKTOP_SESSIONS / str(account)
    if not root.is_dir():
        return None
    orgs = [d for d in root.iterdir() if d.is_dir()]
    if not orgs:
        return None
    return max(orgs, key=lambda d: d.stat().st_mtime)


def hook_command(direction: str) -> str:
    return f"{sys.executable} {Path(__file__).resolve()} mirror --from={direction} >/dev/null 2>&1 || true"


def register(config: Path, direction: str, remove: bool) -> str:
    """Add or drop this skill's hook entries in one tool's hook configuration.

    Both tools read the same shape, so one writer serves both. Only entries whose
    command names this script are touched; anything else in the file is another
    hook someone installed on purpose and is left exactly as it was.
    """
    try:
        data = json.loads(config.read_text()) if config.is_file() else {}
    except ValueError:
        return f"{config} is not valid JSON — left alone"
    hooks = data.setdefault("hooks", {})
    marker = str(Path(__file__).resolve())
    dropped = added = 0
    for event in HOOK_EVENTS:
        entries = [e for e in hooks.get(event, []) if isinstance(e, dict)]
        kept = [e for e in entries if marker not in json.dumps(e)]
        dropped += len(entries) - len(kept)
        if not remove:
            kept.append({"hooks": [{"type": "command", "command": hook_command(direction)}]})
            added += 1
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if remove:
        return f"{config.name}: {dropped} removed"
    return f"{config.name}: {added} written, {dropped} replaced"


def cmd_mirror(args: argparse.Namespace) -> int:
    """The hook entrypoint. It reports nothing and fails nothing.

    A hook that writes to stdout is read as feedback by the agent that ran it,
    and a hook that exits non-zero can stop a turn. Mirroring is bookkeeping;
    it has no business doing either, so every failure is swallowed here and
    surfaced through `status` instead.
    """
    try:
        state = load_state()
        payload = hook_payload()
        if args.source == "claude":
            note = mirror_from_claude(payload, state)
        else:
            note = mirror_from_codex(payload, state)
        state["last"] = {"at": datetime.now().isoformat(timespec="seconds"), "note": note}
        save_state(state)
    except Exception as error:
        try:
            state = load_state()
            state["last"] = {"at": datetime.now().isoformat(timespec="seconds"), "error": repr(error)}
            save_state(state)
        except OSError:
            pass
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    print(register(CLAUDE_HOOKS, "claude", remove=args.remove))
    print(register(CODEX_HOOKS, "codex", remove=args.remove))
    if args.remove:
        print("Mirrors already written are left in place; delete them yourself if you want them gone.")
    else:
        print("Codex trusts a hook by hash — the first Codex session after this asks you to approve it.")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    state = load_state()
    pairs = state.get("pairs") or {}
    print(f"Handoff state {STATE_PATH}")
    print(f"  {len(pairs)} conversation(s) mirrored")
    for key, pair in sorted(pairs.items(), key=lambda kv: kv[1].get("started") or "", reverse=True)[:10]:
        side = "Claude → Codex" if key.startswith("claude:") else "Codex → Claude"
        print(f"  {side}  {pair.get('started', '?')}  {Path(pair.get('cwd') or '?').name}")
        print(f"      read {pair.get('source_offset', 0)} bytes of source")
    last = state.get("last")
    if last:
        print(f"  last run {last.get('at')}: {last.get('note') or last.get('error')}")
    for config, direction in ((CLAUDE_HOOKS, "claude"), (CODEX_HOOKS, "codex")):
        installed = config.is_file() and str(Path(__file__).resolve()) in config.read_text()
        print(f"  hooks in {config.name}: {'installed' if installed else 'not installed'} ({direction})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    mirror = sub.add_parser("mirror", help="hook entrypoint: copy new lines to the other side")
    mirror.add_argument("--from", dest="source", choices=("claude", "codex"), required=True)
    mirror.set_defaults(run=cmd_mirror)
    install = sub.add_parser("install", help="register the hooks on both sides")
    install.add_argument("--remove", action="store_true", help=argparse.SUPPRESS)
    install.set_defaults(run=cmd_install)
    uninstall = sub.add_parser("uninstall", help="drop this skill's hook entries from both sides")
    uninstall.set_defaults(run=cmd_install, remove=True)
    sub.add_parser("status", help="what is paired and whether the hooks are registered").set_defaults(
        run=cmd_status
    )
    args = parser.parse_args()
    if not hasattr(args, "remove"):
        args.remove = False
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
