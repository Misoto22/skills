#!/usr/bin/env python3
"""Render a plain-text email body as deterministic, escaped HTML."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


_UNORDERED_ITEM = re.compile(r"^[-*]\s+(.+)$")
_ORDERED_ITEM = re.compile(r"^\d+[.)]\s+(.+)$")


def normalize_text(text: str) -> str:
    """Normalize line endings and join hard-wrapped prose within paragraphs."""

    canonical = _canonical_text(text)
    if not canonical.strip():
        return ""

    blocks: list[str] = []
    current: list[str] = []
    for line in canonical.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(_normalize_block(current))
                current = []
            continue
        current.append(stripped)
    if current:
        blocks.append(_normalize_block(current))

    return "\n\n".join(blocks) + "\n"


def render_html(text: str, signature: str | None = None) -> str:
    """Render text as safe HTML, optionally preserving a fixed signature."""

    canonical = _canonical_text(text).strip("\n")
    signature_text: str | None = None
    main_text = canonical

    if signature is not None:
        signature_text = _normalize_fixed_text(signature)
        if not signature_text or not canonical.endswith(signature_text):
            raise ValueError("signature does not match the end of the text body")
        prefix = canonical[: -len(signature_text)]
        if prefix and not prefix.endswith("\n\n"):
            raise ValueError("signature does not match a complete final block")
        main_text = prefix.rstrip("\n")

    parts = _render_blocks(normalize_text(main_text))
    if signature_text is not None:
        escaped_lines = [html.escape(line, quote=True) for line in signature_text.split("\n")]
        parts.append(f'<div class="signature">{"<br>".join(escaped_lines)}</div>')

    body = "".join(parts)
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"></head>'
        f"<body>{body}</body></html>\n"
    )


def _canonical_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if "\x00" in text:
        raise ValueError("text contains a NUL byte")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_fixed_text(text: str) -> str:
    canonical = _canonical_text(text)
    lines = [line.rstrip() for line in canonical.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _normalize_block(lines: list[str]) -> str:
    if all(_UNORDERED_ITEM.fullmatch(line) for line in lines):
        return "\n".join(lines)
    if all(_ORDERED_ITEM.fullmatch(line) for line in lines):
        return "\n".join(lines)
    return " ".join(lines)


def _render_blocks(normalized: str) -> list[str]:
    if not normalized:
        return []
    rendered: list[str] = []
    for block in normalized.rstrip("\n").split("\n\n"):
        lines = block.split("\n")
        unordered = [_UNORDERED_ITEM.fullmatch(line) for line in lines]
        ordered = [_ORDERED_ITEM.fullmatch(line) for line in lines]
        if all(unordered):
            items = "".join(
                f"<li>{html.escape(match.group(1), quote=True)}</li>"
                for match in unordered
                if match is not None
            )
            rendered.append(f"<ul>{items}</ul>")
        elif all(ordered):
            items = "".join(
                f"<li>{html.escape(match.group(1), quote=True)}</li>"
                for match in ordered
                if match is not None
            )
            rendered.append(f"<ol>{items}</ol>")
        else:
            rendered.append(f"<p>{html.escape(block, quote=True)}</p>")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a UTF-8 plain-text email as escaped HTML.",
    )
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--signature", type=Path)
    args = parser.parse_args()

    text = args.text.read_text(encoding="utf-8")
    signature = (
        args.signature.read_text(encoding="utf-8")
        if args.signature is not None
        else None
    )
    output = render_html(text, signature)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
