"""Swiss Ephemeris boundary with explicit fallback and provenance handling."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from request_schema import CalculationOptions, ExactBirth, Subject, TimeInterval, resolve_interval

SOFTWARE_VERSION = "2.0"
SAMPLE_INTERVAL = timedelta(minutes=15)

HOUSE_SYSTEMS: Mapping[str, bytes] = {
    "placidus": b"P",
    "koch": b"K",
    "campanus": b"C",
    "regiomontanus": b"R",
    "equal": b"E",
    "whole-sign": b"W",
}
_DATA_PATH_ATTRIBUTE = "_synastry_ephemeris_data_path"


class EphemerisError(RuntimeError):
    """The ephemeris could not resolve a chart under the requested policy."""


@dataclass(frozen=True)
class Limitation:
    """A non-fatal calculation constraint suitable for the artifact contract."""

    code: str
    message: str
    affected_fields: tuple[str, ...]


@dataclass(frozen=True)
class BackendProvenance:
    """The requested and observed calculation backend details."""

    software_version: str
    binding_version: str
    requested_backend: str
    actual_backend: str
    return_flags: tuple[int, ...]
    timezone_source: str
    warnings: tuple[str, ...]
    data_path: str | None = None


@dataclass(frozen=True)
class PositionSamples:
    """One body's measurements at every instant in a resolved interval."""

    longitude_degrees: tuple[float, ...]
    latitude_degrees: tuple[float, ...]
    distance_au: tuple[float, ...]
    longitudinal_speed_degrees_per_day: tuple[float, ...]

    @property
    def retrograde_states(self) -> tuple[bool, ...]:
        """Return each distinct observed retrograde state in stable order."""

        return tuple(dict.fromkeys(speed < 0.0 for speed in self.longitudinal_speed_degrees_per_day))


@dataclass(frozen=True)
class ResolvedChart:
    """Backend measurements for one subject, before artifact derivation."""

    subject_id: str
    precision_mode: str
    interval: TimeInterval
    positions: Mapping[str, PositionSamples]
    houses: tuple[float, ...] | None
    angles: Mapping[str, float]
    provenance: BackendProvenance
    limitations: tuple[Limitation, ...]


@dataclass
class _MutableSamples:
    longitudes: list[float]
    latitudes: list[float]
    distances: list[float]
    speeds: list[float]


