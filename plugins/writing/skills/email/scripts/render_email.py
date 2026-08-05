#!/usr/bin/env python3
"""Render a plain-text email body as deterministic, escaped HTML."""

from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path
from typing import Mapping

try:  # pragma: no cover - both import styles are exercised by the test suite
    from .email_policy import discover_policy, load_policy
except ImportError:  # pragma: no cover
    from email_policy import discover_policy, load_policy


_UNORDERED_ITEM = re.compile(r"^[-*]\s+(.+)$")
_ORDERED_ITEM = re.compile(r"^\d+[.)]\s+(.+)$")
_TABLE_ROW = re.compile(r"^\|.*\|$")
_TABLE_DIVIDER_CELL = re.compile(r"^:?-{3,}:?$")
# Closed vocabulary. An unrecognized marker stays literal text, so message
# content can never introduce a colour the policy did not authorize.
_STATUS_MARKER = re.compile(r"^\[!(ok|warn|bad)\]\s*(.*)$", re.DOTALL)


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


def render_html(
    text: str,
    signature: str | None = None,
    style: Mapping[str, object] | None = None,
) -> str:
    """Render text as safe HTML, optionally preserving a fixed signature.

    `style` is a validated policy style profile. Without one the output is bare
    semantic HTML, which is what every bundle validated before the style layer
    existed. Style tokens are read only from the profile, never from the
    message, so no message content can reach a `style` attribute.
    """

    canonical_body = normalize_body(text, signature).rstrip("\n")
    signature_text: str | None = None
    main_text = canonical_body

    if signature is not None:
        signature_text = _normalize_fixed_text(signature)
        main_text = canonical_body[: -len(signature_text)].rstrip("\n")

    parts = _render_blocks(normalize_text(main_text), style)
    if signature_text is not None:
        escaped_lines = [html.escape(line, quote=True) for line in signature_text.split("\n")]
        attributes = _block_attributes(style, first=not parts)
        parts.append(
            f'<div class="signature"{attributes}>{"<br>".join(escaped_lines)}</div>'
        )

    body = "".join(parts)
    if style is not None:
        body = f'<div style="{_container_style(style)}">{body}</div>'
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"></head>'
        f"<body>{body}</body></html>\n"
    )


def normalize_body(text: str, signature: str | None = None) -> str:
    """Return canonical sendable text while preserving a configured signature."""

    canonical = _canonical_text(text).strip("\n")
    if signature is None:
        return normalize_text(canonical)

    signature_text = _normalize_fixed_text(signature)
    if not signature_text or not canonical.endswith(signature_text):
        raise ValueError("signature does not match the end of the text body")
    prefix = canonical[: -len(signature_text)]
    if prefix and not prefix.endswith("\n\n"):
        raise ValueError("signature does not match a complete final block")
    normalized_main = normalize_text(prefix.rstrip("\n")).rstrip("\n")
    if normalized_main:
        return f"{normalized_main}\n\n{signature_text}\n"
    return f"{signature_text}\n"


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
    # Lists and tables are line-structured; joining them as prose would destroy
    # the structure the renderer is about to read back out.
    if all(_UNORDERED_ITEM.fullmatch(line) for line in lines):
        return "\n".join(lines)
    if all(_ORDERED_ITEM.fullmatch(line) for line in lines):
        return "\n".join(lines)
    if _is_table(lines):
        return "\n".join(lines)
    return " ".join(lines)


def _is_table(lines: list[str]) -> bool:
    """Report whether a block is a pipe table with a header divider row."""

    if len(lines) < 2 or not all(_TABLE_ROW.fullmatch(line) for line in lines):
        return False
    divider = _split_row(lines[1])
    return bool(divider) and all(
        _TABLE_DIVIDER_CELL.fullmatch(cell) for cell in divider
    )


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _render_blocks(
    normalized: str,
    style: Mapping[str, object] | None,
) -> list[str]:
    if not normalized:
        return []
    rendered: list[str] = []
    for block in normalized.rstrip("\n").split("\n\n"):
        lines = block.split("\n")
        first = not rendered
        unordered = [_UNORDERED_ITEM.fullmatch(line) for line in lines]
        ordered = [_ORDERED_ITEM.fullmatch(line) for line in lines]
        if _is_table(lines):
            rendered.append(_render_table(lines, style, first))
        elif all(unordered) or all(ordered):
            matches = unordered if all(unordered) else ordered
            rendered.extend(_render_list(lines, matches, style, first))
        else:
            attributes = _block_attributes(style, first)
            rendered.append(f"<p{attributes}>{html.escape(block, quote=True)}</p>")
    return rendered


