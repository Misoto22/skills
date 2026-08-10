#!/usr/bin/env python3
"""Construct and safely persist canonical synastry v2 artifacts."""

from __future__ import annotations

import errno
import hashlib
import os
import re
import secrets
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from astro_math import (
    circular_range,
    dignities,
    find_aspects,
    find_uncertain_aspects,
    house_of,
    is_diurnal,
    lots,
    sign_of,
)
from ephemeris import Limitation, PositionSamples, ResolvedChart
from request_schema import DateOnlyBirth, ExactBirth, Subject, SynastryRequest, WindowBirth, resolve_interval
from synastry_schema import (
    DERIVED_PROFILE,
    EVIDENCE_POLICY,
    KIND,
    SCHEMA_VERSION,
    SchemaError,
    attach_integrity,
    canonical_json,
    validate_artifact,
)

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_UNSAFE_IN_FILENAME = re.compile(r"[^\w-]+", re.UNICODE)
_CHART_ID = re.compile(r"\A[0-9a-f]{12}\Z")
_FILENAME_MAX_BYTES = 255
_PLANETS = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)


class ArtifactExistsError(FileExistsError):
    """The deterministic artifact destination already exists."""


_ASPECT_EXCLUDED = frozenset({"South_Node", "East_Point"})


def chart_id(request: SynastryRequest) -> str:
    """Return the stable identifier for normalized calculation inputs."""

    normalized = {
        "people": [
            {
                "id": subject.id,
                "birth": _calculation_birth(subject.birth),
            }
            for subject in request.people
        ],
        "options": {
            "house_system": request.options.house_system,
            "major_orb": request.options.major_orb,
            "minor_orb": request.options.minor_orb,
            "ephemeris_policy": request.options.ephemeris_policy,
            "calculation_profile": request.options.calculation_profile,
            "aspect_profile": request.options.aspect_profile,
            "include_derived": request.options.include_derived,
        },
    }
    return hashlib.sha256(canonical_json(normalized)).hexdigest()[:12]


def output_name(request: SynastryRequest) -> str:
    """Return the deterministic, path-safe filename for one request."""

    left, right = (_subject_filename(subject.display_name, subject.id) for subject in request.people)
    return _output_filename(left, right, chart_id(request))


def build_artifact(
    request: SynastryRequest,
    charts: Sequence[ResolvedChart],
) -> dict[str, object]:
    """Project resolved charts into a validated, integrity-protected v2 artifact."""

    ordered_charts = _order_charts(request, charts)
    document: dict[str, object] = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "chart_id": chart_id(request),
        "subjects": [
            _subject_document(subject, chart, request.options.privacy)
            for subject, chart in zip(request.people, ordered_charts, strict=True)
        ],
        "configuration": {
            "calculation_profile": request.options.calculation_profile,
            "aspect_profile": request.options.aspect_profile,
            "derived_profile": DERIVED_PROFILE if request.options.include_derived else None,
            "evidence_policy": EVIDENCE_POLICY,
            "privacy": request.options.privacy,
            "language": request.options.language,
            "house_system": request.options.house_system,
            "major_orb": request.options.major_orb,
            "minor_orb": request.options.minor_orb,
            "ephemeris_policy": request.options.ephemeris_policy,
            "include_derived": request.options.include_derived,
        },
        "provenance": _merge_provenance(ordered_charts),
        "charts": [_chart_document(chart, request.options.include_derived) for chart in ordered_charts],
        "aspects": _aspects_document(request, ordered_charts),
        "overlays": _overlays_document(ordered_charts),
        "limitations": _global_limitations(ordered_charts),
    }
    return validate_artifact(attach_integrity(document))


