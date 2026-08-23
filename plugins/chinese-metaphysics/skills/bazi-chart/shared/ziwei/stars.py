"""Place the fourteen main stars, the support stars, and the year transformations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .palaces import YIN_BRANCH, Bureau, ZiweiError

TIANFU_AXIS = 4


@dataclass(frozen=True)
class Star:
    """One placed star, with the transformation it carries in this chart."""

    name: str
    palace_index: int
    category: str
    brightness: str | None
    transformation: str | None


def ziwei_palace_index(bureau: Bureau, lunar_day: int) -> int:
    """Return where 紫微 sits for this bureau and lunar day.

    Step up in bureau-sized strides until the day is covered, then move the
    remainder forward from 寅 when it is even and backward when it is odd.
    """

    if not 1 <= lunar_day <= 30:
        raise ZiweiError(f"lunar day must be 1 through 30, got {lunar_day}")
    strides = -(-lunar_day // bureau.value)
    remainder = strides * bureau.value - lunar_day
    offset = (strides - 1) + remainder if remainder % 2 == 0 else (strides - 1) - remainder
    return (YIN_BRANCH + offset) % 12


def tianfu_palace_index(ziwei_index: int) -> int:
    """Return where 天府 sits — mirrored with 紫微 across the 寅-申 axis."""

    return (TIANFU_AXIS - ziwei_index) % 12


def place_stars(
    *,
    bureau: Bureau,
    lunar_month: int,
    lunar_day: int,
    hour_branch: int,
    year_stem: str,
    rules: Mapping[str, Any],
) -> tuple[Star, ...]:
    """Return every star this release places, in a stable reporting order."""

    transformations = rules["four_transformations"].get(year_stem)
    if not transformations:
        raise ZiweiError(f"no 四化 recorded for year stem {year_stem!r}")
    carried = {star: label for label, star in transformations.items()}

    positions: dict[str, tuple[int, str]] = {}
    ziwei_index = ziwei_palace_index(bureau, lunar_day)
    for star, offset in rules["north_dipper"]["offsets"].items():
        positions[star] = ((ziwei_index + offset) % 12, "主星")

    tianfu_index = tianfu_palace_index(ziwei_index)
    for star, offset in rules["south_dipper"]["offsets"].items():
        positions[star] = ((tianfu_index + offset) % 12, "主星")

    counters = {"month": lunar_month - 1, "hour": hour_branch}
    for star, rule in rules["support_stars"].items():
        steps = counters[rule["from"]]
        positions[star] = ((rule["start"] + rule["direction"] * steps) % 12, "辅星")

    for star, table in rules["year_stem_stars"].items():
        if year_stem not in table:
            raise ZiweiError(f"{star} has no placement for year stem {year_stem!r}")
        positions[star] = (int(table[year_stem]) % 12, "辅星")

    for star, rule in rules["derived_stars"].items():
        anchor = positions.get(rule["from"])
        if anchor is None:
            raise ZiweiError(f"{star} depends on {rule['from']!r}, which was not placed")
        positions[star] = ((anchor[0] + int(rule["offset"])) % 12, "煞星")

    order = [
        *rules["star_classes"]["主星"],
        *rules["star_classes"]["辅星"],
        *rules["star_classes"]["煞星"],
    ]
    brightness = rules["brightness"]
    return tuple(
        Star(
            name=star,
            palace_index=positions[star][0],
            category=positions[star][1],
            brightness=(brightness[star][positions[star][0]] if star in brightness else None),
            transformation=carried.get(star),
        )
        for star in order
        if star in positions
    )


def stars_by_palace(stars: tuple[Star, ...]) -> dict[int, list[Star]]:
    """Group placed stars by palace, preserving the reporting order."""

    grouped: dict[int, list[Star]] = {index: [] for index in range(12)}
    for star in stars:
        grouped[star.palace_index].append(star)
    return grouped


def unplaced_transformations(stars: tuple[Star, ...], rules: Mapping[str, Any], year_stem: str) -> list[str]:
    """Return transformations whose target star this release does not place.

    Recording the gap keeps a reading honest instead of letting a missing
    transformation read as an absent one.
    """

    placed = {star.name for star in stars}
    table = rules["four_transformations"].get(year_stem, {})
    return [f"{star}化{label}" for label, star in table.items() if star not in placed]