def _render_list(
    lines: list[str],
    matches: list[re.Match[str] | None],
    style: Mapping[str, object] | None,
    first: bool,
) -> list[str]:
    if style is not None and style.get("list_style") == "paragraph":
        # Some webmail composers mangle list indentation when HTML is pasted in.
        # Paragraph mode keeps each authored line intact as its own block.
        return [
            f"<p{_block_attributes(style, first and index == 0)}>"
            f"{html.escape(line, quote=True)}</p>"
            for index, line in enumerate(lines)
        ]
    tag = "ul" if _UNORDERED_ITEM.fullmatch(lines[0]) else "ol"
    items = "".join(
        f"<li>{html.escape(match.group(1), quote=True)}</li>"
        for match in matches
        if match is not None
    )
    return [f"<{tag}{_list_attributes(style, first)}>{items}</{tag}>"]


def _render_table(
    lines: list[str],
    style: Mapping[str, object] | None,
    first: bool,
) -> str:
    header = _split_row(lines[0])
    body_rows = [_split_row(line) for line in lines[2:]]

    head_cells = "".join(_render_cell(cell, "th", style) for cell in header)
    parts = [f"<thead><tr>{head_cells}</tr></thead>"]
    if body_rows:
        rows = "".join(
            "<tr>" + "".join(_render_cell(cell, "td", style) for cell in row) + "</tr>"
            for row in body_rows
        )
        parts.append(f"<tbody>{rows}</tbody>")
    return f"<table{_table_attributes(style, first)}>{''.join(parts)}</table>"


def _render_cell(cell: str, tag: str, style: Mapping[str, object] | None) -> str:
    text, colour = _split_status_marker(cell, style)
    content = html.escape(text, quote=True)
    if colour is not None:
        content = f'<span style="color:{colour}">{content}</span>'
    return f"<{tag}{_cell_attributes(style, tag)}>{content}</{tag}>"


def _split_status_marker(
    cell: str,
    style: Mapping[str, object] | None,
) -> tuple[str, str | None]:
    """Strip a recognized status marker and resolve its configured colour."""

    match = _STATUS_MARKER.fullmatch(cell)
    if match is None:
        return cell, None
    text = match.group(2)
    if style is None:
        return text, None
    status_colors = style.get("status_colors")
    if not isinstance(status_colors, Mapping):
        return text, None
    colour = status_colors.get(match.group(1))
    return text, colour if isinstance(colour, str) else None


def _container_style(style: Mapping[str, object]) -> str:
    return ";".join(
        (
            f"font-family:{style['font_family']}",
            f"font-size:{style['font_size_px']}px",
            f"line-height:{style['line_height']}",
            f"color:{style['text_color']}",
        )
    )


def _block_attributes(style: Mapping[str, object] | None, first: bool) -> str:
    if style is None:
        return ""
    declarations = "margin:0"
    if not first:
        declarations += f";margin-top:{style['paragraph_spacing_px']}px"
    return f' style="{declarations}"'


def _list_attributes(style: Mapping[str, object] | None, first: bool) -> str:
    if style is None:
        return ""
    declarations = "margin:0;padding-left:20px"
    if not first:
        declarations += f";margin-top:{style['paragraph_spacing_px']}px"
    return f' style="{declarations}"'


def _table_attributes(style: Mapping[str, object] | None, first: bool) -> str:
    if style is None:
        return ""
    table = style["table"]
    declarations = f"border-collapse:collapse;font-size:{table['font_size_px']}px"
    if not first:
        declarations += f";margin-top:{style['paragraph_spacing_px']}px"
    return f' style="{declarations}"'


def _cell_attributes(style: Mapping[str, object] | None, tag: str) -> str:
    if style is None:
        return ""
    table = style["table"]
    vertical, horizontal = table["cell_padding_px"]
    declarations = (
        f"border:1px solid {table['border_color']};"
        f"padding:{vertical}px {horizontal}px"
    )
    if tag == "th":
        declarations += ";text-align:left"
    return f' style="{declarations}"'


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a UTF-8 plain-text email as escaped HTML.",
    )
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument(
        "--policy",
        type=Path,
        help="Policy supplying the style profile; omit for normal discovery.",
    )
    args = parser.parse_args()

    text = args.text.read_text(encoding="utf-8")
    signature = (
        args.signature.read_text(encoding="utf-8")
        if args.signature is not None
        else None
    )
    policy = load_policy(discover_policy(args.policy, Path.cwd(), os.environ))
    output = render_html(text, signature, policy["style"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
