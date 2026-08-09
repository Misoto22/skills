"""Closed JSON v2 schema and integrity checks for synastry artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence

KIND = "synastry-chart"
SCHEMA_VERSION = "2.0"
CALCULATION_PROFILE = "western-tropical-v1"
ASPECT_PROFILE = "ptolemaic-minor-v1"
DERIVED_PROFILE = "classical-derived-v1"
EVIDENCE_POLICY = "editorial-v1"

_DIGEST = re.compile(r"\A[0-9a-f]{64}\Z")
_TOP_LEVEL_FIELDS = frozenset(
    {
        "kind",
        "schema_version",
        "chart_id",
        "subjects",
        "configuration",
        "provenance",
        "charts",
        "aspects",
        "overlays",
        "limitations",
        "integrity",
    }
)
_MAJOR_ASPECTS = frozenset({"conjunction", "opposition", "trine", "square", "sextile"})
_MINOR_ASPECTS = frozenset(
    {"semi-sextile", "semi-square", "quintile", "sesquiquadrate", "biquintile", "quincunx"}
)
_ASPECTS = _MAJOR_ASPECTS | _MINOR_ASPECTS
_ANGLE_NAMES = frozenset({"ascendant", "medium_coeli", "descendant", "imum_coeli", "vertex", "east_point"})
_DIGNITIES = frozenset({"domicile", "exaltation", "detriment", "fall"})


class SchemaError(ValueError):
    """A synastry artifact does not satisfy the v2 contract."""


def canonical_json(value: object) -> bytes:
    """Serialize JSON values deterministically for hashing and artifact writes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_digest(document: Mapping[str, object]) -> str:
    """Return the SHA-256 digest of an artifact excluding its integrity envelope."""

    unsigned = {key: value for key, value in document.items() if key != "integrity"}
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


def attach_integrity(document: Mapping[str, object]) -> dict[str, object]:
    """Return a deep-copied artifact with its deterministic integrity envelope."""

    result = copy.deepcopy(dict(document))
    result["integrity"] = {"algorithm": "sha256", "digest": payload_digest(result)}
    return result


def validate_artifact(document: Mapping[str, object]) -> dict[str, object]:
    """Validate and return a deep copy of one complete, closed v2 artifact."""

    if not isinstance(document, Mapping):
        raise SchemaError("artifact: expected an object")
    result = copy.deepcopy(dict(document))
    _reject_non_finite(result, "artifact")
    artifact = _object(result, _TOP_LEVEL_FIELDS, _TOP_LEVEL_FIELDS, "artifact")

    _equal(artifact["kind"], KIND, "artifact.kind")
    _equal(artifact["schema_version"], SCHEMA_VERSION, "artifact.schema_version")
    _string(artifact["chart_id"], "artifact.chart_id")

    subject_ids, subject_modes = _validate_subjects(artifact["subjects"])
    major_orb, minor_orb = _validate_configuration(artifact["configuration"])
    _validate_provenance(artifact["provenance"])
    chart_modes, chart_bodies, chart_houses = _validate_charts(artifact["charts"], subject_ids)
    for subject_id, chart_mode in chart_modes.items():
        if chart_mode != subject_modes[subject_id]:
            raise SchemaError(
                f"artifact.charts: precision {chart_mode!r} does not match "
                f"birth precision {subject_modes[subject_id]!r} for {subject_id!r}"
            )
    _validate_aspects(artifact["aspects"], subject_ids, chart_modes, chart_bodies, major_orb, minor_orb)
    _validate_overlays(artifact["overlays"], subject_ids, chart_modes, chart_bodies, chart_houses)
    _validate_limitations(artifact["limitations"])
    _validate_integrity(artifact, artifact["integrity"])
    return result


