"""Render a validated poster payload into one self-contained ink-wash HTML file.

The reading skill supplies data only. Every visual decision lives in the
template, so a model can never widen a column, invent a colour, or drop the
limitation footer. Placeholder values are HTML-escaped on the way in.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SECTION = re.compile(r"\{\{([#^])\s*([\w.]+)\s*\}\}(.*?)\{\{/\s*\2\s*\}\}", re.DOTALL)
PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
MISSING = re.compile(r"\{\{.*?\}\}", re.DOTALL)

REQUIRED_TOP = ("meta", "identity", "core_metrics", "axes", "narrative", "footer")
REQUIRED_META = ("archetype", "one_line", "subject", "system_label", "seal")
REQUIRED_FOOTER = ("limitation", "generated_at")
TOP_LISTS = ("identity", "core_metrics", "axes")
NESTED_LISTS = (
    ("distribution", "items"),
    ("tendencies", "strengths"),
    ("tendencies", "tensions"),
    ("domains", "rows"),
    ("conflicts", "rows"),
    ("narrative", "paragraphs"),
    ("reflection", "items"),
    ("confidence", "items"),
)
CAPPED = {"core_metrics": 6, "identity": 8, "axes": 4}


class PosterError(ValueError):
    """A poster payload or template cannot produce a complete document."""


def render(template: str, data: Mapping[str, Any]) -> str:
    """Return the template with every section expanded and value escaped."""

    rendered = _expand(template, data, data)
    leftover = MISSING.search(rendered)
    if leftover:
        raise PosterError(f"template still holds an unresolved tag: {leftover.group(0)[:60]!r}")
    return rendered


def validate(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the poster payload and report every fault in one round trip."""

    problems: list[str] = []
    for field in REQUIRED_TOP:
        if data.get(field) in (None, "", [], {}):
            problems.append(f"{field}: required")

    meta = data.get("meta")
    if isinstance(meta, Mapping):
        for field in REQUIRED_META:
            if not str(meta.get(field) or "").strip():
                problems.append(f"meta.{field}: required")
    elif "meta" not in [problem.split(":")[0] for problem in problems]:
        problems.append("meta: expected an object")

    footer = data.get("footer")
    if isinstance(footer, Mapping):
        for field in REQUIRED_FOOTER:
            if not str(footer.get(field) or "").strip():
                problems.append(f"footer.{field}: required")
    elif "footer" not in [problem.split(":")[0] for problem in problems]:
        problems.append("footer: expected an object")

    for field in TOP_LISTS:
        _require_list(data.get(field), field, problems)

    for parent, field in NESTED_LISTS:
        block = data.get(parent)
        if block is None:
            continue
        if not isinstance(block, Mapping):
            problems.append(f"{parent}: expected an object holding {field!r}")
            continue
        if field in block or parent in ("narrative", "reflection"):
            _require_list(block.get(field), f"{parent}.{field}", problems)

    for field, limit in CAPPED.items():
        value = data.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) > limit:
            problems.append(f"{field}: keep at most {limit} entries so the poster stays readable")

    _check_ratios(data, problems)
    if problems:
        raise PosterError("; ".join(problems))
    return dict(data)


def _require_list(value: Any, field: str, problems: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        problems.append(f"{field}: expected a list")


def _check_ratios(data: Mapping[str, Any], problems: list[str]) -> None:
    """A ratio drives a bar width, so an out-of-range value would break layout."""

    for field in ("core_metrics", "confidence", "distribution"):
        block = data.get(field)
        items = block.get("items") if isinstance(block, Mapping) else block
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, Mapping) or item.get("ratio") is None:
                continue
            ratio = item["ratio"]
            if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= ratio <= 100:
                problems.append(f"{field}[{index}].ratio: expected a number from 0 through 100")


def _expand(template: str, scope: Any, root: Mapping[str, Any]) -> str:
    def section(match: re.Match[str]) -> str:
        marker, path, body = match.group(1), match.group(2), match.group(3)
        value = _lookup(path, scope, root)
        truthy = _truthy(value)
        if marker == "^":
            return _expand(body, scope, root) if not truthy else ""
        if not truthy:
            return ""
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return "".join(_expand(body, _child(item, scope), root) for item in value)
        return _expand(body, _child(value, scope), root)

    expanded = SECTION.sub(section, template)
    return PLACEHOLDER.sub(lambda match: _escape(_lookup(match.group(1), scope, root)), expanded)


def _child(value: Any, parent: Any) -> Any:
    """Keep the parent reachable so a loop body can still read outer fields."""

    if isinstance(value, Mapping):
        return {"__parent__": parent, **value}
    return {"__parent__": parent, ".": value}


def _lookup(path: str, scope: Any, root: Mapping[str, Any]) -> Any:
    for candidate in (scope, root):
        value = _walk(path, candidate)
        if value is not None:
            return value
        parent = candidate.get("__parent__") if isinstance(candidate, Mapping) else None
        while parent is not None:
            value = _walk(path, parent)
            if value is not None:
                return value
            parent = parent.get("__parent__") if isinstance(parent, Mapping) else None
    return None


def _walk(path: str, value: Any) -> Any:
    if path == ".":
        return value.get(".") if isinstance(value, Mapping) else None
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _escape(value: Any) -> str:
    if value is None or value is False:
        return ""
    if value is True:
        return "true"
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return html.escape(text, quote=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="poster payload JSON written by the reading skill")
    parser.add_argument("--template", help="override the bundled ink-wash template")
    parser.add_argument("--out", required=True, help="destination .html path")
    args = parser.parse_args()

    template_path = (
        Path(args.template) if args.template else Path(__file__).parent / "templates" / "ink-wash-poster.html"
    )
    try:
        payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
        data = validate(payload)
        document = render(template_path.read_text(encoding="utf-8"), data)
    except (OSError, json.JSONDecodeError, PosterError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    print(destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
