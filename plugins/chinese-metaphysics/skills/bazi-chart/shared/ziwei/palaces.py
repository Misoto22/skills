"""Locate the twelve palaces, the bureau, and the stem each palace carries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")
STEMS = tuple("甲乙丙丁戊己庚辛壬癸")
YIN_BRANCH = 2
ELEMENTS = tuple("金木水火土")


class ZiweiError(ValueError):
    """A Zi Wei chart cannot be placed from the supplied lunar record."""


@dataclass(frozen=True)
class Bureau:
    """The 五行局 that sets where 紫微 sits and when each decade opens."""

    element: str
    name: str
    value: int


@dataclass(frozen=True)
class Palace:
    """One of the twelve palaces, named from the life palace and running backward."""

    index: int
    branch: str
    stem: str
    name: str
    is_life: bool
    is_body: bool


def life_palace_index(lunar_month: int, hour_branch: int) -> int:
    """Count months forward from 寅, then hours backward, the standard placement."""

    _check(lunar_month, hour_branch)
    return (YIN_BRANCH + lunar_month - 1 - hour_branch) % 12


def body_palace_index(lunar_month: int, hour_branch: int) -> int:
    """Count months forward from 寅, then hours forward — the body palace."""

    _check(lunar_month, hour_branch)
    return (YIN_BRANCH + lunar_month - 1 + hour_branch) % 12


def palace_stem(palace_index: int, year_stem_index: int) -> str:
    """Return the stem a palace carries under the 五虎遁 month-stem rule."""

    yin_stem = (year_stem_index % 5) * 2 + 2
    return STEMS[(yin_stem + palace_index - YIN_BRANCH) % 10]


def bureau_for(life_index: int, year_stem_index: int, rules: Mapping[str, Any]) -> Bureau:
    """Derive the bureau from the sexagenary sound of the life palace."""

    pillar = palace_stem(life_index, year_stem_index) + BRANCHES[life_index]
    sound = rules["nayin"].get(pillar)
    if not sound:
        raise ZiweiError(f"no 纳音 recorded for life palace {pillar}")
    element = sound[-1]
    bureau = rules["bureaus"].get(element)
    if not bureau:
        raise ZiweiError(f"纳音 {sound!r} does not resolve to a bureau element")
    return Bureau(element=element, name=bureau["name"], value=int(bureau["value"]))


def build_palaces(
    life_index: int,
    body_index: int,
    year_stem_index: int,
    rules: Mapping[str, Any],
) -> tuple[Palace, ...]:
    """Return all twelve palaces in branch order, named backward from the life palace."""

    names: list[str] = [""] * 12
    for step, name in enumerate(rules["palace_names"]):
        names[(life_index - step) % 12] = name

    return tuple(
        Palace(
            index=index,
            branch=BRANCHES[index],
            stem=palace_stem(index, year_stem_index),
            name=names[index],
            is_life=index == life_index,
            is_body=index == body_index,
        )
        for index in range(12)
    )


def decade_cycles(
    life_index: int,
    bureau: Bureau,
    year_stem_index: int,
    gender: str,
    palaces: tuple[Palace, ...],
) -> tuple[dict[str, Any], ...]:
    """Return the twelve decade ranges, running forward or backward by polarity.

    A yang-stem year with a male subject, or a yin-stem year with a female one,
    runs forward; the other two combinations run backward. Gender is required
    here and is never inferred elsewhere.
    """

    if gender not in ("male", "female"):
        raise ZiweiError("decade cycles require an explicitly supplied gender")
    yang_year = year_stem_index % 2 == 0
    forward = yang_year == (gender == "male")
    step = 1 if forward else -1

    return tuple(
        {
            "order": order + 1,
            "palace_index": (index := (life_index + step * order) % 12),
            "palace_branch": BRANCHES[index],
            "palace_name": palaces[index].name,
            "start_age": bureau.value + order * 10,
            "end_age": bureau.value + order * 10 + 9,
        }
        for order in range(12)
    )


def _check(lunar_month: int, hour_branch: int) -> None:
    if not 1 <= lunar_month <= 12:
        raise ZiweiError(f"lunar month must be 1 through 12, got {lunar_month}")
    if not 0 <= hour_branch <= 11:
        raise ZiweiError(f"hour branch index must be 0 through 11, got {hour_branch}")