def _validate_subjects(value: object) -> tuple[set[str], dict[str, str]]:
    subjects = _list(value, "artifact.subjects")
    if len(subjects) != 2:
        raise SchemaError("artifact.subjects: expected exactly two subjects")

    subject_ids: set[str] = set()
    subject_modes: dict[str, str] = {}
    for index, value in enumerate(subjects):
        subject = _object(
            value,
            {"id", "display_name", "birth"},
            {"id", "birth"},
            f"artifact.subjects[{index}]",
        )
        subject_id = _string(subject["id"], f"artifact.subjects[{index}].id")
        if not subject_id:
            raise SchemaError(f"artifact.subjects[{index}].id: must not be blank")
        if subject_id in subject_ids:
            raise SchemaError(f"artifact.subjects[{index}].id: duplicate subject")
        subject_ids.add(subject_id)
        if "display_name" in subject and subject["display_name"] is not None:
            _string(subject["display_name"], f"artifact.subjects[{index}].display_name")
        subject_modes[subject_id] = _validate_birth(subject["birth"], f"artifact.subjects[{index}].birth")
    return subject_ids, subject_modes


def _validate_birth(value: object, where: str) -> str:
    birth = _object(
        value,
        {
            "mode",
            "utc",
            "utc_start",
            "utc_end",
            "julian_day",
            "julian_start",
            "julian_end",
            "latitude",
            "longitude",
            "date",
            "time",
            "time_window",
            "timezone",
            "timezone_fold",
            "utc_offset_hours",
            "utc_offset_reason",
            "place_label",
            "location_source",
        },
        {"mode"},
        where,
    )
    mode = _enum(birth["mode"], {"exact", "window", "date-only"}, f"{where}.mode")
    for field in (
        "utc",
        "utc_start",
        "utc_end",
        "date",
        "time",
        "timezone",
        "utc_offset_reason",
        "place_label",
        "location_source",
    ):
        if field in birth:
            _string(birth[field], f"{where}.{field}")
    for field in ("julian_day", "julian_start", "julian_end", "latitude", "longitude", "utc_offset_hours"):
        if field in birth:
            _number(birth[field], f"{where}.{field}")
    if "timezone_fold" in birth and birth["timezone_fold"] not in (0, 1):
        raise SchemaError(f"{where}.timezone_fold: expected 0 or 1")
    if "time_window" in birth:
        window = _object(birth["time_window"], {"start", "end"}, {"start", "end"}, f"{where}.time_window")
        _string(window["start"], f"{where}.time_window.start")
        _string(window["end"], f"{where}.time_window.end")
    if mode == "exact" and "utc" not in birth:
        raise SchemaError(f"{where}: exact birth requires utc")
    if mode in {"window", "date-only"} and not ({"utc_start", "utc_end"} <= birth.keys()):
        raise SchemaError(f"{where}: {mode} birth requires utc_start and utc_end")
    return mode


def _validate_configuration(value: object) -> tuple[float, float]:
    configuration = _object(
        value,
        {
            "calculation_profile",
            "aspect_profile",
            "derived_profile",
            "evidence_policy",
            "privacy",
            "language",
            "house_system",
            "major_orb",
            "minor_orb",
            "ephemeris_policy",
            "include_derived",
        },
        {
            "calculation_profile",
            "aspect_profile",
            "derived_profile",
            "privacy",
            "major_orb",
            "minor_orb",
        },
        "artifact.configuration",
    )
    _equal(
        configuration["calculation_profile"],
        CALCULATION_PROFILE,
        "artifact.configuration.calculation_profile",
    )
    _equal(configuration["aspect_profile"], ASPECT_PROFILE, "artifact.configuration.aspect_profile")
    if configuration["derived_profile"] not in (None, DERIVED_PROFILE):
        raise SchemaError("artifact.configuration.derived_profile: unsupported profile")
    _enum(configuration["privacy"], {"minimal", "full"}, "artifact.configuration.privacy")
    if "evidence_policy" in configuration:
        _equal(configuration["evidence_policy"], EVIDENCE_POLICY, "artifact.configuration.evidence_policy")
    for field in ("language", "house_system", "ephemeris_policy"):
        if field in configuration:
            _string(configuration[field], f"artifact.configuration.{field}")
    major_orb = _number(configuration["major_orb"], "artifact.configuration.major_orb")
    minor_orb = _number(configuration["minor_orb"], "artifact.configuration.minor_orb")
    if not 0 <= major_orb <= 15:
        raise SchemaError("artifact.configuration.major_orb: expected a value from 0 through 15")
    if not 0 <= minor_orb <= 7.5:
        raise SchemaError("artifact.configuration.minor_orb: expected a value from 0 through 7.5")
    if "include_derived" in configuration and not isinstance(configuration["include_derived"], bool):
        raise SchemaError("artifact.configuration.include_derived: expected a boolean")
    return major_orb, minor_orb