class _BindingAdapter:
    """Validate every value crossing the reviewed pyswisseph boundary."""

    def __init__(self, module: Any):
        self.module = module

    def julian_day(self, moment: datetime) -> float:
        hour = (
            moment.hour + moment.minute / 60.0 + moment.second / 3600.0 + moment.microsecond / 3_600_000_000.0
        )
        try:
            result = self.module.julday(moment.year, moment.month, moment.day, hour)
        except self.module.Error as error:
            raise EphemerisError(f"could not calculate Julian day: {_concise(error)}") from error
        except (TypeError, IndexError, ValueError) as error:
            raise EphemerisError(f"Julian day binding returned invalid data: {_concise(error)}") from error
        try:
            return _finite_number(result, "Julian day")
        except (TypeError, ValueError) as error:
            raise EphemerisError(f"Julian day binding returned invalid data: {_concise(error)}") from error

    def calc_ut(self, julian_day: float, code: int, flags: int) -> tuple[tuple[float, ...], int]:
        try:
            result = self.module.calc_ut(julian_day, code, flags)
        except self.module.Error:
            raise
        except (TypeError, IndexError, ValueError) as error:
            raise EphemerisError(f"calc_ut binding returned invalid data: {_concise(error)}") from error
        try:
            outer = _binding_sequence(result, 2, "calc_ut result")
            position = tuple(
                _finite_number(value, f"calc_ut position[{index}]")
                for index, value in enumerate(_binding_sequence(outer[0], 6, "calc_ut position"))
            )
            returned_flags = outer[1]
            if isinstance(returned_flags, bool) or not isinstance(returned_flags, int):
                raise TypeError("invalid calc_ut flags")
        except (TypeError, IndexError, ValueError) as error:
            raise EphemerisError(f"calc_ut binding returned invalid data: {_concise(error)}") from error
        return position, returned_flags

    def houses(
        self,
        julian_day: float,
        latitude: float,
        longitude: float,
        system: bytes,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        try:
            result = self.module.houses(julian_day, latitude, longitude, system)
        except self.module.Error:
            raise
        except (TypeError, IndexError, ValueError) as error:
            raise EphemerisError(f"house binding returned invalid data: {_concise(error)}") from error
        try:
            outer = _binding_sequence(result, 2, "house result")
            cusps = tuple(
                _finite_number(value, f"house cusp[{index}]")
                for index, value in enumerate(_binding_sequence(outer[0], 12, "house cusps"))
            )
            angles = tuple(
                _finite_number(value, f"house angle[{index}]")
                for index, value in enumerate(_binding_sequence(outer[1], 8, "house angles"))
            )
        except (TypeError, IndexError, ValueError) as error:
            raise EphemerisError(f"house binding returned invalid data: {_concise(error)}") from error
        return cusps, angles


def backend_name(flags: int, swe_module: Any) -> str:
    """Name the backend recorded in flags returned by ``calc_ut``."""

    selected = [
        name
        for bit, name in (
            (swe_module.FLG_JPLEPH, "jpl"),
            (swe_module.FLG_SWIEPH, "swiss"),
            (swe_module.FLG_MOSEPH, "moshier"),
        )
        if flags & bit
    ]
    if len(selected) > 1:
        raise EphemerisError(f"ambiguous ephemeris backend in returned flags {flags}")
    if not selected or selected[0] == "jpl":
        raise EphemerisError(f"unrecognized ephemeris backend in returned flags {flags}")
    return selected[0]


def set_ephemeris_path(path: str | None, swe_module: Any | None = None) -> None:
    """Configure and retain a data path without leaking the binding into orchestration."""

    swe = swe_module if swe_module is not None else _load_binding()
    try:
        swe.set_ephe_path(path)
    except swe.Error as error:
        raise EphemerisError(f"could not configure ephemeris path: {_concise(error)}") from error
    setattr(swe, _DATA_PATH_ATTRIBUTE, path)


def resolve_subject(
    subject: Subject,
    options: CalculationOptions,
    swe_module: Any | None = None,
) -> ResolvedChart:
    """Resolve exact or sampled positions and record the backend actually used."""

    _validate_policy(options)
    swe = swe_module if swe_module is not None else _load_binding()
    binding = _BindingAdapter(swe)
    interval, julian_days = _sampling_interval(subject, binding)
    positions, returned_flags, actual_backends, unavailable = _sample_positions(
        julian_days,
        options,
        binding,
    )
    limitations = _limitations(unavailable, actual_backends)
    houses: tuple[float, ...] | None = None
    angles: Mapping[str, float] = {}
    if isinstance(subject.birth, ExactBirth):
        houses, angles = _resolve_houses(julian_days[0], subject.birth, options, binding)
    provenance = _build_provenance(subject, swe, returned_flags, actual_backends, limitations)
    return ResolvedChart(
        subject_id=subject.id,
        precision_mode=subject.birth.mode,
        interval=interval,
        positions=positions,
        houses=houses,
        angles=angles,
        provenance=provenance,
        limitations=limitations,
    )


def _validate_policy(options: CalculationOptions) -> None:
    if options.ephemeris_policy not in {"swiss-only", "allow-moshier"}:
        raise EphemerisError(f"unsupported ephemeris policy {options.ephemeris_policy!r}")


def _sampling_interval(
    subject: Subject,
    binding: _BindingAdapter,
) -> tuple[TimeInterval, tuple[float, ...]]:
    interval = resolve_interval(subject.birth)
    julian_days = tuple(binding.julian_day(moment) for moment in _sample_moments(interval))
    resolved = replace(interval, julian_start=julian_days[0], julian_end=julian_days[-1])
    return resolved, julian_days


def _load_binding() -> Any:
    try:
        import swisseph
    except ImportError as error:  # pragma: no cover - covered by dependency integration in CI
        raise EphemerisError(
            "pyswisseph is not installed; install the pinned synastry requirements"
        ) from error
    return swisseph


def _sample_moments(interval: TimeInterval) -> tuple[datetime, ...]:
    if interval.start_utc == interval.end_utc:
        return (interval.start_utc,)
    moments: list[datetime] = []
    current = interval.start_utc
    while current < interval.end_utc:
        moments.append(current)
        current += SAMPLE_INTERVAL
    moments.append(interval.end_utc)
    return tuple(moments)


def _sample_positions(
    julian_days: tuple[float, ...],
    options: CalculationOptions,
    binding: _BindingAdapter,
) -> tuple[dict[str, PositionSamples], set[int], set[str], set[str]]:
    swe = binding.module
    requested_flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    bodies = _body_codes(swe)
    optional_names = frozenset({"Chiron", "Ceres", "Pallas", "Juno", "Vesta"})
    collected = {
        name: _MutableSamples(longitudes=[], latitudes=[], distances=[], speeds=[]) for name in bodies
    }
    returned_flags: set[int] = set()
    actual_backends: set[str] = set()
    unavailable: set[str] = set()
    for julian_day in julian_days:
        for name, code in bodies.items():
            if name in unavailable:
                continue
            try:
                position, flags = binding.calc_ut(julian_day, code, requested_flags)
            except swe.Error as error:
                if name in optional_names and _is_missing_data_error(error):
                    unavailable.add(name)
                    continue
                raise EphemerisError(f"could not resolve {name}: {_concise(error)}") from error
            _enforce_backend_policy(flags, options, swe, returned_flags, actual_backends)
            samples = collected[name]
            samples.longitudes.append(position[0] % 360.0)
            samples.latitudes.append(position[1])
            samples.distances.append(position[2])
            samples.speeds.append(position[3])
    positions = _freeze_positions(collected, unavailable, len(julian_days))
    positions["South_Node"] = _south_node(positions["North_Node"])
    return positions, returned_flags, actual_backends, unavailable


def _enforce_backend_policy(
    flags: int,
    options: CalculationOptions,
    swe: Any,
    returned_flags: set[int],
    actual_backends: set[str],
) -> None:
    if not flags & swe.FLG_SPEED:
        raise EphemerisError(f"returned flags {flags} did not include requested speed data")
    actual = backend_name(flags, swe)
    if actual != "swiss" and options.ephemeris_policy != "allow-moshier":
        raise EphemerisError(
            "requested Swiss Ephemeris data but used Moshier; provide --ephemeris-path "
            "or explicitly choose allow-moshier"
        )
    returned_flags.add(flags)
    actual_backends.add(actual)


def _build_provenance(
    subject: Subject,
    swe: Any,
    returned_flags: set[int],
    actual_backends: set[str],
    limitations: tuple[Limitation, ...],
) -> BackendProvenance:
    data_path = getattr(swe, _DATA_PATH_ATTRIBUTE, None)
    return BackendProvenance(
        software_version=SOFTWARE_VERSION,
        binding_version=str(getattr(swe, "version", getattr(swe, "__version__", "unknown"))),
        requested_backend="swiss",
        actual_backend="moshier" if "moshier" in actual_backends else "swiss",
        return_flags=tuple(sorted(returned_flags)),
        timezone_source=(
            "explicit-utc-offset" if subject.birth.utc_offset_hours is not None else "iana-zoneinfo"
        ),
        warnings=tuple(item.message for item in limitations),
        data_path=str(data_path) if data_path is not None else None,
    )


def _binding_sequence(value: object, length: int, label: str) -> tuple[object, ...] | list[object]:
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise TypeError(f"invalid {label} shape")
    return value


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"invalid {label} numeric field")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"invalid {label}: numeric field must be finite")
    return number


