"""Derive the four sexagenary pillars from normalized birth time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from .calendar import solar_term_instant
from .ephemeris import Ephemeris
from .models import BirthInput, NormalizedMoment

STEMS = tuple("甲乙丙丁戊己庚辛壬癸")
BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")
DAY_ANCHOR = date(2000, 1, 7)
JIE = (
    (315.0, 2, "立春"),
    (345.0, 3, "惊蛰"),
    (15.0, 4, "清明"),
    (45.0, 5, "立夏"),
    (75.0, 6, "芒种"),
    (105.0, 7, "小暑"),
    (135.0, 8, "立秋"),
    (165.0, 9, "白露"),
    (195.0, 10, "寒露"),
    (225.0, 11, "立冬"),
    (255.0, 0, "大雪"),
    (285.0, 1, "小寒"),
)


@dataclass(frozen=True)
class Pillar:
    stem_index: int
    branch_index: int

    def __post_init__(self) -> None:
        if not 0 <= self.stem_index < 10 or not 0 <= self.branch_index < 12:
            raise ValueError("pillar indexes are outside the stem or branch cycle")
        if self.stem_index % 2 != self.branch_index % 2:
            raise ValueError("stem and branch polarities cannot form a sexagenary pillar")

    @classmethod
    def from_cycle(cls, index: int) -> Pillar:
        return cls(index % 10, index % 12)

    @classmethod
    def from_text(cls, text: str) -> Pillar:
        if len(text) != 2 or text[0] not in STEMS or text[1] not in BRANCHES:
            raise ValueError(f"invalid pillar {text!r}")
        return cls(STEMS.index(text[0]), BRANCHES.index(text[1]))

    @property
    def stem(self) -> str:
        return STEMS[self.stem_index]

    @property
    def branch(self) -> str:
        return BRANCHES[self.branch_index]

    @property
    def text(self) -> str:
        return self.stem + self.branch

    @property
    def cycle_index(self) -> int:
        return next(
            index for index in range(60) if index % 10 == self.stem_index and index % 12 == self.branch_index
        )


@dataclass(frozen=True)
class FourPillars:
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar
    year_boundary_utc: datetime | None
    month_boundary_name: str
    month_boundary_utc: datetime | None
    day_boundary: str


def calculate_pillars(birth: BirthInput, moment: NormalizedMoment, ephemeris: Ephemeris) -> FourPillars:
    """Calculate the primary chart using the configured 23:00 day boundary."""

    return _calculate(birth, moment, ephemeris, day_boundary="23:00")


def alternate_midnight_pillars(
    birth: BirthInput, moment: NormalizedMoment, ephemeris: Ephemeris
) -> FourPillars | None:
    """Return the conventional midnight-boundary alternate during 23:00-23:59."""

    if moment.true_solar.hour != 23:
        return None
    return _calculate(birth, moment, ephemeris, day_boundary="00:00")


def _calculate(
    birth: BirthInput,
    moment: NormalizedMoment,
    ephemeris: Ephemeris,
    *,
    day_boundary: str,
) -> FourPillars:
    _ = birth
    utc = moment.utc.astimezone(UTC)
    li_chun = solar_term_instant(utc.year, 315.0, ephemeris)
    solar_year = utc.year if utc >= li_chun else utc.year - 1
    if solar_year != utc.year:
        li_chun = solar_term_instant(solar_year, 315.0, ephemeris)
    year_cycle = (solar_year - 4) % 60
    year_pillar = Pillar.from_cycle(year_cycle)

    boundaries = []
    for boundary_year in (utc.year - 1, utc.year, utc.year + 1):
        for longitude, branch_index, name in JIE:
            instant = solar_term_instant(boundary_year, longitude, ephemeris)
            if instant <= utc:
                boundaries.append((instant, branch_index, name))
    month_boundary, month_branch, month_name = max(boundaries, key=lambda item: item[0])
    month_stem = (year_pillar.stem_index * 2 + month_branch) % 10
    month_pillar = Pillar(month_stem, month_branch)

    pillar_date = moment.true_solar.date()
    if day_boundary == "23:00" and moment.true_solar.hour >= 23:
        pillar_date += timedelta(days=1)
    day_pillar = Pillar.from_cycle((pillar_date - DAY_ANCHOR).days)

    hour_branch = ((moment.true_solar.hour + 1) // 2) % 12
    hour_stem = (day_pillar.stem_index * 2 + hour_branch) % 10
    hour_pillar = Pillar(hour_stem, hour_branch)
    return FourPillars(
        year=year_pillar,
        month=month_pillar,
        day=day_pillar,
        hour=hour_pillar,
        year_boundary_utc=li_chun,
        month_boundary_name=month_name,
        month_boundary_utc=month_boundary,
        day_boundary=day_boundary,
    )