def _validate_provenance(value: object) -> None:
    provenance = _object(
        value,
        {
            "software_version",
            "binding_version",
            "requested_backend",
            "actual_backend",
            "return_flags",
            "timezone_source",
            "warnings",
            "data_path",
        },
        {
            "software_version",
            "binding_version",
            "requested_backend",
            "actual_backend",
            "return_flags",
            "timezone_source",
            "warnings",
        },
        "artifact.provenance",
    )
    for field in (
        "software_version",
        "binding_version",
        "requested_backend",
        "actual_backend",
        "timezone_source",
    ):
        _string(provenance[field], f"artifact.provenance.{field}")
    if "data_path" in provenance and provenance["data_path"] is not None:
        _string(provenance["data_path"], "artifact.provenance.data_path")
    for index, flag in enumerate(_list(provenance["return_flags"], "artifact.provenance.return_flags")):
        _integer(flag, f"artifact.provenance.return_flags[{index}]")
    for index, warning in enumerate(_list(provenance["warnings"], "artifact.provenance.warnings")):
        _string(warning, f"artifact.provenance.warnings[{index}]")


def _validate_charts(
    value: object, subject_ids: set[str]
) -> tuple[dict[str, str], dict[str, set[str]], dict[str, bool]]:
    charts = _list(value, "artifact.charts")
    if len(charts) != len(subject_ids):
        raise SchemaError("artifact.charts: expected one chart per subject")

    modes: dict[str, str] = {}
    bodies: dict[str, set[str]] = {}
    calculated_houses: dict[str, bool] = {}
    for index, value in enumerate(charts):
        chart = _object(
            value,
            {"subject_id", "precision_mode", "positions", "houses", "angles", "derived", "limitations"},
            {"subject_id", "precision_mode", "positions", "derived"},
            f"artifact.charts[{index}]",
        )
        subject_id = _owner(chart["subject_id"], subject_ids, f"artifact.charts[{index}].subject_id")
        if subject_id in modes:
            raise SchemaError(f"artifact.charts[{index}].subject_id: duplicate chart")
        mode = _enum(
            chart["precision_mode"],
            {"exact", "window", "date-only"},
            f"artifact.charts[{index}].precision_mode",
        )
        positions = _object(chart["positions"], None, None, f"artifact.charts[{index}].positions")
        if not positions:
            raise SchemaError(f"artifact.charts[{index}].positions: must not be empty")
        body_names: set[str] = set()
        for body, position in positions.items():
            _string(body, f"artifact.charts[{index}].positions key")
            if not body:
                raise SchemaError(f"artifact.charts[{index}].positions: body name must not be blank")
            if mode == "exact":
                _validate_exact_position(position, f"artifact.charts[{index}].positions.{body}")
            else:
                _validate_uncertain_position(position, f"artifact.charts[{index}].positions.{body}")
            body_names.add(body)
        _validate_derived(chart["derived"], f"artifact.charts[{index}].derived")
        if mode == "exact":
            if "houses" in chart:
                houses = _list(chart["houses"], f"artifact.charts[{index}].houses")
                if len(houses) != 12:
                    raise SchemaError(f"artifact.charts[{index}].houses: expected twelve cusps")
                for house_index, cusp in enumerate(houses):
                    _longitude(cusp, f"artifact.charts[{index}].houses[{house_index}]")
            if "angles" in chart:
                _validate_angles(chart["angles"], f"artifact.charts[{index}].angles")
        elif "houses" in chart or "angles" in chart:
            raise SchemaError(f"artifact.charts[{index}]: uncertain charts cannot include houses or angles")
        if "limitations" in chart:
            _validate_limitations(chart["limitations"], f"artifact.charts[{index}].limitations")
        modes[subject_id] = mode
        bodies[subject_id] = body_names
        calculated_houses[subject_id] = "houses" in chart
    if set(modes) != subject_ids:
        raise SchemaError("artifact.charts: chart ownership does not match subjects")
    return modes, bodies, calculated_houses


