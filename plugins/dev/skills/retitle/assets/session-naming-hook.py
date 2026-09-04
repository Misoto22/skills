#!/usr/bin/env python3
"""UserPromptSubmit hook: keep a Claude Code session titled `MMDD｜TYPE｜subject`.

The batch half of this skill renames conversations that already exist. This is the
live half: without it a new session keeps whichever title the client auto-generated,
and the scheme decays from the front.

Python rather than shell because a hook runs on whatever machine the skill was
installed on, and the obvious shell version needs `jq` to read the event — one more
thing to be missing. Nothing here is imported.

Reads the hook event as JSON on stdin, writes an `additionalContext` reminder as JSON
on stdout, and stays silent otherwise. Any failure exits 0 with no output: a hook that
breaks a user's prompt is worse than a session with a dull title.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

# Prompts between re-checks. A session's direction drifts, and a title set in its
# first minute goes stale, but the full rule is long enough that injecting it every
# turn would cost more context than the title is worth. Override with
# SESSION_TITLE_RECHECK_EVERY; 0 fires the full rule once and never re-checks.
DEFAULT_RECHECK_EVERY = 5
MARKER_TTL_SECONDS = 7 * 24 * 60 * 60

DEFAULT_LANG = "en"

# One vocabulary per language, and each one internally uniform in width — that is the
# whole reason the English types are five uppercase letters rather than the natural
# words. Two CJK characters are a fixed em each, so `优化` and `研究` occupy the same
# pixels and the subject starts at the same x on every row. English in a proportional
# UI font cannot reproduce that exactly, but a fixed letter count in uppercase gets
# the jitter down to about a tenth of a glyph, where `DESIGN` against `FIX` would be
# a factor of two and no column would survive it. SHIP is the one four-letter member:
# no five-letter English verb covers commit/PR/merge/tag/deploy/publish honestly, and
# a word that lies is worse than a column that is one character ragged.
SCHEMES: dict[str, dict[str, str]] = {
    "en": {
        "scheme": "MMDD｜TYPE｜subject",
        "types": "BUILD, SHAPE, PATCH, TWEAK, SHIP, PROBE, WRITE, AUDIT, STUDY",
        "fields": "TYPE and subject",
        "type_field": "TYPE",
        "body": """- TYPE: exactly one of {types} — uppercase, exactly as written
  - BUILD: new capability, new endpoint, new screen
  - SHAPE: shape decided before code — architecture, interface, layout
  - PATCH: something behaved wrongly and was corrected
  - TWEAK: behaviour was already correct; speed, cost, or clarity improved
  - SHIP: commit, PR, merge, tag, deploy, publish
  - PROBE: tried something to find out what happens; no committed outcome
  - WRITE: README, comments, guides, changelogs
  - AUDIT: checked something that already exists against a standard and reported the gaps; nothing built
  - STUDY: read the outside world to answer a question; nothing built and nothing of the user's inspected

AUDIT and STUDY both end in a report. The line is the object: AUDIT inspects something the user already owns (a repository, a deployment, a page, a configuration), STUDY reads the outside world. "Audit the site's SEO" is AUDIT; "which SEO tools are worth using" is STUDY.
- subject: what the session is actually about, in two to four lowercase words and at most 24 characters — English runs about two and a half times wider than Chinese for the same meaning, and it is the subject that gets truncated in a narrow sidebar, not the type. Name the object, not the activity (batch text rendering, not fixed some display issues). Do not repeat the project or repository name — the sidebar already groups by project.

Examples: 0903｜TWEAK｜batch text rendering · 0902｜BUILD｜unified shortcut page · 0813｜SHIP｜push code to github""",
    },
    "zh": {
        "scheme": "MMDD｜类型｜主题",
        "types": "功能, 设计, 修复, 优化, 发布, 探索, 文档, 审计, 研究",
        "fields": "类型 and 主题",
        "type_field": "类型",
        "body": """- 类型: exactly one of {types}
  - 功能: new capability, new endpoint, new screen
  - 设计: shape decided before code — architecture, interface, layout
  - 修复: something behaved wrongly and was corrected
  - 优化: behaviour was already correct; speed, cost, or clarity improved
  - 发布: commit, PR, merge, tag, deploy, publish
  - 探索: tried something to find out what happens; no committed outcome
  - 文档: README, comments, guides, changelogs
  - 审计: checked something that already exists against a standard and reported the gaps; nothing built
  - 研究: read the outside world to answer a question; nothing built and nothing of the user's inspected

审计 and 研究 both end in a report. The line is the object: 审计 inspects something the user already owns (a repository, a deployment, a page, a configuration), 研究 reads the outside world. "Audit the site's SEO" is 审计; "which SEO tools are worth using" is 研究.
- 主题: what the session is actually about, roughly 4-12 characters. Name the object, not the activity (批次文字显示, not 处理了一些显示问题). Do not repeat the project or repository name — the sidebar already groups by project.

