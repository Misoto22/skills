"""Strict v2 synastry request parsing and civil-time resolution."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = "2.0"
CALCULATION_PROFILE = "western-tropical-v1"
ASPECT_PROFILE = "ptolemaic-minor-v1"
DERIVED_PROFILE = "classical-derived-v1"
EVIDENCE_POLICY = "editorial-v1"

_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
_TIME = re.compile(r"\A\d{2}:\d{2}\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_HOUSE_SYSTEMS = frozenset({"placidus", "koch", "campanus", "regiomontanus", "equal", "whole-sign"})
_LANGUAGES = frozenset({"en", "zh"})
_EPHEMERIS_POLICIES = frozenset({"swiss-only", "allow-moshier"})
_PRIVACY_MODES = frozenset({"minimal", "full"})


class RequestError(ValueError):
    """A request has one or more validation problems."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class ExactBirth:
    mode: str
    date: date
    time: time
    time_accuracy_minutes: int
    timezone: str
    timezone_fold: int | None
    latitude: float
    longitude: float
    utc_offset_hours: float | None
    utc_offset_reason: str | None
    place_label: str | None
    location_source: str | None


@dataclass(frozen=True)
class WindowBirth:
    mode: str
    date: date
    start: time
    end: time
    timezone: str
    utc_offset_hours: float | None
    utc_offset_reason: str | None
    place_label: str | None
    location_source: str | None


@dataclass(frozen=True)
class DateOnlyBirth:
    mode: str
    date: date
    timezone: str
    utc_offset_hours: float | None
    utc_offset_reason: str | None
    place_label: str | None
    location_source: str | None


@dataclass(frozen=True)
class Subject:
    id: str
    display_name: str | None
    pronouns: str | None
    birth: ExactBirth | WindowBirth | DateOnlyBirth


@dataclass(frozen=True)
class CalculationOptions:
    language: str
    house_system: str
    major_orb: float
    minor_orb: float
    ephemeris_policy: str
    calculation_profile: str
    aspect_profile: str
    include_derived: bool
    privacy: str


@dataclass(frozen=True)
class RelationshipContext:
    description: str
    requested_domains: tuple[str, ...]


@dataclass(frozen=True)
class SynastryRequest:
    people: tuple[Subject, Subject]
    options: CalculationOptions
    relationship_context: RelationshipContext


@dataclass(frozen=True)
class TimeInterval:
    start_utc: datetime
    end_utc: datetime
    julian_start: float | None = None
    julian_end: float | None = None


def parse_request(payload: object) -> SynastryRequest:
    """Parse one closed v2 request and collect every independent violation."""

    problems: list[str] = []
    request = _object(
        payload,
        {"schema_version", "people", "options", "relationship_context"},
        {"schema_version", "people", "options", "relationship_context"},
        "request",
        problems,
    )
    if request is None:
        raise RequestError(problems)

    if request.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"request.schema_version: expected {SCHEMA_VERSION!r}")
    people = _parse_people(request.get("people"), problems)
    options = _parse_options(request.get("options"), problems)
    relationship_context = _parse_relationship_context(request.get("relationship_context"), problems)
    if problems:
        raise RequestError(problems)
    assert people is not None
    assert options is not None
    assert relationship_context is not None
    return SynastryRequest(people=people, options=options, relationship_context=relationship_context)


def resolve_interval(birth: ExactBirth | WindowBirth | DateOnlyBirth) -> TimeInterval:
    """Resolve a validated birth record into its UTC instant or uncertainty interval."""

    if isinstance(birth, ExactBirth):
        moment = _resolve_local(
            datetime.combine(birth.date, birth.time),
            birth.timezone,
            birth.timezone_fold,
            birth.utc_offset_hours,
            birth.utc_offset_reason,
            "birth",
        )
        return TimeInterval(moment, moment)

    if isinstance(birth, WindowBirth):
        start = _resolve_local(
            datetime.combine(birth.date, birth.start),
            birth.timezone,
            None,
            birth.utc_offset_hours,
            birth.utc_offset_reason,
            "birth.time_window.start",
        )
        end = _resolve_local(
            datetime.combine(birth.date, birth.end),
            birth.timezone,
            None,
            birth.utc_offset_hours,
            birth.utc_offset_reason,
            "birth.time_window.end",
        )
        if end <= start:
            raise RequestError(["birth.time_window: end must be after start"])
        return TimeInterval(start, end)

    start = _resolve_local(
        datetime.combine(birth.date, time.min),
        birth.timezone,
        None,
        birth.utc_offset_hours,
        birth.utc_offset_reason,
        "birth.date",
    )
    try:
        following_date = birth.date + timedelta(days=1)
    except OverflowError as error:
        raise RequestError(["birth.date: date-only interval exceeds the supported calendar range"]) from error
    end = _resolve_local(
        datetime.combine(following_date, time.min),
        birth.timezone,
        None,
        birth.utc_offset_hours,
        birth.utc_offset_reason,
        "birth.date",
    )
    return TimeInterval(start, end)


