"""Resolve historical civil time and convert it to local apparent solar time."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import BirthDataError, BirthInput, CivilMoment, NormalizedMoment


def resolve_civil_time(birth: BirthInput) -> CivilMoment:
    """Resolve one wall time, refusing DST folds and gaps rather than guessing."""

    naive = datetime(birth.year, birth.month, birth.day, birth.hour, birth.minute)
    if birth.utc_offset_minutes is not None:
        zone = timezone(timedelta(minutes=birth.utc_offset_minutes))
        local = naive.replace(tzinfo=zone)
        return _civil(local, source="explicit-offset")

    try:
        zone = ZoneInfo(birth.timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise BirthDataError(
            [f"timezone: {birth.timezone!r} is not a known IANA zone; resolve the birthplace again"]
        ) from error

    candidates = [naive.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid = [candidate for candidate in candidates if _round_trips(candidate, naive, zone)]
    distinct_offsets = {candidate.utcoffset() for candidate in valid}

    if not valid:
        raise BirthDataError(
            [f"birth_time: {birth.birth_date} {birth.birth_time} does not exist in {birth.timezone}"]
        )
    if len(distinct_offsets) > 1:
        if birth.fold is None:
            raise BirthDataError(
                [
                    f"birth_time: {birth.birth_date} {birth.birth_time} is ambiguous in"
                    f" {birth.timezone}; supply fold 0 or 1, or an explicit UTC offset"
                ]
            )
        selected = next(candidate for candidate in valid if candidate.fold == birth.fold)
    else:
        if birth.fold == 1:
            raise BirthDataError(["fold: 1 was supplied for a civil time that is not repeated"])
        selected = valid[0]
    return _civil(selected, source="iana")


def apply_true_solar_time(
    birth: BirthInput, moment: CivilMoment, equation_of_time_days: float
) -> NormalizedMoment:
    """Apply longitude and equation-of-time corrections without hiding either one."""

    longitude_correction = 4.0 * birth.longitude - moment.utc_offset_minutes
    equation_minutes = equation_of_time_days * 1440.0
    true_solar = moment.local.replace(tzinfo=None) + timedelta(
        minutes=longitude_correction + equation_minutes
    )
    return NormalizedMoment(
        local=moment.local,
        utc=moment.utc,
        utc_offset_minutes=moment.utc_offset_minutes,
        fold=moment.fold,
        source=moment.source,
        longitude_correction_minutes=longitude_correction,
        equation_of_time_minutes=equation_minutes,
        true_solar=true_solar,
    )


def _round_trips(candidate: datetime, naive: datetime, zone: ZoneInfo) -> bool:
    returned = candidate.astimezone(UTC).astimezone(zone)
    return returned.replace(tzinfo=None) == naive and returned.fold == candidate.fold


def _civil(local: datetime, *, source: str) -> CivilMoment:
    offset = local.utcoffset()
    if offset is None:  # pragma: no cover - every selected datetime is zone-aware
        raise BirthDataError(["timezone: resolved no UTC offset"])
    return CivilMoment(
        local=local,
        utc=local.astimezone(UTC),
        utc_offset_minutes=offset.total_seconds() / 60.0,
        fold=local.fold,
        source=source,
    )