def _body_codes(swe: Any) -> Mapping[str, int]:
    return {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mercury": swe.MERCURY,
        "Venus": swe.VENUS,
        "Mars": swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO,
        "Chiron": swe.CHIRON,
        "Ceres": swe.CERES,
        "Pallas": swe.PALLAS,
        "Juno": swe.JUNO,
        "Vesta": swe.VESTA,
        "Lilith": swe.MEAN_APOG,
        "North_Node": swe.MEAN_NODE,
    }


def _freeze_positions(
    collected: Mapping[str, _MutableSamples],
    unavailable: set[str],
    expected_samples: int,
) -> dict[str, PositionSamples]:
    positions: dict[str, PositionSamples] = {}
    for name, samples in collected.items():
        if name in unavailable:
            continue
        if len(samples.longitudes) != expected_samples:
            raise EphemerisError(f"incomplete ephemeris samples for {name}")
        positions[name] = PositionSamples(
            longitude_degrees=tuple(samples.longitudes),
            latitude_degrees=tuple(samples.latitudes),
            distance_au=tuple(samples.distances),
            longitudinal_speed_degrees_per_day=tuple(samples.speeds),
        )
    return positions


def _south_node(north_node: PositionSamples) -> PositionSamples:
    return PositionSamples(
        longitude_degrees=tuple((value + 180.0) % 360.0 for value in north_node.longitude_degrees),
        latitude_degrees=tuple(-value for value in north_node.latitude_degrees),
        distance_au=north_node.distance_au,
        longitudinal_speed_degrees_per_day=north_node.longitudinal_speed_degrees_per_day,
    )