def canonical_request(request: SynastryRequest) -> dict[str, object]:
    """Return a JSON-ready, deterministic representation of a parsed v2 request."""

    return {
        "schema_version": SCHEMA_VERSION,
        "people": [_canonical_subject(subject) for subject in request.people],
        "options": {
            "language": request.options.language,
            "house_system": request.options.house_system,
            "major_orb": request.options.major_orb,
            "minor_orb": request.options.minor_orb,
            "ephemeris_policy": request.options.ephemeris_policy,
            "calculation_profile": request.options.calculation_profile,
            "aspect_profile": request.options.aspect_profile,
            "include_derived": request.options.include_derived,
            "privacy": request.options.privacy,
        },
        "relationship_context": {
            "description": request.relationship_context.description,
            "requested_domains": list(request.relationship_context.requested_domains),
        },
    }


def _parse_people(value: object, problems: list[str]) -> tuple[Subject, Subject] | None:
    if not isinstance(value, list):
        problems.append("request.people: expected an array")
        return None
    if len(value) != 2:
        problems.append("request.people: expected exactly two subjects")
        return None
    parsed = [_parse_subject(entry, index, problems) for index, entry in enumerate(value)]
    identities = [subject.id for subject in parsed if subject is not None]
    if len(set(identities)) != len(identities):
        problems.append("request.people: duplicate subject id")
    if any(subject is None for subject in parsed):
        return None
    return parsed[0], parsed[1]


def _parse_subject(value: object, index: int, problems: list[str]) -> Subject | None:
    where = f"request.people[{index}]"
    subject = _object(value, {"id", "display_name", "pronouns", "birth"}, {"id", "birth"}, where, problems)
    if subject is None:
        return None
    subject_id = _label(subject.get("id"), f"{where}.id", problems, required=True)
    display_name = _label(subject.get("display_name"), f"{where}.display_name", problems)
    pronouns = _label(subject.get("pronouns"), f"{where}.pronouns", problems)
    birth = _parse_birth(subject.get("birth"), f"{where}.birth", problems)
    if subject_id is None or birth is None:
        return None
    return Subject(id=subject_id, display_name=display_name, pronouns=pronouns, birth=birth)


