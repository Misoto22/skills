"""Solar-term and standardized Chinese-calendar calculations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from functools import lru_cache
from itertools import pairwise

from .ephemeris import Ephemeris

BEIJING = timezone(timedelta(hours=8))
ROOT_TOLERANCE_DAYS = 0.5 / 86400.0


class CalendarError(ValueError):
    """A calendar date or astronomical boundary cannot be resolved."""


@dataclass(frozen=True)
class LunarDate:
    """One standardized Chinese lunar date, as Zi Wei Dou Shu needs it."""

    year: int
    month: int
    day: int
    leap: bool

    @property
    def text(self) -> str:
        prefix = "闰" if self.leap else ""
        return f"{self.year}年{prefix}{self.month}月{self.day}日"


@dataclass(frozen=True)
class _LunarMonth:
    lunar_year: int
    number: int
    leap: bool
    start: date
    end: date

    @property
    def length(self) -> int:
        return (self.end - self.start).days


def signed_angle(value: float, target: float) -> float:
    """Return the shortest signed angular difference in [-180, 180)."""

    return (value - target + 180.0) % 360.0 - 180.0


def solar_term_instant(year: int, longitude: float, ephemeris: Ephemeris) -> datetime:
    """Return the UTC instant when the apparent Sun reaches a longitude that year."""

    if not 0.0 <= longitude < 360.0:
        raise CalendarError("solar-term longitude must be from 0 up to but not including 360")
    start = ephemeris.julian_day(datetime(year, 1, 1, tzinfo=UTC))
    end = ephemeris.julian_day(datetime(year + 1, 1, 1, tzinfo=UTC))
    roots = _angle_crossings(
        start,
        end,
        lambda value: signed_angle(ephemeris.sun_longitude(value), longitude),
        step_days=1.0,
    )
    if len(roots) != 1:
        raise CalendarError(f"expected one {longitude:g}° solar crossing in {year}, found {len(roots)}")
    return ephemeris.from_julian_day(roots[0]).astimezone(UTC)


def lunar_to_gregorian(
    year: int,
    month: int,
    day: int,
    leap: bool,
    ephemeris: Ephemeris,
) -> date:
    """Convert one standardized Chinese lunar date to a Gregorian date."""

    if not 1900 <= year <= 2100:
        raise CalendarError("lunar year must be from 1900 through 2100")
    if not 1 <= month <= 12:
        raise CalendarError("lunar month must be from 1 through 12")
    if not 1 <= day <= 30:
        raise CalendarError("lunar day must be from 1 through 30")

    months = [
        item
        for item in (*_sui(year - 1, ephemeris), *_sui(year, ephemeris))
        if item.lunar_year == year and item.number == month and item.leap is leap
    ]
    if len(months) != 1:
        qualifier = "leap " if leap else ""
        raise CalendarError(f"lunar {year} {qualifier}month {month} does not exist")
    selected = months[0]
    if day > selected.length:
        raise CalendarError(
            f"lunar {year} month {month} day {day} does not exist; the month has {selected.length} days"
        )
    return selected.start + timedelta(days=day - 1)


def gregorian_to_lunar(target: date, ephemeris: Ephemeris) -> LunarDate:
    """Convert one Gregorian date to its standardized Chinese lunar date.

    Zi Wei Dou Shu places every star from the lunar month and day, so this is the
    inverse the star engine needs; the four pillars use solar terms instead.
    """

    if not 1900 <= target.year <= 2100:
        raise CalendarError("lunar conversion is supported for 1900 through 2100")
    for winter_year in (target.year - 1, target.year):
        for month in _sui(winter_year, ephemeris):
            if month.start <= target < month.end:
                return LunarDate(
                    year=month.lunar_year,
                    month=month.number,
                    day=(target - month.start).days + 1,
                    leap=month.leap,
                )
    raise CalendarError(f"no lunar month brackets calendar date {target.isoformat()}")


@lru_cache(maxsize=512)
def _sui(winter_year: int, ephemeris: Ephemeris) -> tuple[_LunarMonth, ...]:
    """Build lunar months from one winter-solstice month to the next."""

    first_solstice = solar_term_instant(winter_year, 270.0, ephemeris)
    second_solstice = solar_term_instant(winter_year + 1, 270.0, ephemeris)
    start_jd = ephemeris.julian_day(first_solstice - timedelta(days=40))
    end_jd = ephemeris.julian_day(second_solstice + timedelta(days=40))
    conjunctions = _angle_crossings(
        start_jd,
        end_jd,
        lambda value: signed_angle(ephemeris.moon_longitude(value), ephemeris.sun_longitude(value)),
        step_days=0.5,
    )
    starts = [_beijing_date(ephemeris.from_julian_day(value)) for value in conjunctions]
    starts = list(dict.fromkeys(starts))

    first_index = _month_containing(starts, first_solstice.astimezone(BEIJING).date())
    second_index = _month_containing(starts, second_solstice.astimezone(BEIJING).date())
    count = second_index - first_index
    if count not in (12, 13):
        raise CalendarError(f"expected 12 or 13 lunar months in sui {winter_year}, found {count}")

    month_starts = starts[first_index : second_index + 1]
    leap_index: int | None = None
    if count == 13:
        for index in range(1, count):
            if not _contains_principal_term(month_starts[index], month_starts[index + 1], ephemeris):
                leap_index = index
                break
        if leap_index is None:
            raise CalendarError(f"could not identify the leap month in sui {winter_year}")

    result: list[_LunarMonth] = []
    number = 11
    for index in range(count):
        is_leap = index == leap_index
        if index and not is_leap:
            number = number % 12 + 1
        lunar_year = winter_year if number >= 11 else winter_year + 1
        result.append(
            _LunarMonth(
                lunar_year=lunar_year,
                number=number,
                leap=is_leap,
                start=month_starts[index],
                end=month_starts[index + 1],
            )
        )
    return tuple(result)


def _month_containing(starts: list[date], target: date) -> int:
    for index, (start, end) in enumerate(pairwise(starts)):
        if start <= target < end:
            return index
    raise CalendarError(f"no lunar month brackets calendar date {target.isoformat()}")


def _contains_principal_term(start: date, end: date, ephemeris: Ephemeris) -> bool:
    start_jd = ephemeris.julian_day(datetime.combine(start, time(), BEIJING).astimezone(UTC))
    end_jd = ephemeris.julian_day(datetime.combine(end, time(), BEIJING).astimezone(UTC))
    start_longitude = ephemeris.sun_longitude(start_jd)
    end_longitude = ephemeris.sun_longitude(end_jd)
    traveled = (end_longitude - start_longitude) % 360.0
    distance_to_term = (30.0 - start_longitude % 30.0) % 30.0
    if distance_to_term < 1e-10:
        distance_to_term = 30.0
    return distance_to_term < traveled or abs(distance_to_term - traveled) < 1e-10


def _beijing_date(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(BEIJING).date()


def _angle_crossings(
    start: float,
    end: float,
    residual: Callable[[float], float],
    *,
    step_days: float,
) -> list[float]:
    if end <= start or step_days <= 0:
        raise CalendarError("root search requires an increasing interval and positive step")

    roots: list[float] = []
    left = start
    left_value = residual(left)
    while left < end:
        right = min(left + step_days, end)
        right_value = residual(right)
        if left_value == 0.0:
            root = left
        elif left_value < 0.0 <= right_value and right_value - left_value < 180.0:
            root = _bisect_crossing(left, right, residual)
        else:
            root = None
        if root is not None and (not roots or root - roots[-1] > ROOT_TOLERANCE_DAYS):
            roots.append(root)
        left, left_value = right, right_value
    return roots


def _bisect_crossing(left: float, right: float, residual: Callable[[float], float]) -> float:
    left_value = residual(left)
    right_value = residual(right)
    if not left_value <= 0.0 <= right_value or right_value - left_value >= 180.0:
        raise CalendarError("angular root is not bracketed")
    while right - left > ROOT_TOLERANCE_DAYS:
        middle = (left + right) / 2.0
        middle_value = residual(middle)
        if middle_value < 0.0:
            left = middle
        else:
            right = middle
    return (left + right) / 2.0