def write_artifact(
    document: Mapping[str, object],
    output_directory: str | os.PathLike[str],
    overwrite: bool = False,
) -> Path:
    """Atomically write canonical JSON without replacing an existing file by default."""

    validated = validate_artifact(document)
    filename = _artifact_output_name(validated)
    directory = Path(output_directory).expanduser()
    destination = directory / filename
    payload = canonical_json(validated) + b"\n"
    temporary: Path | None = None
    descriptor: int | None = None

    directory.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(32):
            candidate = directory / (f".synastry-{validated['chart_id']}-{secrets.token_hex(8)}.tmp")
            try:
                descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            break
        if temporary is None or descriptor is None:
            raise FileExistsError(errno.EEXIST, "could not allocate an exclusive temporary file")

        descriptor_chmod = getattr(os, "fchmod", None)
        if descriptor_chmod is not None:
            descriptor_chmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError("could not complete artifact write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None

        if overwrite:
            os.replace(temporary, destination)
            temporary = None
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as error:
                raise ArtifactExistsError(
                    errno.EEXIST,
                    f"output already exists; pass --overwrite to replace it: {destination}",
                    destination,
                ) from error
            temporary.unlink()
            temporary = None
        return destination
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            with suppress(FileNotFoundError):
                temporary.unlink()


def _calculation_birth(birth: ExactBirth | WindowBirth | DateOnlyBirth) -> dict[str, object]:
    interval = resolve_interval(birth)
    if isinstance(birth, ExactBirth):
        return {
            "mode": birth.mode,
            "utc": _utc(interval.start_utc),
            "time_accuracy_minutes": birth.time_accuracy_minutes,
            "latitude": birth.latitude,
            "longitude": birth.longitude,
        }
    return {
        "mode": birth.mode,
        "utc_start": _utc(interval.start_utc),
        "utc_end": _utc(interval.end_utc),
    }


def _subject_document(subject: Subject, chart: ResolvedChart, privacy: str) -> dict[str, object]:
    birth = subject.birth
    interval = chart.interval
    if isinstance(birth, ExactBirth):
        projected_birth: dict[str, object] = {
            "mode": birth.mode,
            "utc": _utc(interval.start_utc),
            "julian_day": _required_julian(interval.julian_start, subject.id),
            "latitude": birth.latitude,
            "longitude": birth.longitude,
        }
    else:
        projected_birth = {
            "mode": birth.mode,
            "utc_start": _utc(interval.start_utc),
            "utc_end": _utc(interval.end_utc),
            "julian_start": _required_julian(interval.julian_start, subject.id),
            "julian_end": _required_julian(interval.julian_end, subject.id),
        }

    if privacy == "full":
        projected_birth.update(_archival_birth(birth))

    projected: dict[str, object] = {"id": subject.id, "birth": projected_birth}
    if subject.display_name is not None:
        projected["display_name"] = subject.display_name
    return projected


def _archival_birth(birth: ExactBirth | WindowBirth | DateOnlyBirth) -> dict[str, object]:
    result: dict[str, object] = {
        "date": birth.date.isoformat(),
        "timezone": birth.timezone,
    }
    if isinstance(birth, ExactBirth):
        result["time"] = birth.time.strftime("%H:%M")
        if birth.timezone_fold is not None:
            result["timezone_fold"] = birth.timezone_fold
    elif isinstance(birth, WindowBirth):
        result["time_window"] = {
            "start": birth.start.strftime("%H:%M"),
            "end": birth.end.strftime("%H:%M"),
        }
    for field in (
        "utc_offset_hours",
        "utc_offset_reason",
        "place_label",
        "location_source",
    ):
        value = getattr(birth, field)
        if value is not None:
            result[field] = value
    return result


def _chart_document(chart: ResolvedChart, include_derived: bool) -> dict[str, object]:
    positions: dict[str, object] = {}
    for body, samples in chart.positions.items():
        if chart.precision_mode == "exact":
            positions[body] = _exact_position(body, samples, chart.houses)
        else:
            positions[body] = _uncertain_position(samples)

    result: dict[str, object] = {
        "subject_id": chart.subject_id,
        "precision_mode": chart.precision_mode,
        "positions": positions,
        "derived": _derived_document(chart) if include_derived else {},
    }
    if chart.houses is not None:
        result["houses"] = list(chart.houses)
    if chart.angles:
        result["angles"] = dict(chart.angles)
    limitations = _all_limitations(chart)
    if limitations:
        result["limitations"] = [_limitation_document(item) for item in limitations]
    return result


def _exact_position(
    body: str,
    samples: PositionSamples,
    houses: tuple[float, ...] | None,
) -> dict[str, object]:
    if not all(
        len(values) == 1
        for values in (
            samples.longitude_degrees,
            samples.latitude_degrees,
            samples.distance_au,
            samples.longitudinal_speed_degrees_per_day,
        )
    ):
        raise SchemaError(f"chart position {body!r}: exact precision requires one complete sample")
    longitude = samples.longitude_degrees[0] % 360.0
    result: dict[str, object] = {
        "longitude_degrees": longitude,
        "latitude_degrees": samples.latitude_degrees[0],
        "distance_au": samples.distance_au[0],
        "longitudinal_speed_degrees_per_day": samples.longitudinal_speed_degrees_per_day[0],
        "retrograde": samples.longitudinal_speed_degrees_per_day[0] < 0.0,
        "sign": sign_of(longitude),
    }
    if houses is not None:
        result["house"] = house_of(longitude, houses)
    return result


def _uncertain_position(samples: PositionSamples) -> dict[str, object]:
    longitude_range = circular_range(samples.longitude_degrees)
    return {
        "longitude_range": {
            "start_degrees": longitude_range.start_degrees,
            "end_degrees": longitude_range.end_degrees,
            "wraps_zero": longitude_range.wraps_zero,
        },
        "max_span_degrees": longitude_range.span_degrees,
        "signs": _range_signs(
            longitude_range.start_degrees,
            longitude_range.end_degrees,
            longitude_range.wraps_zero,
        ),
        "retrograde_states": list(samples.retrograde_states),
    }


def _range_signs(start: float, end: float, wraps_zero: bool) -> list[str]:
    signs = ("Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis")
    segments = ((start, 360.0), (0.0, end)) if wraps_zero else ((start, end),)
    return [
        sign
        for index, sign in enumerate(signs)
        if any(
            segment_start < (index + 1) * 30.0 and segment_end >= index * 30.0
            for segment_start, segment_end in segments
        )
    ]


def _derived_document(chart: ResolvedChart) -> dict[str, object]:
    if chart.precision_mode != "exact":
        return {}
    exact = {body: samples.longitude_degrees[0] for body, samples in chart.positions.items()}
    derived: dict[str, object] = {
        "dignities": {
            body: list(states)
            for body, longitude in exact.items()
            if (states := dignities(body, sign_of(longitude)))
        }
    }
    required = {"Sun", "Moon", "Venus", "Jupiter", "Saturn"}
    if chart.houses is not None and "ascendant" in chart.angles and required <= exact.keys():
        diurnal = is_diurnal(exact["Sun"], chart.houses)
        derived["sect"] = "diurnal" if diurnal else "nocturnal"
        derived["lots"] = lots(
            ascendant=chart.angles["ascendant"],
            sun=exact["Sun"],
            moon=exact["Moon"],
            venus=exact["Venus"],
            jupiter=exact["Jupiter"],
            saturn=exact["Saturn"],
            diurnal=diurnal,
        )
    return derived


def _aspects_document(
    request: SynastryRequest,
    charts: tuple[ResolvedChart, ResolvedChart],
) -> list[dict[str, object]]:
    left, right = charts
    left_samples = _aspect_samples(left)
    right_samples = _aspect_samples(right)
    common = {
        "source_subject_id": left.subject_id,
        "target_subject_id": right.subject_id,
    }
    if left.precision_mode == right.precision_mode == "exact":
        aspects = find_aspects(
            {name: values[0] for name, values in left_samples.items()},
            {name: values[0] for name, values in right_samples.items()},
            major_orb=request.options.major_orb,
            minor_orb=request.options.minor_orb,
        )
        return [
            {
                **common,
                "source_body": aspect.left,
                "target_body": aspect.right,
                "kind": aspect.kind,
                "certainty": "exact",
                "orb_degrees": aspect.orb,
            }
            for aspect in aspects
        ]

    evidence = find_uncertain_aspects(
        left_samples,
        right_samples,
        request.options.major_orb,
        request.options.minor_orb,
    )
    return [
        {
            **common,
            "source_body": aspect.left,
            "target_body": aspect.right,
            "kind": aspect.kind,
            "certainty": aspect.certainty,
            "orb_range_degrees": {
                "minimum_degrees": aspect.minimum_orb,
                "maximum_degrees": aspect.maximum_orb,
            },
        }
        for aspect in evidence
    ]


def _aspect_samples(chart: ResolvedChart) -> dict[str, tuple[float, ...]]:
    return {
        body: samples.longitude_degrees
        for body, samples in chart.positions.items()
        if body not in _ASPECT_EXCLUDED
    }


def _overlays_document(charts: tuple[ResolvedChart, ResolvedChart]) -> list[dict[str, object]]:
    if any(chart.precision_mode != "exact" or chart.houses is None for chart in charts):
        return []
    overlays: list[dict[str, object]] = []
    for source, target in (charts, charts[::-1]):
        assert target.houses is not None
        for body in _PLANETS:
            samples = source.positions.get(body)
            if samples is None:
                continue
            overlays.append(
                {
                    "source_subject_id": source.subject_id,
                    "target_subject_id": target.subject_id,
                    "source_body": body,
                    "target_house": house_of(samples.longitude_degrees[0], target.houses),
                }
            )
    return overlays


def _merge_provenance(charts: tuple[ResolvedChart, ResolvedChart]) -> dict[str, object]:
    provenances = tuple(chart.provenance for chart in charts)
    for field in ("software_version", "binding_version", "requested_backend", "data_path"):
        values = {getattr(item, field) for item in provenances}
        if len(values) != 1:
            raise SchemaError(f"artifact provenance: charts disagree on {field}")
    actual_backend = "moshier" if any(item.actual_backend == "moshier" for item in provenances) else "swiss"
    timezone_sources = sorted({item.timezone_source for item in provenances})
    result: dict[str, object] = {
        "software_version": provenances[0].software_version,
        "binding_version": provenances[0].binding_version,
        "requested_backend": provenances[0].requested_backend,
        "actual_backend": actual_backend,
        "return_flags": sorted({flag for item in provenances for flag in item.return_flags}),
        "timezone_source": timezone_sources[0] if len(timezone_sources) == 1 else ",".join(timezone_sources),
        "warnings": list(dict.fromkeys(warning for item in provenances for warning in item.warnings)),
    }
    if provenances[0].data_path is not None:
        result["data_path"] = provenances[0].data_path
    return result


def _global_limitations(charts: tuple[ResolvedChart, ResolvedChart]) -> list[dict[str, object]]:
    return [
        {
            "code": limitation.code,
            "message": limitation.message,
            "affected_fields": [f"charts.{chart.subject_id}.{field}" for field in limitation.affected_fields],
        }
        for chart in charts
        for limitation in _all_limitations(chart)
    ]


def _all_limitations(chart: ResolvedChart) -> tuple[Limitation, ...]:
    return (*chart.limitations, *_uncertainty_limitations(chart))


def _uncertainty_limitations(chart: ResolvedChart) -> tuple[Limitation, ...]:
    if chart.precision_mode == "exact":
        return ()
    limitations: list[Limitation] = []
    if "Moon" in chart.positions:
        limitations.append(
            Limitation(
                code="time-uncertain-moon",
                message="The Moon position varies across the birth-time interval.",
                affected_fields=("positions.Moon",),
            )
        )
    sign_changes = tuple(
        f"positions.{body}.signs"
        for body, samples in chart.positions.items()
        if len(_range_signs_from_samples(samples)) > 1
    )
    if sign_changes:
        limitations.append(
            Limitation(
                code="sign-boundary-uncertainty",
                message="One or more bodies cross a sign boundary within the birth-time interval.",
                affected_fields=sign_changes,
            )
        )
    retrograde_changes = tuple(
        f"positions.{body}.retrograde_states"
        for body, samples in chart.positions.items()
        if len(samples.retrograde_states) > 1
    )
    if retrograde_changes:
        limitations.append(
            Limitation(
                code="retrograde-state-uncertainty",
                message="One or more bodies change retrograde state within the birth-time interval.",
                affected_fields=retrograde_changes,
            )
        )
    return tuple(limitations)


def _range_signs_from_samples(samples: PositionSamples) -> list[str]:
    longitude_range = circular_range(samples.longitude_degrees)
    return _range_signs(
        longitude_range.start_degrees,
        longitude_range.end_degrees,
        longitude_range.wraps_zero,
    )


def _limitation_document(limitation: Limitation) -> dict[str, object]:
    return {
        "code": limitation.code,
        "message": limitation.message,
        "affected_fields": list(limitation.affected_fields),
    }


def _order_charts(
    request: SynastryRequest,
    charts: Sequence[ResolvedChart],
) -> tuple[ResolvedChart, ResolvedChart]:
    by_subject = {chart.subject_id: chart for chart in charts}
    expected = {subject.id for subject in request.people}
    if len(charts) != 2 or len(by_subject) != 2 or set(by_subject) != expected:
        raise SchemaError("resolved charts must contain exactly one chart for each request subject")
    ordered = by_subject[request.people[0].id], by_subject[request.people[1].id]
    for subject, chart in zip(request.people, ordered, strict=True):
        if chart.precision_mode != subject.birth.mode:
            raise SchemaError(
                f"resolved chart {subject.id!r} precision does not match its request birth mode"
            )
        interval = resolve_interval(subject.birth)
        if chart.interval.start_utc != interval.start_utc or chart.interval.end_utc != interval.end_utc:
            raise SchemaError(f"resolved chart {subject.id!r} UTC interval does not match its request")
    return ordered


def _artifact_output_name(document: Mapping[str, object]) -> str:
    identifier = document["chart_id"]
    if not isinstance(identifier, str) or not _CHART_ID.fullmatch(identifier):
        raise ValueError("chart_id must be twelve lowercase hexadecimal characters")
    subjects = document["subjects"]
    if not isinstance(subjects, list) or len(subjects) != 2:
        raise ValueError("artifact must contain two subjects for a safe filename")
    names = []
    for subject in subjects:
        if not isinstance(subject, Mapping):
            raise ValueError("artifact subject cannot form a safe filename")
        label = subject.get("display_name") or subject.get("id")
        if not isinstance(label, str):
            raise ValueError("artifact subject cannot form a safe filename")
        names.append(_filename_label(label))
    return _output_filename(names[0], names[1], identifier)


def _subject_filename(display_name: str | None, subject_id: str) -> str:
    return _filename_label(display_name or subject_id)


def _filename_label(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("control characters cannot form a safe filename")
    normalized = unicodedata.normalize("NFKC", value)
    slug = _UNSAFE_IN_FILENAME.sub("-", normalized).strip("-_")
    if not slug or slug in {".", ".."}:
        raise ValueError("subject label cannot form a safe filename")
    return slug


def _output_filename(left: str, right: str, identifier: str) -> str:
    fixed_bytes = len(f"synastry___{identifier}.json".encode())
    label_budget = _FILENAME_MAX_BYTES - fixed_bytes
    left_size = len(left.encode("utf-8"))
    right_size = len(right.encode("utf-8"))
    left_budget = min(left_size, label_budget // 2)
    right_budget = min(right_size, label_budget - left_budget)
    left_budget = min(left_size, label_budget - right_budget)
    filename = (
        f"synastry_{_truncate_utf8(left, left_budget)}_"
        f"{_truncate_utf8(right, right_budget)}_{identifier}.json"
    )
    if len(filename.encode("utf-8")) > _FILENAME_MAX_BYTES:  # pragma: no cover - invariant guard
        raise ValueError("artifact filename exceeds the filesystem byte limit")
    return filename


def _truncate_utf8(value: str, byte_limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= byte_limit:
        return value
    return encoded[:byte_limit].decode("utf-8", errors="ignore")


def _required_julian(value: float | None, subject_id: str) -> float:
    if value is None:
        raise SchemaError(f"resolved chart {subject_id!r} is missing its Julian interval")
    return value


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