def _validate_angles(value: object, where: str) -> None:
    angles = _object(value, _ANGLE_NAMES, None, where)
    for name, longitude in angles.items():
        _longitude(longitude, f"{where}.{name}")


def _validate_derived(value: object, where: str) -> None:
    derived = _object(value, {"sect", "dignities", "lots"}, None, where)
    if "sect" in derived:
        _enum(derived["sect"], {"diurnal", "nocturnal"}, f"{where}.sect")
    if "dignities" in derived:
        dignities = _object(derived["dignities"], None, None, f"{where}.dignities")
        for body, values in dignities.items():
            _string(body, f"{where}.dignities key")
            for index, dignity in enumerate(_list(values, f"{where}.dignities.{body}")):
                _enum(dignity, _DIGNITIES, f"{where}.dignities.{body}[{index}]")
    if "lots" in derived:
        lots = _object(derived["lots"], None, None, f"{where}.lots")
        for name, longitude in lots.items():
            _string(name, f"{where}.lots key")
            _longitude(longitude, f"{where}.lots.{name}")


def _validate_exact_position(value: object, where: str) -> None:
    position = _object(
        value,
        {
            "longitude_degrees",
            "latitude_degrees",
            "distance_au",
            "longitudinal_speed_degrees_per_day",
            "retrograde",
            "sign",
            "house",
        },
        {
            "longitude_degrees",
            "latitude_degrees",
            "distance_au",
            "longitudinal_speed_degrees_per_day",
            "retrograde",
            "sign",
        },
        where,
    )
    _longitude(position["longitude_degrees"], f"{where}.longitude_degrees")
    _number(position["latitude_degrees"], f"{where}.latitude_degrees")
    _number(position["distance_au"], f"{where}.distance_au")
    _number(position["longitudinal_speed_degrees_per_day"], f"{where}.longitudinal_speed_degrees_per_day")
    if not isinstance(position["retrograde"], bool):
        raise SchemaError(f"{where}.retrograde: expected a boolean")
    _string(position["sign"], f"{where}.sign")
    if "house" in position:
        house = _integer(position["house"], f"{where}.house")
        if not 1 <= house <= 12:
            raise SchemaError(f"{where}.house: expected a house from 1 through 12")


def _validate_uncertain_position(value: object, where: str) -> None:
    position = _object(
        value,
        {"longitude_range", "max_span_degrees", "signs", "retrograde_states"},
        {"longitude_range", "max_span_degrees", "signs", "retrograde_states"},
        where,
    )
    longitude_range = _object(
        position["longitude_range"],
        {"start_degrees", "end_degrees", "wraps_zero"},
        {"start_degrees", "end_degrees", "wraps_zero"},
        f"{where}.longitude_range",
    )
    _longitude(longitude_range["start_degrees"], f"{where}.longitude_range.start_degrees")
    _longitude(longitude_range["end_degrees"], f"{where}.longitude_range.end_degrees")
    if not isinstance(longitude_range["wraps_zero"], bool):
        raise SchemaError(f"{where}.longitude_range.wraps_zero: expected a boolean")
    span = _number(position["max_span_degrees"], f"{where}.max_span_degrees")
    if not 0 <= span <= 360:
        raise SchemaError(f"{where}.max_span_degrees: expected a value from 0 through 360")
    signs = _list(position["signs"], f"{where}.signs")
    if not signs:
        raise SchemaError(f"{where}.signs: must not be empty")
    for index, sign in enumerate(signs):
        _string(sign, f"{where}.signs[{index}]")
    states = _list(position["retrograde_states"], f"{where}.retrograde_states")
    if not states:
        raise SchemaError(f"{where}.retrograde_states: must not be empty")
    for index, state in enumerate(states):
        if not isinstance(state, bool):
            raise SchemaError(f"{where}.retrograde_states[{index}]: expected a boolean")