Examples: 0903｜优化｜批次文字显示 · 0902｜功能｜整合快捷键提示页 · 0813｜发布｜提交代码到GitHub""",
    },
}

FULL_RULE = """Session naming rule: once you understand this session's primary task (usually after your first substantive response, sooner if obvious), call mcp__ccd_session_mgmt__set_session_title once with session_id: "self" to set this session's title. Do this silently, without announcing it to the user.

session_id is required, and "self" is the only value that names the session you are in. Omitting it fails validation, and the session id in your own transcript path or scratchpad path is a different id — passing that one answers "Session ... not found" and the title is left as the client generated it.

Format: "{scheme}" — for this session, MMDD is {mmdd}.

The separator is the fullwidth vertical line ｜ (U+FF5C), not the ASCII pipe |. No spaces around it.

{body}

If the task fits none of the nine types, pick the closest one rather than inventing a tenth."""

RECHECK = """Title re-check: if this session's work has moved away from what its current title says, call mcp__ccd_session_mgmt__set_session_title again with session_id: "self" — keep MMDD as {mmdd} (the date the session started), and change {fields} to match where the work actually went. {type_field} is one of {types}.

Only retitle on a real change of subject, not on a new step within the same task — a title that changes every few messages is worse than one that is slightly stale. If the current title still fits, do nothing, and either way do not mention this to the user."""


def _recheck_every() -> int:
    raw = os.environ.get("SESSION_TITLE_RECHECK_EVERY", "")
    return int(raw) if raw.isdigit() else DEFAULT_RECHECK_EVERY


def _scheme() -> dict[str, str]:
    """The vocabulary to name sessions in, English unless SESSION_TITLE_LANG says otherwise.

    Matched on prefix so `zh-CN` and `zh_Hans` land where the user meant. An
    unrecognised value falls back to the default rather than failing: the hook's job is
    to inject a rule, and a rule in the wrong language still beats no rule at all.
    """
    raw = os.environ.get("SESSION_TITLE_LANG", "").strip().lower()
    for lang in SCHEMES:
        if raw.startswith(lang):
            return SCHEMES[lang]
    return SCHEMES[DEFAULT_LANG]


def _session_mmdd(event: dict) -> str:
    """The date the session opened, not today.

    A re-check can fire days after a session started, and a session can simply run past
    midnight. Resolving `MMDD` as "now" on every firing rewrites the date to whichever day
    the reminder happened to land on — which destroys the one thing the scheme orders by,
    and does it silently, because the title still looks well-formed.

    The transcript's first timestamped record is when the session began, so read that and
    fall back to today only when there is no transcript to read.
    """
    path = event.get("transcript_path")
    if isinstance(path, str) and path:
        with (
            contextlib.suppress(OSError, ValueError, json.JSONDecodeError),
            open(path, encoding="utf-8") as handle,
        ):
            for line in handle:
                stamp = json.loads(line).get("timestamp")
                if isinstance(stamp, str) and stamp:
                    parsed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                    return parsed.astimezone().strftime("%m%d")
    return time.strftime("%m%d")


def _marker_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / ".session-naming-markers"


def _prune(directory: Path) -> None:
    """Drop markers for sessions nobody will return to, so the directory stays flat."""
    cutoff = time.time() - MARKER_TTL_SECONDS
    for path in directory.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def _bump(marker: Path) -> int:
    """Return this session's prompt count, treating anything unreadable as the first.

    An empty marker is what the earlier fire-once version of this hook left behind, so
    it has to read as 0 and upgrade in place rather than crashing a live session.
    """
    try:
        count = int(marker.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        count = 0
    count += 1
    with contextlib.suppress(OSError):
        marker.write_text(str(count), encoding="utf-8")
    return count


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0

    session_id = event.get("session_id") or event.get("transcript_path") or ""
    if not isinstance(session_id, str) or not session_id:
        return 0

    directory = _marker_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _prune(directory)
    except OSError:
        return 0

    count = _bump(directory / re.sub(r"[^A-Za-z0-9._-]", "_", session_id))

    every = _recheck_every()
    # Resolved here rather than by the model, and from the transcript rather than the
    # clock — see _session_mmdd.
    fields = dict(_scheme(), mmdd=_session_mmdd(event))
    if count == 1:
        context = FULL_RULE.format(**dict(fields, body=fields["body"].format(**fields)))
    elif every > 0 and count % every == 1:
        context = RECHECK.format(**fields)
    else:
        return 0

    json.dump(
        {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}},
        sys.stdout,
        ensure_ascii=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
