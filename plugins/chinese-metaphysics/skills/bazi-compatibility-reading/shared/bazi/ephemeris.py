"""Astronomical data boundary used by the BaZi calendar engine."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from os import PathLike
from typing import Protocol, runtime_checkable


class EphemerisUnavailable(RuntimeError):
    """The configured astronomical backend cannot be loaded."""


@runtime_checkable
class Ephemeris(Protocol):
    """Minimum apparent-position interface required by the calendar engine."""

    def julian_day(self, moment: datetime) -> float: ...

    def from_julian_day(self, value: float) -> datetime: ...

    def sun_longitude(self, value: float) -> float: ...

    def moon_longitude(self, value: float) -> float: ...

    def equation_of_time(self, value: float) -> float: ...


class SwissEphemeris:
    """Lazy adapter over pyswisseph using apparent geocentric longitudes."""

    def __init__(self, ephemeris_path: str | PathLike[str] | None = None) -> None:
        try:
            self._swe = importlib.import_module("swisseph")
        except ImportError as error:
            raise EphemerisUnavailable(
                "pyswisseph is required for BaZi astronomy; install it with "
                "`python -m pip install pyswisseph` and retry"
            ) from error
        self._flags = self._swe.FLG_SWIEPH
        if ephemeris_path is not None:
            self._swe.set_ephe_path(str(ephemeris_path))

    def julian_day(self, moment: datetime) -> float:
        if moment.tzinfo is None:
            raise ValueError("julian_day requires a timezone-aware datetime")
        utc = moment.astimezone(UTC)
        hour = utc.hour + utc.minute / 60.0 + utc.second / 3600.0 + utc.microsecond / 3_600_000_000.0
        return float(self._swe.julday(utc.year, utc.month, utc.day, hour, self._swe.GREG_CAL))

    def from_julian_day(self, value: float) -> datetime:
        year, month, day, hour = self._swe.revjul(value, self._swe.GREG_CAL)
        return datetime(year, month, day, tzinfo=UTC) + timedelta(hours=hour)

    def sun_longitude(self, value: float) -> float:
        position, _ = self._swe.calc_ut(value, self._swe.SUN, self._flags)
        return float(position[0] % 360.0)

    def moon_longitude(self, value: float) -> float:
        position, _ = self._swe.calc_ut(value, self._swe.MOON, self._flags)
        return float(position[0] % 360.0)

    def equation_of_time(self, value: float) -> float:
        return float(self._swe.time_equ(value))
