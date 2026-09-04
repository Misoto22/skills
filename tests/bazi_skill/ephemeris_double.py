"""A dependency-free ephemeris, so the engines can be run without pyswisseph.

The real backend is an AGPL C extension that a contributor may not have
installed, and a suite that skips itself when it is missing tests nothing on the
machine most likely to be missing it. Mean solar motion is wrong by minutes
against the sky and exactly right for these tests: every rule under test reads
the *shape* of what the engines emit, and that shape does not depend on the
ephemeris being accurate — only on it answering.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

TROPICAL_DAYS = 365.2422


class MeanSolarEphemeris:
    """Uniform solar and lunar motion from a fixed epoch."""

    epoch = datetime(2024, 1, 1, tzinfo=UTC)
    rate = 360.0 / TROPICAL_DAYS

    def julian_day(self, moment: datetime) -> float:
        return (moment.astimezone(UTC) - self.epoch).total_seconds() / 86400.0

    def from_julian_day(self, value: float) -> datetime:
        return self.epoch + timedelta(days=value)

    def sun_longitude(self, value: float) -> float:
        return (280.0 + value * self.rate) % 360.0

    def moon_longitude(self, value: float) -> float:
        return (20.0 + value * 13.0) % 360.0

    def equation_of_time(self, value: float) -> float:
        return 0.0