def _validate_aspects(
    value: object,
    subject_ids: set[str],
    chart_modes: dict[str, str],
    chart_bodies: dict[str, set[str]],
    major_orb: float,
    minor_orb: float,
) -> None:
    for index, item in enumerate(_list(value, "artifact.aspects")):
        aspect = _object(
            item,
            {
                "source_subject_id",
                "target_subject_id",
                "source_body",
                "target_body",
                "kind",
                "certainty",
                "orb_degrees",
                "orb_range_degrees",
            },
            {"source_subject_id", "target_subject_id", "source_body", "target_body", "kind", "certainty"},
            f"artifact.aspects[{index}]",
        )
        source = _owner(
            aspect["source_subject_id"], subject_ids, f"artifact.aspects[{index}].source_subject_id"
        )
        target = _owner(
            aspect["target_subject_id"], subject_ids, f"artifact.aspects[{index}].target_subject_id"
        )
        if source == target:
            raise SchemaError(f"artifact.aspects[{index}]: source and target subjects must differ")
        _body_owner(aspect["source_body"], chart_bodies[source], f"artifact.aspects[{index}].source_body")
        _body_owner(aspect["target_body"], chart_bodies[target], f"artifact.aspects[{index}].target_body")
        kind = _enum(aspect["kind"], _ASPECTS, f"artifact.aspects[{index}].kind")
        certainty = _enum(
            aspect["certainty"], {"exact", "confirmed", "possible"}, f"artifact.aspects[{index}].certainty"
        )
        allowed_orb = major_orb if kind in _MAJOR_ASPECTS else minor_orb
        if certainty == "exact":
            if chart_modes[source] != "exact" or chart_modes[target] != "exact":
                raise SchemaError(f"artifact.aspects[{index}]: exact aspect requires exact charts")
            if "orb_degrees" not in aspect:
                raise SchemaError(f"artifact.aspects[{index}]: exact aspect requires orb_degrees")
            if "orb_range_degrees" in aspect:
                raise SchemaError(f"artifact.aspects[{index}]: exact aspect cannot carry orb_range_degrees")
            _configured_orb(aspect["orb_degrees"], allowed_orb, f"artifact.aspects[{index}].orb_degrees")
        else:
            if chart_modes[source] == "exact" and chart_modes[target] == "exact":
                raise SchemaError(f"artifact.aspects[{index}]: uncertain aspect requires an uncertain chart")
            if "orb_range_degrees" not in aspect:
                raise SchemaError(f"artifact.aspects[{index}]: uncertain aspect requires orb_range_degrees")
            if "orb_degrees" in aspect:
                raise SchemaError(f"artifact.aspects[{index}]: uncertain aspect cannot carry orb_degrees")
            _validate_orb_range(
                aspect["orb_range_degrees"], allowed_orb, f"artifact.aspects[{index}].orb_range_degrees"
            )


def _validate_orb_range(value: object, allowed_orb: float, where: str) -> None:
    orb_range = _object(
        value, {"minimum_degrees", "maximum_degrees"}, {"minimum_degrees", "maximum_degrees"}, where
    )
    minimum = _configured_orb(orb_range["minimum_degrees"], allowed_orb, f"{where}.minimum_degrees")
    maximum = _configured_orb(orb_range["maximum_degrees"], allowed_orb, f"{where}.maximum_degrees")
    if minimum > maximum:
        raise SchemaError(f"{where}: minimum_degrees must not exceed maximum_degrees")


def _validate_overlays(
    value: object,
    subject_ids: set[str],
    chart_modes: dict[str, str],
    chart_bodies: dict[str, set[str]],
    chart_houses: dict[str, bool],
) -> None:
    for index, item in enumerate(_list(value, "artifact.overlays")):
        overlay = _object(
            item,
            {"source_subject_id", "target_subject_id", "source_body", "target_house"},
            {"source_subject_id", "target_subject_id", "source_body", "target_house"},
            f"artifact.overlays[{index}]",
        )
        source = _owner(
            overlay["source_subject_id"], subject_ids, f"artifact.overlays[{index}].source_subject_id"
        )
        target = _owner(
            overlay["target_subject_id"], subject_ids, f"artifact.overlays[{index}].target_subject_id"
        )
        if source == target:
            raise SchemaError(f"artifact.overlays[{index}]: source and target subjects must differ")
        if chart_modes[source] != "exact" or chart_modes[target] != "exact":
            raise SchemaError(f"artifact.overlays[{index}]: overlays require exact charts")
        if not chart_houses[source] or not chart_houses[target]:
            raise SchemaError(
                f"artifact.overlays[{index}]: overlays require calculated houses for both charts"
            )
        _body_owner(overlay["source_body"], chart_bodies[source], f"artifact.overlays[{index}].source_body")
        house = _integer(overlay["target_house"], f"artifact.overlays[{index}].target_house")
        if not 1 <= house <= 12:
            raise SchemaError(f"artifact.overlays[{index}].target_house: expected a house from 1 through 12")