def _parse_birth(
    value: object, where: str, problems: list[str]
) -> ExactBirth | WindowBirth | DateOnlyBirth | None:
    birth = _object(value, None, {"date", "time_mode", "timezone"}, where, problems)
    if birth is None:
        return None
    mode = birth.get("time_mode")
    if not isinstance(mode, str):
        problems.append(f"{where}.time_mode: expected a string")
        return None
    if mode not in {"exact", "window", "date-only"}:
        problems.append(f"{where}.time_mode: unsupported mode {mode!r}")
        return None
    allowed = {
        "exact": {
            "date",
            "time_mode",
            "time",
            "time_accuracy_minutes",
            "timezone",
            "timezone_fold",
            "latitude",
            "longitude",
            "utc_offset_hours",
            "utc_offset_reason",
            "place_label",
            "location_source",
        },
        "window": {
            "date",
            "time_mode",
            "time_window",
            "timezone",
            "utc_offset_hours",
            "utc_offset_reason",
            "place_label",
            "location_source",
        },
        "date-only": {
            "date",
            "time_mode",
            "timezone",
            "utc_offset_hours",
            "utc_offset_reason",
            "place_label",
            "location_source",
        },
    }[mode]
    for field in sorted(set(birth) - allowed):
        problems.append(f"{where}.{field}: unknown field")

    parsed_date = _civil_date(birth.get("date"), f"{where}.date", problems)
    timezone_name = _timezone_name(birth.get("timezone"), f"{where}.timezone", problems)
    offset, reason = _offset_override(birth, where, problems)
    place_label = _label(birth.get("place_label"), f"{where}.place_label", problems)
    location_source = _label(birth.get("location_source"), f"{where}.location_source", problems)

    if mode == "exact":
        parsed_time = _civil_time(birth.get("time"), f"{where}.time", problems)
        accuracy = _integer(
            birth.get("time_accuracy_minutes"),
            f"{where}.time_accuracy_minutes",
            problems,
            minimum=0,
            maximum=15,
        )
        latitude = _number(birth.get("latitude"), f"{where}.latitude", problems, minimum=-90, maximum=90)
        longitude = _number(birth.get("longitude"), f"{where}.longitude", problems, minimum=-180, maximum=180)
        fold = _fold(birth.get("timezone_fold"), f"{where}.timezone_fold", problems)
        if None in (parsed_date, timezone_name, parsed_time, accuracy, latitude, longitude):
            return None
        result = ExactBirth(
            mode=mode,
            date=parsed_date,
            time=parsed_time,
            time_accuracy_minutes=accuracy,
            timezone=timezone_name,
            timezone_fold=fold,
            latitude=latitude,
            longitude=longitude,
            utc_offset_hours=offset,
            utc_offset_reason=reason,
            place_label=place_label,
            location_source=location_source,
        )
    elif mode == "window":
        window = _parse_window(birth.get("time_window"), f"{where}.time_window", problems)
        if parsed_date is None or timezone_name is None or window is None:
            return None
        result = WindowBirth(
            mode=mode,
            date=parsed_date,
            start=window[0],
            end=window[1],
            timezone=timezone_name,
            utc_offset_hours=offset,
            utc_offset_reason=reason,
            place_label=place_label,
            location_source=location_source,
        )
    else:
        if parsed_date is None or timezone_name is None:
            return None
        result = DateOnlyBirth(
            mode=mode,
            date=parsed_date,
            timezone=timezone_name,
            utc_offset_hours=offset,
            utc_offset_reason=reason,
            place_label=place_label,
            location_source=location_source,
        )

    try:
        resolve_interval(result)
    except RequestError as error:
        problems.extend(error.problems)
        return None
    return result


def _parse_options(value: object, problems: list[str]) -> CalculationOptions | None:
    where = "request.options"
    allowed = {
        "language",
        "house_system",
        "major_orb",
        "minor_orb",
        "ephemeris_policy",
        "calculation_profile",
        "aspect_profile",
        "include_derived",
        "privacy",
    }
    options = _object(value, allowed, allowed, where, problems)
    if options is None:
        return None
    language = _enum(options.get("language"), _LANGUAGES, f"{where}.language", problems)
    house_system = _enum(options.get("house_system"), _HOUSE_SYSTEMS, f"{where}.house_system", problems)
    major_orb = _number(options.get("major_orb"), f"{where}.major_orb", problems, minimum=0, maximum=15)
    minor_orb = _number(options.get("minor_orb"), f"{where}.minor_orb", problems, minimum=0, maximum=7.5)
    policy = _enum(
        options.get("ephemeris_policy"),
        _EPHEMERIS_POLICIES,
        f"{where}.ephemeris_policy",
        problems,
    )
    calculation_profile = _profile(
        options.get("calculation_profile"), CALCULATION_PROFILE, f"{where}.calculation_profile", problems
    )
    aspect_profile = _profile(
        options.get("aspect_profile"),
        ASPECT_PROFILE,
        f"{where}.aspect_profile",
        problems,
    )
    include_derived = options.get("include_derived")
    if not isinstance(include_derived, bool):
        problems.append(f"{where}.include_derived: expected a boolean")
        include_derived = None
    privacy = _enum(options.get("privacy"), _PRIVACY_MODES, f"{where}.privacy", problems)
    if None in (
        language,
        house_system,
        major_orb,
        minor_orb,
        policy,
        calculation_profile,
        aspect_profile,
        include_derived,
        privacy,
    ):
        return None
    return CalculationOptions(
        language=language,
        house_system=house_system,
        major_orb=major_orb,
        minor_orb=minor_orb,
        ephemeris_policy=policy,
        calculation_profile=calculation_profile,
        aspect_profile=aspect_profile,
        include_derived=include_derived,
        privacy=privacy,
    )


