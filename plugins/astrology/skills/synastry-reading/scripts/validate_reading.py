#!/usr/bin/env python3
"""Validate evidence-linked synastry Markdown before accepting the reading."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from validate_synastry import (
    EvidenceItem,
    EvidenceLedger,
    OutputExistsError,
    SchemaError,
    SourceIdentityError,
    _is_source_path,
    _source_identity,
    _write_atomic_bytes,
    load_ledger,
)

_EVIDENCE_TOKEN = re.compile(r"\[E-(?:ASPECT|OVERLAY)-[0-9A-F]{4}\]")
_EVIDENCE_LIKE = re.compile(r"\[E-(?:ASPECT|OVERLAY)-[^\]\s]+\]", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"<[^<>\n]+>")
_DEGREE_CLAIM = re.compile(
    r"(?P<first>\d+(?:\.\d+)?)[ \t]*(?:°|deg(?:ree)?s?)"
    r"(?:[ \t]*(?:-|\N{EN DASH}|\N{EM DASH}|to)[ \t]*"
    r"(?P<second>\d+(?:\.\d+)?)[ \t]*(?:°|deg(?:ree)?s?))?",
    re.IGNORECASE,
)
_SCORE = re.compile(
    r"compatibility[ \t]+(?:score|rating)|(?:score|rating)[ \t]*[:=][ \t]*\d|"
    r"\b\d+(?:\.\d+)?[ \t]*(?:%|percent\b|points?\b|/[ \t]*(?:5|10|100))|[★⭐]{2,}",
    re.IGNORECASE,
)
_PREDICTION = re.compile(
    r"\b(?:will|shall|guarantees?|guaranteed|destined|definitely|inevitably|certain to|must happen)\b|"
    r"\bgoing[ \t]+to(?:[ \t]+\w+){1,4}\b|"
    r"必然|注定|保证|一定会|肯定会|必定",
    re.IGNORECASE,
)
_CONDITIONAL = {
    "en": re.compile(
        r"\b(?:can|could|may|might|tends?|often|suggests?|appears?|possibly|perhaps|potentially)\b",
        re.IGNORECASE,
    ),
    "zh": re.compile(r"可能|也许|或许|倾向|往往|通常|可以|可(?:能)?|有时|似乎"),
}
_FENCE = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")
_ATX_HEADING = re.compile(r"^[ \t]{0,3}(?P<marker>#{1,6})[ \t]+(?P<title>.*?)[ \t]*#*[ \t]*$")
_LIST_PREFIX = re.compile(r"^[ \t]{0,3}(?:(?:>[ \t]*)+)?(?:[-+*]|\d+[.)])[ \t]+")
_QUOTE_PREFIX = re.compile(r"^[ \t]{0,3}(?:>[ \t]*)+")
_CLAIM_BOUNDARY = re.compile(
    r"[.!?;\N{IDEOGRAPHIC FULL STOP}\N{FULLWIDTH EXCLAMATION MARK}"
    r"\N{FULLWIDTH QUESTION MARK}\N{FULLWIDTH SEMICOLON}]+|"
    r"\b(?:and|but|while|whereas|although|however)\b",
    re.IGNORECASE,
)
_WORD_HOUSES = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
}
_ASPECT_KINDS = frozenset(
    {
        "conjunction",
        "opposition",
        "trine",
        "square",
        "sextile",
        "semi-sextile",
        "semi-square",
        "quintile",
        "sesquiquadrate",
        "biquintile",
        "quincunx",
    }
)
_BODY_NAMES = frozenset(
    {
        "sun",
        "moon",
        "mercury",
        "venus",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
        "pluto",
        "chiron",
        "ceres",
        "pallas",
        "juno",
        "vesta",
        "ascendant",
        "descendant",
        "medium_coeli",
        "imum_coeli",
        "vertex",
        "east_point",
    }
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

_CANONICAL_MODULES = {
    "en": (
        "Romance and intimacy",
        "Friendship and community",
        "Family and care",
        "Work and creative collaboration",
        "Money and shared resources",
    ),
    "zh": ("浪漫与亲密关系", "友谊与社群", "家庭与照护", "工作与创意协作", "金钱与共同资源"),
}
_NONCANONICAL_MODULE_ALIASES = frozenset(
    {
        "attraction, romance, and intimacy",
        "friendship, community, and social networks",
        "daily life, home, family, and care",
        "career, business, and creative collaboration",
        "money, shared resources, and risk tolerance",
        "吸引力、浪漫与亲密关系",
        "友谊、社群与社交网络",
        "日常生活、家庭与照护",
        "事业、商业与创意协作",
        "金钱、共同资源与风险承受",
    }
)


@dataclass(frozen=True)
class _Block:
    kind: str
    text: str
    level: int = 0


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

    blocks = _rendered_blocks(markdown)
    rendered = "\n".join(block.text for block in blocks)
    language_key = _language_key(language)
    if language_key is None:
        problems.append("language: unsupported value")
    else:
        _validate_headings(blocks, language_key, selected_modules, problems)

    placeholders = _PLACEHOLDER.findall(rendered)
    if placeholders:
        problems.append("template placeholder remains")
    if _SCORE.search(rendered):
        problems.append("compatibility score or rating language is forbidden")
    if _PREDICTION.search(rendered):
        problems.append("deterministic prediction language is forbidden")

    if language_key is not None:
        _validate_evidence(blocks, ledger, language_key, problems)
    return _deduplicate(problems)


def _validate_headings(
    blocks: Sequence[_Block],
    language: str,
    selected_modules: Sequence[str],
    problems: list[str],
) -> None:
    headings = [block for block in blocks if block.kind == "heading"]
    level_two = [block.text for block in headings if block.level == 2]
    required = _UNIVERSAL_HEADINGS[language]
    missing = [heading for heading in required if heading not in level_two]
    for heading in missing:
        problems.append(f"required universal heading is missing: {heading}")
    present_positions = [level_two.index(heading) for heading in required if heading in level_two]
    if present_positions != sorted(present_positions):
        problems.append("required universal heading order is incorrect")

    domains = _normalize_heading(required[6])
    canonical = {_normalize_heading(module): module for module in _CANONICAL_MODULES[language]}
    selected = {_normalize_heading(module) for module in selected_modules}
    invalid_selected = selected - canonical.keys()
    if invalid_selected:
        problems.append("selected module is not a canonical module heading")
    selected &= canonical.keys()

    current_level_two: str | None = None
    present: set[str] = set()
    for heading in headings:
        normalized = _normalize_heading(heading.text)
        if normalized in _NONCANONICAL_MODULE_ALIASES:
            problems.append("noncanonical module heading is forbidden")
        if normalized in canonical:
            if heading.level != 3 or current_level_two != domains:
                problems.append("canonical module appears outside the domains section or at the wrong level")
            elif normalized not in selected:
                problems.append("unselected module is present in the domains section")
            else:
                present.add(normalized)
        elif heading.level == 3 and current_level_two == domains:
            problems.append("unselected module is present in the domains section")
        if heading.level == 2:
            current_level_two = normalized

    for module in sorted(selected - present):
        problems.append(f"selected module is missing: {canonical[module]}")


def _rendered_blocks(markdown: str) -> list[_Block]:
    masked = _mask_nonrendered(markdown)
    blocks: list[_Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(_Block("paragraph", " ".join(paragraph).strip()))
            paragraph.clear()

    for raw_line in masked.splitlines():
        line = _strip_inline_nonrendered(raw_line)
        heading = _ATX_HEADING.match(line)
        if heading is not None:
            flush()
            title = heading.group("title").strip()
            blocks.append(_Block("heading", title, len(heading.group("marker"))))
            continue
        if not line.strip():
            flush()
            continue
        if _LIST_PREFIX.match(line):
            flush()
            line = _LIST_PREFIX.sub("", line, count=1)
            blocks.append(_Block("paragraph", line.strip()))
            continue
        line = _QUOTE_PREFIX.sub("", line, count=1)
        paragraph.append(line.strip())
    flush()
    return blocks


def _strip_inline_nonrendered(line: str) -> str:
    line = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)
    return line


def _mask_nonrendered(markdown: str) -> str:
    masked = _mask_html_comments(markdown)
    masked = _mask_code_containers(masked)
    return _mask_code_spans(masked)


def _blank(value: str) -> str:
    return re.sub(r"[^\n]", " ", value)


def _mask_html_comments(markdown: str) -> str:
    result: list[str] = []
    cursor = 0
    while True:
        start = markdown.find("<!--", cursor)
        if start < 0:
            result.append(markdown[cursor:])
            return "".join(result)
        result.append(markdown[cursor:start])
        end = markdown.find("-->", start + 4)
        stop = len(markdown) if end < 0 else end + 3
        result.append(_blank(markdown[start:stop]))
        cursor = stop


def _mask_code_containers(markdown: str) -> str:
    result: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for raw_line in markdown.splitlines(keepends=True):
        content = raw_line.rstrip("\r\n")
        container_content = _QUOTE_PREFIX.sub("", content, count=1)
        fence = _FENCE.match(container_content)
        if fence_character is not None:
            result.append(_blank(raw_line))
            if fence is not None:
                marker = fence.group("marker")
                if marker[0] == fence_character and len(marker) >= fence_length:
                    fence_character = None
                    fence_length = 0
            continue
        if fence is not None:
            marker = fence.group("marker")
            fence_character = marker[0]
            fence_length = len(marker)
            result.append(_blank(raw_line))
            continue
        if container_content.startswith("    ") or container_content.startswith("\t"):
            result.append(_blank(raw_line))
            continue
        result.append(raw_line)
    return "".join(result)


def _mask_code_spans(markdown: str) -> str:
    characters = list(markdown)
    cursor = 0
    while cursor < len(markdown):
        if markdown[cursor] != "`":
            cursor += 1
            continue
        end_of_opener = cursor
        while end_of_opener < len(markdown) and markdown[end_of_opener] == "`":
            end_of_opener += 1
        delimiter = markdown[cursor:end_of_opener]
        closing = markdown.find(delimiter, end_of_opener)
        while closing >= 0 and (
            (closing > 0 and markdown[closing - 1] == "`")
            or (closing + len(delimiter) < len(markdown) and markdown[closing + len(delimiter)] == "`")
        ):
            closing = markdown.find(delimiter, closing + len(delimiter))
        if closing < 0:
            cursor = end_of_opener
            continue
        stop = closing + len(delimiter)
        for index in range(cursor, stop):
            if characters[index] not in "\r\n":
                characters[index] = " "
        cursor = stop
    return "".join(characters)


def _validate_evidence(
    blocks: Sequence[_Block],
    ledger: EvidenceLedger,
    language: str,
    problems: list[str],
) -> None:
    known = {f"[{item.id}]": item for item in ledger.evidence}
    rendered = "\n".join(block.text for block in blocks)
    tokens = _EVIDENCE_TOKEN.findall(rendered)
    malformed = sorted(set(_EVIDENCE_LIKE.findall(rendered)) - set(tokens))
    if malformed:
        problems.append("malformed evidence token")
    if ledger.evidence and not tokens:
        problems.append("reading contains no inline evidence tokens")

    for token in sorted(set(tokens)):
        if token not in known:
            problems.append("unknown evidence token")

    keys = _section_keys(blocks, language)
    section_evidence: dict[tuple[str, str | None], dict[str, EvidenceItem]] = {}
    for index, block in enumerate(blocks):
        if block.kind != "paragraph" or keys[index] is None:
            continue
        for token in _EVIDENCE_TOKEN.findall(block.text):
            item = known.get(token)
            if item is not None and (block.text.startswith(item.citation) or block.text == item.display):
                section_evidence.setdefault(keys[index], {})[item.id] = item

    for index, block in enumerate(blocks):
        if block.kind != "paragraph":
            continue
        direct = [known[token] for token in _EVIDENCE_TOKEN.findall(block.text) if token in known]
        section = list(section_evidence.get(keys[index], {}).values()) if keys[index] else []
        bound = direct or section
        top_section = keys[index][0] if keys[index] else ""
        substantive = _is_substantive(block.text, top_section, ledger, language)
        if substantive and not bound:
            problems.append("substantive paragraph lacks valid evidence")
        if substantive and _contains_unconditional_claim(block.text, language):
            problems.append("substantive paragraph requires conditional language")
        if bound:
            _validate_claims(block.text, bound, ledger, problems)
        elif _DEGREE_CLAIM.search(block.text):
            problems.append("measurement does not match paragraph evidence")


def _section_keys(blocks: Sequence[_Block], language: str) -> list[tuple[str, str | None] | None]:
    domains = _normalize_heading(_UNIVERSAL_HEADINGS[language][6])
    current_level_two: str | None = None
    current_module: str | None = None
    result: list[tuple[str, str | None] | None] = []
    for block in blocks:
        if block.kind == "heading":
            if block.level == 2:
                current_level_two = _normalize_heading(block.text)
                current_module = None
            elif block.level == 3 and current_level_two == domains:
                current_module = _normalize_heading(block.text)
        result.append((current_level_two, current_module) if current_level_two is not None else None)
    return result


def _is_substantive(
    text: str,
    top_section: str,
    ledger: EvidenceLedger,
    language: str,
) -> bool:
    exempt_sections = {
        _normalize_heading(_UNIVERSAL_HEADINGS[language][0]),
        _normalize_heading(_UNIVERSAL_HEADINGS[language][-1]),
    }
    if top_section in exempt_sections:
        return False
    if any(text == item.citation or text == item.display for item in ledger.evidence):
        return False
    if re.match(
        r"^(?:Source|House system|Aspect orbs|Relationship context|Data limitations|"
        r"数据来源|宫位系统|相位容许度|用户提供的关系背景|数据限制)[ \t]*:",
        text,
        re.IGNORECASE,
    ):
        return False
    if re.match(
        r"^(?:No directly relevant measurement|The source does not support|Evidence is insufficient|"
        r"No unrequested domain met|没有直接相关证据|源数据不足)",
        text,
        re.IGNORECASE,
    ):
        return False
    return bool(re.search(r"[A-Za-z\u3400-\u9fff]", text))


def _contains_unconditional_claim(text: str, language: str) -> bool:
    without_citations = _EVIDENCE_TOKEN.sub("", text)
    for claim in _CLAIM_BOUNDARY.split(without_citations):
        if language == "en":
            substantive = len(re.findall(r"[A-Za-z]+", claim)) >= 3
        else:
            substantive = len(re.findall(r"[\u3400-\u9fff]", claim)) >= 4
        if substantive and _CONDITIONAL[language].search(claim) is None:
            return True
    return False


def _validate_claims(
    text: str,
    evidence: Sequence[EvidenceItem],
    ledger: EvidenceLedger,
    problems: list[str],
) -> None:
    claim_mismatch = False
    measurement_mismatch = False
    allowed_pairs: set[tuple[str, str]] = set()
    allowed_directions: set[tuple[str, str]] = set()
    allowed_certainties: set[str] = set()
    allowed_houses: set[int] = set()
    allowed_aspects: set[str] = set()
    allowed_measurements: set[tuple[float, float | None]] = set()
    uncertain_ranges: set[tuple[float, float]] = set()
    for item in evidence:
        data = item.data
        source = str(data["source_subject_id"])
        target = str(data["target_subject_id"])
        allowed_directions.add((source, target))
        allowed_pairs.add((source, str(data["source_body"])))
        certainty = str(data.get("certainty", "exact"))
        allowed_certainties.add(certainty)
        if item.kind == "aspect":
            allowed_pairs.add((target, str(data["target_body"])))
            allowed_aspects.add(str(data["kind"]))
            if certainty == "exact":
                allowed_measurements.add((float(data["orb_degrees"]), None))
            else:
                orb_range = data["orb_range_degrees"]
                minimum = float(orb_range["minimum_degrees"])  # type: ignore[index]
                maximum = float(orb_range["maximum_degrees"])  # type: ignore[index]
                allowed_measurements.add((minimum, maximum))
                uncertain_ranges.add((minimum, maximum))
        else:
            allowed_houses.add(int(data["target_house"]))

    subject_ids = [subject.id for subject in ledger.subjects]
    evidence_body_names = {body.casefold() for _, body in allowed_pairs}
    for subject_id in subject_ids:
        pattern = re.compile(rf"(?<![\w-]){re.escape(subject_id)}(?:'s)?[ \t]+([\w-]+)", re.IGNORECASE)
        for body in pattern.findall(text):
            if body.casefold() not in _BODY_NAMES and body.casefold() not in evidence_body_names:
                continue
            if not any(
                subject_id.casefold() == owner.casefold() and body.casefold() == known_body.casefold()
                for owner, known_body in allowed_pairs
            ):
                claim_mismatch = True
        reversed_pattern = re.compile(
            rf"(?<![\w-])([\w-]+)[ \t]+of[ \t]+{re.escape(subject_id)}(?![\w-])",
            re.IGNORECASE,
        )
        for body in reversed_pattern.findall(text):
            if body.casefold() not in _BODY_NAMES and body.casefold() not in evidence_body_names:
                continue
            if not any(
                subject_id.casefold() == owner.casefold() and body.casefold() == known_body.casefold()
                for owner, known_body in allowed_pairs
            ):
                claim_mismatch = True
        for other_id in subject_ids:
            if subject_id == other_id:
                continue
            direction = re.compile(
                rf"(?<![\w-]){re.escape(subject_id)}[ \t]*(?:->|→|to)[ \t]*"
                rf"{re.escape(other_id)}(?![\w-])",
                re.IGNORECASE,
            )
            if direction.search(text) and (subject_id, other_id) not in allowed_directions:
                claim_mismatch = True

    for certainty in re.findall(r"\b(?:exact|confirmed|possible)\b", text, re.IGNORECASE):
        if certainty.casefold() not in {item.casefold() for item in allowed_certainties}:
            claim_mismatch = True
    for house in re.findall(r"\bhouse[ \t]+(\d{1,2})\b", text, re.IGNORECASE):
        if int(house) not in allowed_houses:
            measurement_mismatch = True
    for house in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)[ \t]+house\b", text, re.IGNORECASE):
        if int(house) not in allowed_houses:
            measurement_mismatch = True
    word_house_pattern = r"\b(" + "|".join(_WORD_HOUSES) + r")[ \t]+house\b"
    for house in re.findall(word_house_pattern, text, re.IGNORECASE):
        if _WORD_HOUSES[house.casefold()] not in allowed_houses:
            measurement_mismatch = True
    for aspect in re.findall(r"\b[\w-]+\b", text.casefold()):
        if aspect in _ASPECT_KINDS and aspect not in {item.casefold() for item in allowed_aspects}:
            claim_mismatch = True
        if aspect in _BODY_NAMES and aspect not in {body.casefold() for _, body in allowed_pairs}:
            claim_mismatch = True

    for match in _DEGREE_CLAIM.finditer(text):
        measurement = (
            float(match.group("first")),
            float(match.group("second")) if match.group("second") is not None else None,
        )
        if measurement not in allowed_measurements:
            measurement_mismatch = True
        elif measurement[1] is not None and (
            measurement not in uncertain_ranges
            or not any(certainty in text.casefold() for certainty in ("confirmed", "possible"))
        ):
            claim_mismatch = True

    if claim_mismatch:
        problems.append("claim does not match paragraph evidence")
    if measurement_mismatch:
        problems.append("measurement does not match paragraph evidence")


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
    if _is_source_path(target, ledger):
        raise SourceIdentityError("reading destination must not replace the source JSON")
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
        forbidden_identity=_source_identity(ledger),
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

    arguments = _parser().parse_args(argv)
    try:
        ledger = load_ledger(arguments.source)
    except json.JSONDecodeError:
        print("error: source is not valid JSON", file=sys.stderr)
        return 2
    except SchemaError:
        print("error: source JSON failed synastry v2 validation", file=sys.stderr)
        return 2
    except OSError:
        print("error: could not read source JSON", file=sys.stderr)
        return 2
    except (TypeError, ValueError):
        print("error: source must be a synastry v2 JSON object or .json file", file=sys.stderr)
        return 2

    try:
        markdown = arguments.reading.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("error: could not read draft Markdown", file=sys.stderr)
        return 2

    language = arguments.language or ledger.language
    try:
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
    except ReadingError:
        print("error: reading validation failed", file=sys.stderr)
    except SourceIdentityError:
        print("error: reading output must not replace the source JSON", file=sys.stderr)
    except OutputExistsError:
        print("error: reading output already exists; use --overwrite", file=sys.stderr)
    except (OSError, TypeError, ValueError):
        print("error: could not write validated reading", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
