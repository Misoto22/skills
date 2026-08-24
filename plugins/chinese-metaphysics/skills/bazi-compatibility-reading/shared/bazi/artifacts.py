"""Canonical checksums, safe names, and atomic artifact pairs."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# One name and one version per artifact kind, imported by the engine that writes
# it and the validator that checks it. Written in both places instead, a bumped
# version here would reject the very output this plugin's engine still produces.
CHART_SCHEMA = "chinese-metaphysics.bazi-chart"
COMPATIBILITY_SCHEMA = "chinese-metaphysics.bazi-compatibility"
ZIWEI_SCHEMA = "chinese-metaphysics.ziwei-chart"

SCHEMAS = {
    CHART_SCHEMA: 1,
    COMPATIBILITY_SCHEMA: 1,
    ZIWEI_SCHEMA: 1,
}

# Both systems change the day at the same instant, because they read the same
# true solar time. Two copies of that decision could drift into two calendars
# inside one plugin, and a cross-reading would compare charts built on different
# days without either one looking wrong.
DAY_BOUNDARY = "23:00"
ALTERNATE_DAY_BOUNDARY = "00:00"


class ArtifactError(ValueError):
    """An artifact is invalid or cannot be written safely."""


def slugify(value: str) -> str:
    """Return a portable Unicode filename component with no path semantics."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = re.sub(r"[\\/]+", "-", normalized)
    normalized = re.sub(r"[^\w\-\u3400-\u9fff]+", "-", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[-_]{2,}", "-", normalized).strip(" .-_")
    return normalized or "unnamed"


def add_checksum(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached JSON-compatible envelope with its canonical SHA-256."""

    result = copy.deepcopy(dict(envelope))
    result.pop("checksum", None)
    result["checksum"] = _checksum(result)
    return result


def validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema identity, version, and canonical content checksum."""

    result = copy.deepcopy(dict(envelope))
    schema = result.get("schema")
    if schema not in SCHEMAS:
        raise ArtifactError(f"unsupported artifact schema {schema!r}")
    if result.get("schema_version") != SCHEMAS[schema]:
        raise ArtifactError(
            f"unsupported {schema} version {result.get('schema_version')!r}; expected {SCHEMAS[schema]}"
        )
    supplied = result.get("checksum")
    if not isinstance(supplied, str) or supplied != _checksum(result):
        raise ArtifactError("artifact checksum does not match its canonical content")
    return result


def write_artifact_pair(
    envelope: Mapping[str, Any],
    output_directory: Path,
    *,
    kind: str,
) -> tuple[Path, Path]:
    """Write or reuse one collision-safe canonical JSON/Markdown pair."""

    validated = validate_envelope(envelope)
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = _artifact_stem(validated, kind)
    json_bytes = _pretty_json(validated)
    markdown_bytes = _render_markdown(validated, kind).encode("utf-8")
    checksum = validated["checksum"]

    json_path = output_directory / f"{stem}.json"
    markdown_path = output_directory / f"{stem}.md"
    if _same_pair(json_path, markdown_path, json_bytes, markdown_bytes):
        return json_path.resolve(), markdown_path.resolve()
    if json_path.exists() or markdown_path.exists():
        stem = f"{stem}-{checksum[:8]}"
        json_path = output_directory / f"{stem}.json"
        markdown_path = output_directory / f"{stem}.md"
        if _same_pair(json_path, markdown_path, json_bytes, markdown_bytes):
            return json_path.resolve(), markdown_path.resolve()
        if json_path.exists() or markdown_path.exists():
            raise ArtifactError(f"artifact collision at {json_path.name}")

    temporary: list[Path] = []
    try:
        json_temp = _write_temp(output_directory, json_bytes)
        temporary.append(json_temp)
        markdown_temp = _write_temp(output_directory, markdown_bytes)
        temporary.append(markdown_temp)
        os.link(json_temp, json_path)
        try:
            os.link(markdown_temp, markdown_path)
        except Exception:
            json_path.unlink(missing_ok=True)
            raise
    except FileExistsError as error:
        raise ArtifactError("artifact path changed during atomic creation; retry") from error
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return json_path.resolve(), markdown_path.resolve()


def _artifact_stem(envelope: Mapping[str, Any], kind: str) -> str:
    if kind == "chart":
        return f"bazi_{slugify(str(envelope['input']['name']))}"
    if kind == "compatibility":
        left = slugify(str(envelope["people"]["left"]["name"]))
        right = slugify(str(envelope["people"]["right"]["name"]))
        return f"bazi_compatibility_{left}_{right}"
    if kind == "ziwei":
        return f"ziwei_{slugify(str(envelope['input']['name']))}"
    raise ArtifactError(f"unsupported artifact kind {kind!r}")


def _checksum(envelope: Mapping[str, Any]) -> str:
    content = dict(envelope)
    content.pop("checksum", None)
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pretty_json(envelope: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def _same_pair(
    json_path: Path,
    markdown_path: Path,
    json_bytes: bytes,
    markdown_bytes: bytes,
) -> bool:
    return (
        json_path.is_file()
        and markdown_path.is_file()
        and json_path.read_bytes() == json_bytes
        and markdown_path.read_bytes() == markdown_bytes
    )


def _write_temp(directory: Path, content: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".bazi-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def _render_markdown(envelope: Mapping[str, Any], kind: str) -> str:
    if kind == "chart":
        return _render_chart_markdown(envelope)
    if kind == "compatibility":
        return _render_compatibility_markdown(envelope)
    if kind == "ziwei":
        return _render_ziwei_markdown(envelope)
    raise ArtifactError(f"unsupported artifact kind {kind!r}")


def _render_chart_markdown(envelope: Mapping[str, Any]) -> str:
    name = envelope["input"]["name"]
    lines = [f"# BaZi chart data: {name}", "", f"- Checksum: `{envelope['checksum']}`"]
    if "calendar" in envelope:
        lines.extend(
            [
                f"- Gregorian date: {envelope['calendar']['resolved_gregorian_date']}",
                f"- True solar time: {envelope['time']['true_solar']}",
                f"- Day boundary: {envelope['pillars']['primary']['boundaries']['day_boundary']}",
            ]
        )
    lines.extend(["", "| Pillar | Stem | Branch | Text |", "|---|---|---|---|"])
    for position in ("year", "month", "day", "hour"):
        item = envelope["pillars"]["primary"].get(position)
        if item:
            lines.append(
                f"| {position} | {item.get('stem', '')} | {item.get('branch', '')} | {item.get('text', '')} |"
            )
    if "scores" in envelope:
        scores = envelope["scores"]["primary"]
        lines.extend(
            [
                "",
                "## Numeric model outputs",
                "",
                "| Element | Base % | Adjusted % |",
                "|---|---:|---:|",
            ]
        )
        for element, value in scores["base_distribution"].items():
            lines.append(f"| {element} | {value:.2f} | {scores['adjusted_distribution'][element]:.2f} |")
        strength = scores["day_master_strength"]
        lines.extend(
            [
                "",
                f"- Day-master strength: {strength['score']:.2f}/100 ({strength['classification']})",
                f"- Model: `{scores['model_version']}`",
                "- Semantics: heuristic model output, not probability.",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_ziwei_markdown(envelope: Mapping[str, Any]) -> str:
    name = envelope["input"]["name"]
    chart = envelope["chart"]["primary"]
    lines = [
        f"# Zi Wei chart data: {name}",
        "",
        f"- Checksum: `{envelope['checksum']}`",
        f"- Gregorian date: {envelope['calendar']['resolved_gregorian_date']}",
        f"- Lunar date: {chart['lunar']['text']} {chart['lunar']['hour_branch']}时",
        f"- True solar time: {envelope['time']['true_solar']}",
        f"- Day boundary: {chart['day_boundary']}",
        f"- Year pillar: {chart['year_pillar']['text']} ({chart['year_pillar']['polarity']})",
        f"- Bureau: {chart['bureau']['name']}",
        f"- Life palace: {chart['life_palace']['branch']}",
        f"- Body palace: {chart['body_palace']['branch']} ({chart['body_palace']['palace_name']})",
        "",
        "| Palace | Stem-branch | Stars |",
        "|---|---|---|",
    ]
    for palace in chart["palaces"]:
        stars = "、".join(_star_label(star) for star in palace["stars"]) or "—"
        marks = "".join(
            mark
            for mark, flag in (("命", palace["is_life_palace"]), ("身", palace["is_body_palace"]))
            if flag
        )
        label = f"{palace['name']}{f' [{marks}]' if marks else ''}"
        lines.append(f"| {label} | {palace['stem']}{palace['branch']} | {stars} |")

    lines.extend(["", "## Year transformations", ""])
    for item in chart["transformations"]["placed"]:
        lines.append(f"- {item['star']}化{item['label']} — {item['palace']}宫")
    for item in chart["transformations"]["unplaced"]:
        lines.append(f"- {item} — target star not placed in this release")

    lines.extend(["", "## Decade ranges", "", "| Order | Palace | Ages |", "|---:|---|---|"])
    for decade in chart["decades"]:
        lines.append(
            f"| {decade['order']} | {decade['palace_branch']} {decade['palace_name']} "
            f"| {decade['start_age']}-{decade['end_age']} |"
        )
    lines.extend(
        [
            "",
            f"- Model: `{envelope['methodology']['placement_model']}`",
            "- Placement data only; no interpretation.",
        ]
    )
    return "\n".join(lines) + "\n"


def _star_label(star: Mapping[str, Any]) -> str:
    parts = [str(star["name"])]
    if star.get("brightness"):
        parts.append(f"({star['brightness']})")
    if star.get("transformation"):
        parts.append(f"化{star['transformation']}")
    return "".join(parts)


def _render_compatibility_markdown(envelope: Mapping[str, Any]) -> str:
    left = envelope["people"]["left"]["name"]
    right = envelope["people"]["right"]["name"]
    lines = [
        f"# BaZi compatibility data: {left} and {right}",
        "",
        f"- Checksum: `{envelope['checksum']}`",
        f"- General score: {envelope['scores']['general']:.2f}/100",
        "- Semantics: heuristic model output, not probability.",
        "",
        "| Dimension | Weight | Score |",
        "|---|---:|---:|",
    ]
    for item in envelope["dimensions"]:
        lines.append(f"| {item['name']} | {item['weight']:.2f} | {item['score']:.2f} |")
    return "\n".join(lines) + "\n"