def _parse_relationship_context(value: object, problems: list[str]) -> RelationshipContext | None:
    where = "request.relationship_context"
    context = _object(
        value,
        {"description", "requested_domains"},
        {"description", "requested_domains"},
        where,
        problems,
    )
    if context is None:
        return None
    description = _label(context.get("description"), f"{where}.description", problems, required=True)
    domains_value = context.get("requested_domains")
    domains: list[str] = []
    if not isinstance(domains_value, list):
        problems.append(f"{where}.requested_domains: expected an array")
    else:
        for index, domain in enumerate(domains_value):
            parsed = _label(domain, f"{where}.requested_domains[{index}]", problems, required=True)
            if parsed is not None:
                domains.append(parsed)
    if description is None or not isinstance(domains_value, list) or len(domains) != len(domains_value):
        return None
    return RelationshipContext(description=description, requested_domains=tuple(domains))


def _object(
    value: object,
    allowed: set[str] | None,
    required: set[str],
    where: str,
    problems: list[str],
) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        problems.append(f"{where}: expected an object")
        return None
    for field in sorted(required - value.keys()):
        problems.append(f"{where}.{field}: required")
    if allowed is not None:
        for field in sorted(value.keys() - allowed):
            problems.append(f"{where}.{field}: unknown field")
    return value


def _label(value: object, where: str, problems: list[str], *, required: bool = False) -> str | None:
    if value is None:
        if required:
            problems.append(f"{where}: required")
        return None
    if not isinstance(value, str):
        problems.append(f"{where}: expected a string")
        return None
    if not value.strip():
        problems.append(f"{where}: must not be blank")
    if _CONTROL.search(value):
        problems.append(f"{where}: must not contain a control character")
    if len(value) > 120:
        problems.append(f"{where}: must be at most 120 Unicode code points")
    if not value.strip() or _CONTROL.search(value) or len(value) > 120:
        return None
    return value


def _civil_date(value: object, where: str, problems: list[str]) -> date | None:
    if not isinstance(value, str):
        problems.append(f"{where}: required valid calendar date in YYYY-MM-DD form")
        return None
    if not _DATE.fullmatch(value):
        problems.append(f"{where}: expected YYYY-MM-DD valid calendar date")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        problems.append(f"{where}: expected a valid calendar date")
        return None


def _civil_time(value: object, where: str, problems: list[str]) -> time | None:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        problems.append(f"{where}: expected valid 24-hour time in HH:MM form")
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        problems.append(f"{where}: expected a valid 24-hour time")
        return None


