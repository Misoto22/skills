"""Immutable input and normalized-time models for BaZi calculations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

DATE = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")
TIME = re.compile(r"\A(\d{2}):(\d{2})\Z")
CALENDARS = frozenset({"gregorian", "lunar"})


class BirthDataError(ValueError):
    """All input faults from one request, reported in one round trip."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class BirthInput:
    """One fully resolved birth record ready for deterministic calculation."""

    name: str
    birth_place: str
    birth_date: str
    birth_time: str
    calendar: str
    leap_month: bool | None
    gender: str | None
    timezone: str
    latitude: float
    longitude: float
    utc_offset_minutes: float | None
    fold: int | None
    year: int
    month: int
    day: int
    hour: int
    minute: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> BirthInput:
        problems: list[str] = []
        name = _required_text(payload, "name", problems)
        birth_place = _required_text(payload, "birth_place", problems)
        timezone = _required_text(payload, "timezone", problems)

        calendar = str(payload.get("calendar") or "gregorian").lower()
        if calendar not in CALENDARS:
            problems.append(f"calendar: expected gregorian or lunar, got {calendar!r}")

        birth_date = str(payload.get("birth_date") or "")
        year = month = day = 0
        matched_date = DATE.match(birth_date)
        if not matched_date:
            problems.append(f"birth_date: expected YYYY-MM-DD, got {birth_date!r}")
        else:
            year, month, day = (int(part) for part in matched_date.groups())
            if not 1900 <= year <= 2100:
                problems.append("birth_date: supported years are 1900 through 2100")
            if calendar == "lunar":
                if not 1 <= month <= 12 or not 1 <= day <= 30:
                    problems.append("birth_date: lunar month must be 01-12 and day 01-30")
            else:
                try:
                    datetime(year, month, day)
                except ValueError as error:
                    problems.append(f"birth_date: {error}")

        birth_time = str(payload.get("birth_time") or "")
        hour = minute = 0
        matched_time = TIME.match(birth_time)
        if not matched_time:
            problems.append(
                f"birth_time: expected HH:MM in 24-hour form to the exact minute, got {birth_time!r}"
            )
        else:
            hour, minute = (int(part) for part in matched_time.groups())
            if hour > 23 or minute > 59:
                problems.append("birth_time: hour must be 00-23 and minute 00-59")

        leap_month = payload.get("leap_month")
        if calendar == "lunar" and not isinstance(leap_month, bool):
            problems.append("leap_month: lunar input requires an explicit true or false flag")
        elif calendar != "lunar" and leap_month is True:
            problems.append("leap_month: true is only valid for lunar input")
        elif leap_month is not None and not isinstance(leap_month, bool):
            problems.append("leap_month: expected true, false, or null")

        gender_value = payload.get("gender")
        if gender_value is not None and not isinstance(gender_value, str):
            problems.append("gender: expected text when supplied")
        gender = gender_value.strip() if isinstance(gender_value, str) and gender_value.strip() else None

        latitude = _number(payload.get("latitude"), "latitude", 90.0, problems)
        longitude = _number(payload.get("longitude"), "longitude", 180.0, problems)
        offset = _optional_number(payload.get("utc_offset_minutes"), "utc_offset_minutes", problems)
        if offset is not None and not -840 <= offset <= 840:
            problems.append("utc_offset_minutes: expected a value from -840 through 840")

        fold_value = payload.get("fold")
        fold: int | None = None
        if fold_value is not None:
            if type(fold_value) is not int or fold_value not in (0, 1):
                problems.append("fold: expected integer 0 or 1")
            else:
                fold = fold_value

        if problems:
            raise BirthDataError(problems)
        return cls(
            name=name,
            birth_place=birth_place,
            birth_date=birth_date,
            birth_time=birth_time,
            calendar=calendar,
            leap_month=leap_month if isinstance(leap_month, bool) else None,
            gender=gender,
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
            utc_offset_minutes=offset,
            fold=fold,
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return only caller-facing fields, suitable for a second validated parse."""

        result = asdict(self)
        for derived in ("year", "month", "day", "hour", "minute"):
            result.pop(derived)
        return result


@dataclass(frozen=True)
class CivilMoment:
    """The stated wall time resolved to one historical UTC instant."""

    local: datetime
    utc: datetime
    utc_offset_minutes: float
    fold: int
    source: str


@dataclass(frozen=True)
class NormalizedMoment:
    """A civil instant plus the corrections that produce true solar time."""

    local: datetime
    utc: datetime
    utc_offset_minutes: float
    fold: int
    source: str
    longitude_correction_minutes: float
    equation_of_time_minutes: float
    true_solar: datetime


def _required_text(payload: Mapping[str, Any], field: str, problems: list[str]) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{field}: required")
        return ""
    return value.strip()


def _number(value: Any, field: str, limit: float, problems: list[str]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{field}: expected decimal degrees")
        return 0.0
    number = float(value)
    if abs(number) > limit:
        problems.append(f"{field}: {number:g} is outside ±{limit:g}")
    return number


def _optional_number(value: Any, field: str, problems: list[str]) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{field}: expected a numeric minute offset")
        return None
    return float(value)
