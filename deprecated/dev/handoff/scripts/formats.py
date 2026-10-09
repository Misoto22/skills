#!/usr/bin/env python3
"""Translate between Claude Code's transcript and Codex's rollout.

Both tools append one JSON object per line and both record the same six things:
a user turn, an assistant turn, the model's reasoning, a tool call, its output,
and a header naming the working directory. They disagree on every field name.

    Claude Code                          Codex
    --------------------------------     ------------------------------------
    (no header; cwd on every line)       session_meta, first line only
    type:user, message.content           response_item/message role=user
    type:assistant, content[text]        response_item/message role=assistant
    content[thinking]                    response_item/reasoning
    content[tool_use]                    response_item/function_call
    type:user, content[tool_result]      response_item/function_call_output
    parentUuid linked list               file order, turn_id on each item

What does not survive the trip is stated where it is dropped. A mirrored
conversation is a readable record of what happened, not a byte-exact replay:
Codex encrypts its reasoning and Claude signs its thinking blocks, and neither
signature is reconstructible from the other side's text.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

CODEX_ROLE_OF = {"user": "user", "assistant": "assistant"}


def read_jsonl(path, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    """Read whole JSON lines from `offset`, returning them and the new offset.

    A hook fires while the other tool is still writing, so the last line is
    routinely half-written. Stopping at the last newline and reporting that
    offset means the partial line is read whole on the next call instead of
    being parsed as garbage or skipped.
    """
    with open(path, "rb") as handle:
        handle.seek(offset)
        chunk = handle.read()
    end = chunk.rfind(b"\n")
    if end < 0:
        return [], offset
    records = []
    for line in chunk[: end + 1].splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records, offset + end + 1


def _text_of(content: Any) -> str:
    """Flatten either side's content field to the text a reader would see."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        parts.append(block.get("text") or block.get("thinking") or "")
    return "\n".join(p for p in parts if p)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def claude_to_codex(records: list[dict[str, Any]], turn_id: str) -> Iterator[dict[str, Any]]:
    """Yield Codex rollout lines for a run of Claude Code transcript lines."""
    for record in records:
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        role = CODEX_ROLE_OF.get(record.get("type") or "")
        if role is None:
            continue
        content = message.get("content")
        if isinstance(content, str):
            yield _codex_message(role, content, turn_id)
            continue
        for block in content if isinstance(content, list) else []:
            item = _codex_item(block, role, turn_id)
            if item is not None:
                yield item


def _codex_message(role: str, text: str, turn_id: str) -> dict[str, Any]:
    kind = "input_text" if role == "user" else "output_text"
    return _response_item(
        {
            "type": "message",
            "id": f"msg_{uuid.uuid4()}",
            "role": role,
            "content": [{"type": kind, "text": text}],
        },
        turn_id,
    )


def _codex_item(block: dict[str, Any], role: str, turn_id: str) -> dict[str, Any] | None:
    """One Claude content block as one Codex response_item, or None to drop it."""
    kind = block.get("type")
    if kind == "text":
        return _codex_message(role, block.get("text") or "", turn_id)
    if kind == "thinking":
        # The signature cannot travel: Codex encrypts reasoning under its own key.
        # Carrying the text as a summary keeps the record readable and honest.
        return _response_item(
            {
                "type": "reasoning",
                "id": f"rs_{uuid.uuid4()}",
                "summary": [{"type": "summary_text", "text": block.get("thinking") or ""}],
            },
            turn_id,
        )
    if kind == "tool_use":
        return _response_item(
            {
                "type": "function_call",
                "id": f"fc_{uuid.uuid4()}",
                "call_id": block.get("id") or f"call_{uuid.uuid4()}",
                "name": block.get("name") or "tool",
                "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
            },
            turn_id,
        )
    if kind == "tool_result":
        return _response_item(
            {
                "type": "function_call_output",
                "id": f"fco_{uuid.uuid4()}",
                "call_id": block.get("tool_use_id") or "",
                "output": _text_of(block.get("content")),
            },
            turn_id,
        )
    return None


def _response_item(payload: dict[str, Any], turn_id: str) -> dict[str, Any]:
    payload["internal_chat_message_metadata_passthrough"] = {"turn_id": turn_id}
    return {"timestamp": _now(), "type": "response_item", "payload": payload}


def codex_session_meta(thread_id: str, cwd: str, originator: str) -> dict[str, Any]:
    """The header Codex requires as a rollout's first line."""
    return {
        "timestamp": _now(),
        "type": "session_meta",
        "payload": {
            "id": thread_id,
            "session_id": thread_id,
            "timestamp": _now(),
            "cwd": cwd,
            "originator": originator,
            "cli_version": "handoff",
            "source": "handoff",
            "model_provider": "anthropic",
        },
    }


CLAUDE_TYPE_OF = {"user": "user", "assistant": "assistant"}


def codex_to_claude(
    records: list[dict[str, Any]],
    *,
    session_id: str,
    cwd: str,
    parent: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Turn Codex rollout lines into Claude transcript lines.

    Claude threads its transcript as a linked list, so each line has to name the
    one before it. The caller keeps the last uuid between runs and gets the new
    tail back, which is what lets a hook append to a conversation it did not start.
    """
    lines = []
    for record in records:
        if record.get("type") != "response_item":
            continue
        block = _claude_block(record.get("payload") or {})
        if block is None:
            continue
        kind, message = block
        node = str(uuid.uuid4())
        lines.append(
            {
                "parentUuid": parent,
                "isSidechain": False,
                "type": kind,
                "userType": "external",
                "cwd": cwd,
                "sessionId": session_id,
                "version": "handoff",
                "gitBranch": "",
                "uuid": node,
                "timestamp": record.get("timestamp") or _now(),
                "message": message,
            }
        )
        parent = node
    return lines, parent


def _claude_block(payload: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """One Codex response_item as a Claude message, or None to drop it."""
    kind = payload.get("type")
    if kind == "message":
        role = payload.get("role")
        if role not in CLAUDE_TYPE_OF:
            return None  # 'developer' carries Codex's own prompt, not the conversation
        text = _text_of(payload.get("content"))
        return role, {"role": role, "content": [{"type": "text", "text": text}]}
    if kind in ("function_call", "custom_tool_call"):
        raw = payload.get("arguments") if kind == "function_call" else payload.get("input")
        return "assistant", {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": payload.get("call_id") or f"call_{uuid.uuid4()}",
                    "name": payload.get("name") or "tool",
                    "input": _as_input(raw),
                }
            ],
        }
    if kind in ("function_call_output", "custom_tool_call_output"):
        return "user", {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": payload.get("call_id") or "",
                    "content": _text_of(payload.get("output")),
                }
            ],
        }
    # 'reasoning' is dropped when Codex left only encrypted_content: a thinking
    # block Claude cannot verify is worse than no thinking block at all.
    if kind == "reasoning" and payload.get("summary"):
        return "assistant", {
            "role": "assistant",
            "content": [{"type": "text", "text": _text_of(payload["summary"])}],
        }
    return None


def _as_input(raw: Any) -> dict[str, Any]:
    """Codex sends tool arguments as a JSON string; Claude wants the object."""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {"raw": raw}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}