def _timezone_name(value: object, where: str, problems: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        problems.append(f"{where}: required IANA timezone")
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        problems.append(f"{where}: unknown IANA timezone {value!r}")
        return None
    return value


def _number(
    value: object,
    where: str,
    problems: list[str],
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{where}: expected a number")
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        problems.append(f"{where}: expected a finite number")
        return None
    if not math.isfinite(number):
        problems.append(f"{where}: expected a finite number")
        return None
    if not minimum <= number <= maximum:
        problems.append(f"{where}: expected a value from {minimum:g} through {maximum:g}")
        return None
    return number


def _integer(value: object, where: str, problems: list[str], *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        problems.append(f"{where}: expected an integer")
        return None
    if not minimum <= value <= maximum:
        problems.append(f"{where}: expected a value from {minimum} through {maximum}")
        return None
    return value


def _fold(value: object, where: str, problems: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or value not in (0, 1):
        problems.append(f"{where}: expected 0 or 1")
        return None
    return int(value)


def _offset_override(
    value: Mapping[str, object], where: str, problems: list[str]
) -> tuple[float | None, str | None]:
    offset_value = value.get("utc_offset_hours")
    reason_value = value.get("utc_offset_reason")
    if offset_value is None:
        if reason_value is not None:
            problems.append(f"{where}.utc_offset_reason: requires utc_offset_hours")
        return None, None
    if isinstance(offset_value, bool) or not isinstance(offset_value, (int, float)):
        problems.append(f"{where}.utc_offset_hours: expected a number")
        return None, None
    try:
        offset = float(offset_value)
    except (OverflowError, ValueError):
        problems.append(f"{where}.utc_offset_hours: expected a finite number")
        return None, None
    representable = False
    if not math.isfinite(offset):
        problems.append(f"{where}.utc_offset_hours: expected a finite number")
    elif not -24 < offset < 24:
        problems.append(f"{where}.utc_offset_hours: expected a value between -24 and 24")
    else:
        try:
            timezone(timedelta(hours=offset))
        except (OverflowError, ValueError):
            problems.append(f"{where}.utc_offset_hours: is not representable as a UTC offset")
        else:
            representable = True
    reason = _label(reason_value, f"{where}.utc_offset_reason", problems, required=True)
    if not math.isfinite(offset) or not -24 < offset < 24 or not representable or reason is None:
        return None, None
    return offset, reason


def _parse_window(value: object, where: str, problems: list[str]) -> tuple[time, time] | None:
    window = _object(value, {"start", "end"}, {"start", "end"}, where, problems)
    if window is None:
        return None
    start = _civil_time(window.get("start"), f"{where}.start", problems)
    end = _civil_time(window.get("end"), f"{where}.end", problems)
    if start is None or end is None:
        return None
    if end <= start:
        problems.append(f"{where}: end must be after start")
        return None
    return start, end


def _enum(value: object, allowed: frozenset[str], where: str, problems: list[str]) -> str | None:
    if not isinstance(value, str):
        problems.append(f"{where}: expected a string")
        return None
    if value not in allowed:
        problems.append(f"{where}: unsupported value {value!r}")
        return None
    return str(value)


def _profile(value: object, expected: str, where: str, problems: list[str]) -> str | None:
    if value != expected:
        problems.append(f"{where}: unsupported profile {value!r}")
        return None
    return expected


def _valid_candidates(local_naive: datetime, zone: ZoneInfo) -> dict[int, datetime]:
    candidates: dict[int, datetime] = {}
    for fold in (0, 1):
        aware = local_naive.replace(tzinfo=zone, fold=fold)
        round_trip = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if round_trip == local_naive:
            candidates[fold] = aware
    return candidates


def _resolve_local(
    local_naive: datetime,
    timezone_name: str,
    fold: int | None,
    utc_offset_hours: float | None,
    utc_offset_reason: str | None,
    where: str,
) -> datetime:
    zone = ZoneInfo(timezone_name)
    candidates = _valid_candidates(local_naive, zone)
    if not candidates:
        raise RequestError([f"{where}: nonexistent local time in {timezone_name!r}"])
    offsets = {candidate.utcoffset() for candidate in candidates.values()}
    ambiguous = len(candidates) == 2 and len(offsets) == 2
    if ambiguous and fold is None and utc_offset_hours is None:
        raise RequestError(
            [f"{where}: ambiguous local time requires timezone_fold or a reasoned utc_offset_hours override"]
        )
    if not ambiguous and fold is not None:
        raise RequestError([f"{where}: timezone_fold is allowed only for ambiguous exact times"])
    if utc_offset_hours is not None:
        assert utc_offset_reason is not None
        return local_naive.replace(tzinfo=timezone(timedelta(hours=utc_offset_hours))).astimezone(UTC)
    if fold is None:
        return next(iter(candidates.values())).astimezone(UTC)
    return candidates[fold].astimezone(UTC)


def _canonical_subject(subject: Subject) -> dict[str, object]:
    result: dict[str, object] = {"id": subject.id, "birth": _canonical_birth(subject.birth)}
    if subject.display_name is not None:
        result["display_name"] = subject.display_name
    if subject.pronouns is not None:
        result["pronouns"] = subject.pronouns
    return result


def _canonical_birth(birth: ExactBirth | WindowBirth | DateOnlyBirth) -> dict[str, object]:
    result: dict[str, object] = {
        "date": birth.date.isoformat(),
        "time_mode": birth.mode,
        "timezone": birth.timezone,
    }
    if isinstance(birth, ExactBirth):
        result.update(
            time=birth.time.strftime("%H:%M"),
            time_accuracy_minutes=birth.time_accuracy_minutes,
            latitude=birth.latitude,
            longitude=birth.longitude,
        )
        if birth.timezone_fold is not None:
            result["timezone_fold"] = birth.timezone_fold
    elif isinstance(birth, WindowBirth):
        result["time_window"] = {"start": birth.start.strftime("%H:%M"), "end": birth.end.strftime("%H:%M")}
    if birth.utc_offset_hours is not None:
        result["utc_offset_hours"] = birth.utc_offset_hours
        result["utc_offset_reason"] = birth.utc_offset_reason
    if birth.place_label is not None:
        result["place_label"] = birth.place_label
    if birth.location_source is not None:
        result["location_source"] = birth.location_source
    return result