def _validate_limitations(value: object, where: str = "artifact.limitations") -> None:
    for index, item in enumerate(_list(value, where)):
        limitation = _object(
            item,
            {"code", "message", "affected_fields"},
            {"code", "message", "affected_fields"},
            f"{where}[{index}]",
        )
        _string(limitation["code"], f"{where}[{index}].code")
        _string(limitation["message"], f"{where}[{index}].message")
        for field_index, field in enumerate(
            _list(limitation["affected_fields"], f"{where}[{index}].affected_fields")
        ):
            _string(field, f"{where}[{index}].affected_fields[{field_index}]")


def _validate_integrity(artifact: Mapping[str, object], value: object) -> None:
    integrity = _object(value, {"algorithm", "digest"}, {"algorithm", "digest"}, "artifact.integrity")
    _equal(integrity["algorithm"], "sha256", "artifact.integrity.algorithm")
    digest = _string(integrity["digest"], "artifact.integrity.digest")
    if not _DIGEST.fullmatch(digest):
        raise SchemaError("artifact.integrity.digest: expected a lowercase SHA-256 digest")
    if digest != payload_digest(artifact):
        raise SchemaError("artifact.integrity.digest: digest mismatch")


def _object(
    value: object,
    allowed: set[str] | frozenset[str] | None,
    required: set[str] | frozenset[str] | None,
    where: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{where}: expected an object")
    result = dict(value)
    if not all(isinstance(key, str) for key in result):
        raise SchemaError(f"{where}: object keys must be strings")
    if allowed is not None:
        unknown = sorted(set(result) - allowed)
        if unknown:
            raise SchemaError(f"{where}: unknown field {unknown[0]!r}")
    if required is not None:
        missing = sorted(required - set(result))
        if missing:
            raise SchemaError(f"{where}: missing required field {missing[0]!r}")
    return result


def _list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise SchemaError(f"{where}: expected an array")
    return value


def _string(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{where}: expected a string")
    return value


def _number(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{where}: expected a number")
    number = float(value)
    if not math.isfinite(number):
        raise SchemaError(f"{where}: non-finite number")
    return number


def _integer(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{where}: expected an integer")
    return value


def _enum(value: object, choices: set[str], where: str) -> str:
    selected = _string(value, where)
    if selected not in choices:
        raise SchemaError(f"{where}: expected one of {sorted(choices)!r}")
    return selected


def _equal(value: object, expected: str, where: str) -> None:
    if value != expected:
        raise SchemaError(f"{where}: expected {expected!r}")


def _longitude(value: object, where: str) -> float:
    longitude = _number(value, where)
    if not 0 <= longitude < 360:
        raise SchemaError(f"{where}: expected a longitude from 0 up to 360")
    return longitude


def _orb(value: object, where: str) -> float:
    orb = _number(value, where)
    if not 0 <= orb <= 180:
        raise SchemaError(f"{where}: expected an orb from 0 through 180")
    return orb


def _configured_orb(value: object, allowed_orb: float, where: str) -> float:
    orb = _orb(value, where)
    if orb > allowed_orb:
        raise SchemaError(f"{where}: exceeds the configured orb of {allowed_orb:g}")
    return orb


def _owner(value: object, subject_ids: set[str], where: str) -> str:
    subject_id = _string(value, where)
    if subject_id not in subject_ids:
        raise SchemaError(f"{where}: unknown subject {subject_id!r}")
    return subject_id


def _body_owner(value: object, bodies: set[str], where: str) -> None:
    body = _string(value, where)
    if body not in bodies:
        raise SchemaError(f"{where}: body is not present in its owner's chart")


def _reject_non_finite(value: object, where: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise SchemaError(f"{where}: non-finite number")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_non_finite(item, f"{where}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_non_finite(item, f"{where}[{index}]")