def _limitations(unavailable: set[str], actual_backends: set[str]) -> tuple[Limitation, ...]:
    limitations: list[Limitation] = []
    if "moshier" in actual_backends:
        limitations.append(
            Limitation(
                code="ephemeris-fallback",
                message="Moshier calculations were used because Swiss Ephemeris data was unavailable.",
                affected_fields=("positions",),
            )
        )
    if unavailable:
        names = tuple(sorted(unavailable))
        limitations.append(
            Limitation(
                code="optional-ephemeris-data-missing",
                message=f"Optional ephemeris data was unavailable for: {', '.join(names)}.",
                affected_fields=tuple(f"positions.{name}" for name in names),
            )
        )
    return tuple(limitations)


def _resolve_houses(
    julian_day: float,
    birth: ExactBirth,
    options: CalculationOptions,
    binding: _BindingAdapter,
) -> tuple[tuple[float, ...], Mapping[str, float]]:
    try:
        raw_cusps, raw_angles = binding.houses(
            julian_day,
            birth.latitude,
            birth.longitude,
            HOUSE_SYSTEMS[options.house_system],
        )
    except binding.module.Error as error:
        raise EphemerisError(
            f"could not calculate {options.house_system} houses at latitude {birth.latitude:g}: "
            f"{_concise(error)}; choose whole-sign or equal houses explicitly for polar locations"
        ) from error
    cusps = tuple(value % 360.0 for value in raw_cusps)
    ascendant = raw_angles[0] % 360.0
    medium_coeli = raw_angles[1] % 360.0
    angles = {
        "ascendant": ascendant,
        "medium_coeli": medium_coeli,
        "descendant": (ascendant + 180.0) % 360.0,
        "imum_coeli": (medium_coeli + 180.0) % 360.0,
        "vertex": raw_angles[3] % 360.0,
        "east_point": raw_angles[4] % 360.0,
    }
    return cusps, angles


def _concise(error: BaseException) -> str:
    message = " ".join(str(error).split())
    return message or type(error).__name__


def _is_missing_data_error(error: BaseException) -> bool:
    message = _concise(error).casefold()
    if "no such file" in message or "missing file" in message:
        return True
    return "not found" in message and re.search(r"\b(?:file|path)\b", message) is not None
