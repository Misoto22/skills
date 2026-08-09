#!/usr/bin/env python3
"""Validate evidence-linked synastry Markdown before accepting the reading."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from validate_synastry import EvidenceLedger, _write_atomic_bytes, load_ledger

_EVIDENCE_TOKEN = re.compile(r"\[E-(?:ASPECT|OVERLAY)-[0-9A-F]{4}\]")
_EVIDENCE_LIKE = re.compile(r"\[E-(?:ASPECT|OVERLAY)-[^\]\s]+\]", re.IGNORECASE)
_HEADING = re.compile(r"^(#{2,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"<[^<>\n]+>")
_ORB = re.compile(
    r"\borb(?:[ \t]+range)?[ \t]+\d+(?:\.\d+)?°(?:[ \t]*-[ \t]*\d+(?:\.\d+)?°)?",
    re.IGNORECASE,
)
_SCORE = re.compile(
    r"compatibility[ \t]+(?:score|rating)|(?:score|rating)[ \t]*[:=][ \t]*\d|"
    r"\b\d+(?:\.\d+)?[ \t]*(?:%|/[ \t]*(?:5|10|100))|[★⭐]{2,}",
    re.IGNORECASE,
)
_PREDICTION = re.compile(
    r"\b(?:will|guarantees?|guaranteed|destined|definitely|inevitably|certain to|must happen)\b|"
    r"必然|注定|保证|一定会|肯定会|必定",
    re.IGNORECASE,
)

_UNIVERSAL_HEADINGS = {
    "en": (
        "Basis, provenance, and limitations",
        "Repeated interaction patterns",
        "Reciprocity and asymmetry",
        "Communication and coordination",
        "Tension, boundaries, and repair",
        "Growth and shared direction",
        "Requested or context-specific domains",
        "Overall synthesis",
        "Evidence index",
    ),
    "zh": (
        "分析基础、数据来源与限制",
        "反复出现的互动模式",
        "双向影响与不对称性",
        "沟通与协作",
        "张力、边界与修复",
        "成长与共同方向",
        "用户要求或关系背景领域",
        "整体总结",
        "证据索引",
    ),
}

_CONDITIONAL_MODULE_ALIASES = (
    frozenset(
        {
            "romance and intimacy",
            "attraction, romance, and intimacy",
            "浪漫与亲密关系",
            "吸引力、浪漫与亲密关系",
        }
    ),
    frozenset(
        {
            "friendship and community",
            "friendship, community, and social networks",
            "友谊与社群",
            "友谊、社群与社交网络",
        }
    ),
    frozenset(
        {"family and care", "daily life, home, family, and care", "家庭与照护", "日常生活、家庭与照护"}
    ),
    frozenset(
        {
            "work and creative collaboration",
            "career, business, and creative collaboration",
            "工作与创意协作",
            "事业、商业与创意协作",
        }
    ),
    frozenset(
        {
            "money and shared resources",
            "money, shared resources, and risk tolerance",
            "金钱与共同资源",
            "金钱、共同资源与风险承受",
        }
    ),
)


class ReadingError(ValueError):
    """One or more deterministic reading checks failed."""

    def __init__(self, problems: Sequence[str]):
        self.problems = tuple(problems)
        super().__init__("\n".join(self.problems))


def validate_markdown(
    markdown: str,
    ledger: EvidenceLedger,
    language: str,
    selected_modules: Sequence[str],
) -> list[str]:
    """Return every structural and evidence-integrity problem in one Markdown reading."""

    problems: list[str] = []
    if not isinstance(markdown, str):
        return ["markdown: expected text"]

    language_key = _language_key(language)
    if language_key is None:
        problems.append(f"language: unsupported value {language!r}")
    else:
        _validate_headings(markdown, language_key, selected_modules, problems)

    placeholders = _PLACEHOLDER.findall(markdown)
    if placeholders:
        problems.append(f"template placeholder remains: {placeholders[0]}")
    if _SCORE.search(markdown):
        problems.append("compatibility score or rating language is forbidden")
    if _PREDICTION.search(markdown):
        problems.append("deterministic prediction language is forbidden")

    _validate_evidence(markdown, ledger, problems)
    return _deduplicate(problems)


def _validate_headings(
    markdown: str,
    language: str,
    selected_modules: Sequence[str],
    problems: list[str],
) -> None:
    headings = [(marker, title.strip()) for marker, title in _HEADING.findall(markdown)]
    level_two = [title for marker, title in headings if marker == "##"]
    required = _UNIVERSAL_HEADINGS[language]
    missing = [heading for heading in required if heading not in level_two]
    for heading in missing:
        problems.append(f"required universal heading is missing: {heading}")
    present_positions = [level_two.index(heading) for heading in required if heading in level_two]
    if present_positions != sorted(present_positions):
        problems.append("required universal heading order is incorrect")

    normalized_headings = {_normalize_heading(title) for _, title in headings}
    selected = {_normalize_heading(module) for module in selected_modules}
    for aliases in _CONDITIONAL_MODULE_ALIASES:
        present_aliases = normalized_headings & aliases
        selected_aliases = selected & aliases
        if present_aliases and not selected_aliases:
            problems.append(f"unselected module is present: {sorted(present_aliases)[0]}")
        if selected_aliases and not present_aliases:
            problems.append(f"selected module is missing: {sorted(selected_aliases)[0]}")

    known_selected = set().union(*_CONDITIONAL_MODULE_ALIASES) & selected
    for module in sorted(selected - known_selected):
        if module not in normalized_headings:
            problems.append(f"selected module is missing: {module}")


def _validate_evidence(markdown: str, ledger: EvidenceLedger, problems: list[str]) -> None:
    known = {f"[{item.id}]": item for item in ledger.evidence}
    tokens = _EVIDENCE_TOKEN.findall(markdown)
    malformed = sorted(set(_EVIDENCE_LIKE.findall(markdown)) - set(tokens))
    for token in malformed:
        problems.append(f"malformed evidence token: {token}")
    if ledger.evidence and not tokens:
        problems.append("reading contains no inline evidence tokens")

    for token in sorted(set(tokens)):
        item = known.get(token)
        if item is None:
            problems.append(f"unknown evidence token: {token}")
        elif item.citation not in markdown:
            problems.append(f"evidence measurement does not match ledger display: {token}")

    for line in markdown.splitlines():
        if "aspect:" not in line.casefold() and "overlay:" not in line.casefold():
            continue
        for token in _EVIDENCE_TOKEN.findall(line):
            item = known.get(token)
            if item is not None and item.citation not in line:
                problems.append(f"evidence measurement does not match ledger display: {token}")

    exact_measurements = {
        match.group(0) for item in ledger.evidence for match in _ORB.finditer(item.citation)
    }
    for measurement in sorted(set(_ORB.findall(markdown))):
        if measurement not in exact_measurements:
            problems.append(f"measurement does not match evidence ledger: {measurement}")


def _language_key(language: str) -> str | None:
    normalized = language.strip().lower().replace("_", "-")
    if normalized == "en" or normalized.startswith("en-"):
        return "en"
    if normalized == "zh" or normalized.startswith("zh-"):
        return "zh"
    return None


def _normalize_heading(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _deduplicate(problems: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(problems))


def write_validated_markdown(
    markdown: str,
    ledger: EvidenceLedger,
    destination: str | os.PathLike[str],
    language: str,
    selected_modules: Sequence[str],
    overwrite: bool = False,
) -> Path:
    """Validate and atomically write Markdown with exclusive, user-only defaults."""

    target = Path(destination).expanduser()
    if ledger.source_path is not None and target.resolve() == Path(ledger.source_path).resolve():
        raise ValueError("reading destination must not replace the source JSON")
    if target.suffix.lower() != ".md":
        raise ValueError("reading destination must end in .md and must not be the source JSON")
    problems = validate_markdown(markdown, ledger, language, selected_modules)
    if problems:
        raise ReadingError(problems)
    return _write_atomic_bytes(
        markdown.encode("utf-8"),
        target,
        overwrite=overwrite,
        temporary_prefix="synastry-reading",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="validated synastry v2 .json artifact")
    parser.add_argument("reading", type=Path, help="draft Markdown to validate")
    parser.add_argument("--language", help="report language; defaults to the artifact language")
    parser.add_argument("--module", action="append", default=[], dest="modules")
    parser.add_argument("--out", type=Path, help="write the validated Markdown atomically")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing reading atomically")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Markdown validator CLI and return zero or two."""

    try:
        arguments = _parser().parse_args(argv)
        ledger = load_ledger(arguments.source)
        markdown = arguments.reading.read_text(encoding="utf-8")
        language = arguments.language or ledger.language
        if arguments.out is not None:
            write_validated_markdown(
                markdown,
                ledger,
                arguments.out,
                language,
                arguments.modules,
                overwrite=arguments.overwrite,
            )
        else:
            problems = validate_markdown(markdown, ledger, language, arguments.modules)
            if problems:
                raise ReadingError(problems)
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        if isinstance(error, ReadingError):
            for problem in error.problems:
                print(f"error: {problem}", file=sys.stderr)
        else:
            print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
