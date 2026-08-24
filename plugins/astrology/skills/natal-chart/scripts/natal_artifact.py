"""Derive one canonical natal chart artifact from resolved single-subject positions.

Everything here is derivation: the astronomy arrived from `shared/astro`, and
this module turns it into the record a reading is allowed to cite. Nothing is
rounded away that a reader might need, and nothing is asserted that the backend
did not report — an unavailable body becomes a recorded limitation rather than a
silently shorter chart.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astro.astro_math import (
    degrees_in_sign,
    dignities,
    find_aspects,
    format_degrees,
    house_of,
    is_critical,
    is_diurnal,
    lots,
    sign_of,
)
from astro.ephemeris import ResolvedChart
from astro.natal_envelope import (
    SCHEMA,
    SCHEMA_VERSION,
    add_checksum,
    validate_envelope,
)

DERIVATION_MODEL = "natal-chart-v1"
ANGLE_ORDER = ("ascendant", "medium_coeli", "descendant", "imum_coeli", "vertex", "east_point")
LOT_BODIES = ("Sun", "Moon", "Venus", "Jupiter", "Saturn")


class NatalArtifactError(ValueError):
    """A natal artifact cannot be derived or written safely."""


def build_artifact(
    chart: ResolvedChart,
    *,
    display_name: str,
    house_system: str,
    major_orb: float,
    minor_orb: float,
) -> dict[str, Any]:
    """Return one checksummed natal envelope, without writing or interpreting it."""

    if chart.precision_mode != "exact":
        raise NatalArtifactError(
            "a natal chart needs an exact birth time: houses, angles and the sect "
            f"cannot be placed from a {chart.precision_mode} record"
        )
    if not chart.houses:
        raise NatalArtifactError("the backend returned no house cusps")

    longitudes = {name: samples.longitude_degrees[0] for name, samples in chart.positions.items()}
    speeds = {
        name: samples.longitudinal_speed_degrees_per_day[0] for name, samples in chart.positions.items()
    }

    envelope = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "subject": {"name": display_name, "id": chart.subject_id},
        "time": {
            "start": chart.interval.start_utc.isoformat(),
            "end": chart.interval.end_utc.isoformat(),
            "precision_mode": chart.precision_mode,
        },
        "houses": {
            "system": house_system,
            "cusps": [round(cusp, 6) for cusp in chart.houses],
        },
        "angles": _angles(chart.angles),
        "positions": _positions(longitudes, speeds, chart.houses),
        "aspects": _aspects(longitudes, major_orb=major_orb, minor_orb=minor_orb),
        "sect": _sect(longitudes, chart.houses),
        "lots": _lots(longitudes, chart.angles, chart.houses),
        "provenance": {
            "software_version": chart.provenance.software_version,
            "binding_version": chart.provenance.binding_version,
            "requested_backend": chart.provenance.requested_backend,
            "actual_backend": chart.provenance.actual_backend,
            "timezone_source": chart.provenance.timezone_source,
            "warnings": list(chart.provenance.warnings),
        },
        "limitations": [
            {
                "code": limitation.code,
                "message": limitation.message,
                "affected_fields": list(limitation.affected_fields),
            }
            for limitation in chart.limitations
        ],
        "methodology": {
            # Declared here rather than in a rules file, and deliberately: this
            # plugin externalizes nothing, because classical dignities are not a
            # live disagreement the way a Zi Wei transformation table is. See the
            # rules-externalization note in AGENTS.md. One place either way.
            "derivation_model": DERIVATION_MODEL,
            "zodiac": "tropical",
            "dignities": "classical rulerships only; modern assignments are a live disagreement",
            "aspect_orbs": {"major": major_orb, "minor": minor_orb},
            "limits": [
                "static natal chart",
                "no transits",
                "no progressions",
                "no solar or lunar return",
                "no dated event",
                "no forecast",
            ],
        },
    }
    return add_checksum(envelope)


def _angles(angles: Mapping[str, float]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "longitude": round(angles[name], 6),
            "sign": sign_of(angles[name]),
            "degrees_in_sign": round(degrees_in_sign(angles[name]), 6),
            "display": format_degrees(degrees_in_sign(angles[name])),
        }
        for name in ANGLE_ORDER
        if name in angles
    ]


def _positions(
    longitudes: Mapping[str, float],
    speeds: Mapping[str, float],
    cusps: tuple[float, ...],
) -> list[dict[str, Any]]:
    """One record per body, in a stable order so two runs compare byte for byte."""

    return [
        {
            "body": name,
            "longitude": round(longitudes[name], 6),
            "sign": sign_of(longitudes[name]),
            "degrees_in_sign": round(degrees_in_sign(longitudes[name]), 6),
            "display": format_degrees(degrees_in_sign(longitudes[name])),
            "house": house_of(longitudes[name], cusps),
            "retrograde": speeds[name] < 0.0,
            "speed_degrees_per_day": round(speeds[name], 6),
            "dignities": list(dignities(name, sign_of(longitudes[name]))),
            # A body in the first or last degree of a sign changes sign on a small
            # time error. A reading has to know which of its claims sit there.
            "critical_degree": is_critical(longitudes[name]),
        }
        for name in sorted(longitudes)
    ]


def _aspects(longitudes: Mapping[str, float], *, major_orb: float, minor_orb: float) -> list[dict[str, Any]]:
    """Intra-chart aspects, each pair once.

    `find_aspects` compares two sets in full, so a chart against itself yields
    every pair twice plus a conjunction of each body with itself. Keeping one
    ordering drops both without a second aspect implementation.
    """

    found = find_aspects(longitudes, longitudes, major_orb=major_orb, minor_orb=minor_orb)
    return [
        {
            "left": aspect.left,
            "right": aspect.right,
            "kind": aspect.kind,
            "orb": round(aspect.orb, 6),
            "display_orb": f"{aspect.orb:.2f}°",
        }
        for aspect in found
        if aspect.left < aspect.right
    ]


def _sect(longitudes: Mapping[str, float], cusps: tuple[float, ...]) -> dict[str, Any]:
    if "Sun" not in longitudes:
        return {"diurnal": None, "basis": "the Sun was unavailable, so sect is undetermined"}
    diurnal = is_diurnal(longitudes["Sun"], cusps)
    return {
        "diurnal": diurnal,
        "basis": "Sun above the horizon" if diurnal else "Sun below the horizon",
    }


def _lots(
    longitudes: Mapping[str, float],
    angles: Mapping[str, float],
    cusps: tuple[float, ...],
) -> list[dict[str, Any]]:
    """Sect-aware classical lots, or nothing when a required body is missing."""

    missing = [body for body in LOT_BODIES if body not in longitudes]
    if missing or "ascendant" not in angles:
        return []
    computed = lots(
        ascendant=angles["ascendant"],
        sun=longitudes["Sun"],
        moon=longitudes["Moon"],
        venus=longitudes["Venus"],
        jupiter=longitudes["Jupiter"],
        saturn=longitudes["Saturn"],
        diurnal=is_diurnal(longitudes["Sun"], cusps),
    )
    return [
        {
            "name": name,
            "longitude": round(value, 6),
            "sign": sign_of(value),
            "degrees_in_sign": round(degrees_in_sign(value), 6),
            "display": format_degrees(degrees_in_sign(value)),
            "house": house_of(value, cusps),
        }
        for name, value in sorted(computed.items())
    ]


def write_artifact_pair(envelope: Mapping[str, Any], directory: Path) -> tuple[Path, Path]:
    """Write a collision-safe canonical JSON and data-only Markdown pair."""

    validated = validate_envelope(envelope)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"natal_{slugify(str(validated['subject']['name']))}"
    json_bytes = (
        json.dumps(validated, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    markdown_bytes = render_markdown(validated).encode("utf-8")

    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    if _same_pair(json_path, markdown_path, json_bytes, markdown_bytes):
        return json_path.resolve(), markdown_path.resolve()
    if json_path.exists() or markdown_path.exists():
        stem = f"{stem}-{validated['checksum'][:8]}"
        json_path = directory / f"{stem}.json"
        markdown_path = directory / f"{stem}.md"
        if _same_pair(json_path, markdown_path, json_bytes, markdown_bytes):
            return json_path.resolve(), markdown_path.resolve()
        if json_path.exists() or markdown_path.exists():
            raise NatalArtifactError(f"artifact collision at {json_path.name}")

    temporary: list[Path] = []
    try:
        json_temporary = _write_temp(directory, json_bytes)
        temporary.append(json_temporary)
        markdown_temporary = _write_temp(directory, markdown_bytes)
        temporary.append(markdown_temporary)
        os.link(json_temporary, json_path)
        try:
            os.link(markdown_temporary, markdown_path)
        except Exception:
            json_path.unlink(missing_ok=True)
            raise
    except FileExistsError as error:
        raise NatalArtifactError("artifact path changed during atomic creation; retry") from error
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return json_path.resolve(), markdown_path.resolve()


def render_markdown(envelope: Mapping[str, Any]) -> str:
    """Render placement data only. Interpretation belongs to the reading skill."""

    lines = [
        f"# Natal chart data: {envelope['subject']['name']}",
        "",
        f"- Checksum: `{envelope['checksum']}`",
        f"- Instant: {envelope['time']['start']}",
        f"- House system: {envelope['houses']['system']}",
        f"- Sect: {'diurnal' if envelope['sect']['diurnal'] else 'nocturnal'} ({envelope['sect']['basis']})",
        f"- Backend: {envelope['provenance']['actual_backend']}",
        "",
        "## Angles",
        "",
        "| Angle | Sign | Degree |",
        "|---|---|---|",
    ]
    lines.extend(f"| {a['name']} | {a['sign']} | {a['display']} |" for a in envelope["angles"])

    lines.extend(
        [
            "",
            "## Positions",
            "",
            "| Body | Sign | Degree | House | R | Dignities | Critical |",
            "|---|---|---|---:|---|---|---|",
        ]
    )
    for position in envelope["positions"]:
        lines.append(
            f"| {position['body']} | {position['sign']} | {position['display']} | {position['house']} "
            f"| {'R' if position['retrograde'] else ''} | {'/'.join(position['dignities'])} "
            f"| {'yes' if position['critical_degree'] else ''} |"
        )

    lines.extend(["", "## Aspects", "", "| Left | Aspect | Right | Orb |", "|---|---|---|---:|"])
    lines.extend(
        f"| {a['left']} | {a['kind']} | {a['right']} | {a['display_orb']} |" for a in envelope["aspects"]
    )

    if envelope["lots"]:
        lines.extend(["", "## Lots", "", "| Lot | Sign | Degree | House |", "|---|---|---|---:|"])
        lines.extend(
            f"| {lot['name']} | {lot['sign']} | {lot['display']} | {lot['house']} |"
            for lot in envelope["lots"]
        )

    if envelope["limitations"]:
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item['code']}: {item['message']}" for item in envelope["limitations"])

    lines.extend(
        [
            "",
            f"- Model: `{envelope['methodology']['derivation_model']}`",
            f"- Zodiac: {envelope['methodology']['zodiac']}",
            "- Placement data only; no interpretation.",
        ]
    )
    return "\n".join(lines) + "\n"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = re.sub(r"[\\/]+", "-", normalized)
    normalized = re.sub(r"[^\w\-㐀-鿿]+", "-", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[-_]{2,}", "-", normalized).strip(" .-_")
    return normalized or "unnamed"


def _same_pair(json_path: Path, markdown_path: Path, json_bytes: bytes, markdown_bytes: bytes) -> bool:
    return (
        json_path.is_file()
        and markdown_path.is_file()
        and json_path.read_bytes() == json_bytes
        and markdown_path.read_bytes() == markdown_bytes
    )


def _write_temp(directory: Path, content: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".natal-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)
