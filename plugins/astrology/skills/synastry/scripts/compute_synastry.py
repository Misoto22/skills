#!/usr/bin/env python3
"""Compute a synastry data file for two people from their birth data.

  python3 scripts/compute_synastry.py --request request.json --out .

Neither person is privileged: both charts come from the request, and no birth
data is stored in this skill. The Swiss Ephemeris is imported inside the backend,
so request parsing and report rendering stay importable — and testable — on a
machine with no ephemeris installed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report import render

DATE = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")
# Minute precision is the whole precondition. The Ascendant moves a degree every
# four minutes, so a chart built from an hour-only birth time carries the wrong
# Ascendant, the wrong houses, and therefore half the wrong synastry.
TIME = re.compile(r"\A(\d{2}):(\d{2})\Z")
UNSAFE_IN_FILENAME = re.compile(r"[^\w-]+", re.UNICODE)

# Swiss Ephemeris house-system letters. Placidus is the default because it is
# what most published charts use, not because it is the best of them.
HOUSE_SYSTEMS: Mapping[str, str] = {
    "placidus": "P",
    "koch": "K",
    "campanus": "C",
    "regiomontanus": "R",
    "equal": "E",
    "whole-sign": "W",
}

REQUIRED_FIELDS = ("name", "date", "time", "timezone", "latitude", "longitude")

# Chiron and the four asteroids are read from a separate Swiss Ephemeris file
# that a plain `pip install pyswisseph` does not carry. A chart without them is
# still a chart, so a missing file drops those bodies and says so; a chart
# without the Sun is not, so anything outside this set still raises.
OPTIONAL_BODIES = frozenset({"Chiron", "Ceres", "Pallas", "Juno", "Vesta"})


class RequestError(Exception):
    """Everything wrong with a request, reported together rather than one at a time."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Person:
    name: str
    date: str
    time: str
    timezone: str
    latitude: float
    longitude: float
    birth_place: str
    residence: str
    utc_offset_hours: float | None


def parse_request(payload: Any) -> tuple[Person, Person]:
    """Validate a request and return exactly two people, reporting every fault at once."""

    people = payload.get("people") if isinstance(payload, Mapping) else payload
    if not isinstance(people, list) or len(people) != 2:
        raise RequestError(
            ["a synastry request carries exactly two people, under a 'people' key or as a bare list"]
        )

    problems: list[str] = []
    parsed: list[Person] = []
    for index, entry in enumerate(people):
        where = f"people[{index}]"
        if not isinstance(entry, Mapping):
            problems.append(f"{where}: must be an object")
            continue
        for field in REQUIRED_FIELDS:
            if entry.get(field) in (None, ""):
                problems.append(f"{where}.{field}: required")
        problems.extend(_field_problems(where, entry))
        parsed.append(
            Person(
                name=str(entry.get("name", "")),
                date=str(entry.get("date", "")),
                time=str(entry.get("time", "")),
                timezone=str(entry.get("timezone", "")),
                latitude=_as_float(entry.get("latitude")),
                longitude=_as_float(entry.get("longitude")),
                birth_place=str(entry.get("birth_place") or entry.get("timezone") or "-"),
                residence=str(entry.get("residence") or "-"),
                utc_offset_hours=(
                    None if entry.get("utc_offset_hours") is None else _as_float(entry["utc_offset_hours"])
                ),
            )
        )

    if problems:
        raise RequestError(problems)
    return parsed[0], parsed[1]


def _field_problems(where: str, entry: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    date = str(entry.get("date", ""))
    if date and not DATE.match(date):
        problems.append(f"{where}.date: expected YYYY-MM-DD, got {date!r}")
    moment = str(entry.get("time", ""))
    if moment and not TIME.match(moment):
        problems.append(
            f"{where}.time: expected HH:MM in 24-hour form, got {moment!r}."
            " A birth time without minutes cannot fix the Ascendant, so this skill will not"
            " substitute noon or compute an early and a late variant. Ask for the minute."
        )
    for field, limit in (("latitude", 90.0), ("longitude", 180.0)):
        value = entry.get(field)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            problems.append(f"{where}.{field}: expected a decimal degree, got {value!r}")
            continue
        if abs(number) > limit:
            problems.append(f"{where}.{field}: {number} is outside ±{limit:g}")
    return problems


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def resolve_moment(person: Person) -> tuple[datetime, float]:
    """Return the birth instant in UTC and the offset that produced it.

    A named zone is resolved against the birth date, so a summer-time birth gets
    the offset in force that day rather than the zone's winter constant. An
    explicit `utc_offset_hours` overrides that, for a historical zone the
    database disagrees about.
    """

    year, month, day = (int(part) for part in DATE.match(person.date).groups())
    hour, minute = (int(part) for part in TIME.match(person.time).groups())
    if person.utc_offset_hours is not None:
        zone: Any = timezone(timedelta(hours=person.utc_offset_hours))
    else:
        try:
            zone = ZoneInfo(person.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise RequestError(
                [
                    f"timezone {person.timezone!r} is not in the zone database ({error})."
                    " Pass 'utc_offset_hours' to state the offset directly."
                ]
            ) from error
    local = datetime(year, month, day, hour, minute, tzinfo=zone)
    offset = local.utcoffset()
    if offset is None:  # pragma: no cover - a tz-aware datetime always resolves one
        raise RequestError([f"timezone {person.timezone!r} resolved no offset for {person.date}"])
    return local.astimezone(UTC), offset.total_seconds() / 3600.0


def swiss_ephemeris(person: Person, house_system: str, ephemeris_path: str | None) -> dict[str, Any]:
    """Resolve one chart with pyswisseph — the only part of this skill with a dependency."""

    try:
        import swisseph as swe
    except ImportError as error:  # pragma: no cover - exercised only without the dependency
        raise SystemExit(
            "pyswisseph is not installed. Install it with `pip install pyswisseph`, or run this"
            " script under an environment that has it."
        ) from error

    if ephemeris_path:
        swe.set_ephe_path(ephemeris_path)
    moment, _ = resolve_moment(person)
    julian_day = swe.julday(
        moment.year,
        moment.month,
        moment.day,
        moment.hour + moment.minute / 60.0 + moment.second / 3600.0,
    )
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    bodies = {
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
        # Mean rather than true node. The true node stations and retrogrades, so
        # charts drawn days apart disagree about a body neither person moved.
        "North_Node": swe.MEAN_NODE,
    }
    longitudes: dict[str, float] = {}
    retrograde: list[str] = []
    unavailable: list[str] = []
    for name, code in bodies.items():
        try:
            position, _ = swe.calc_ut(julian_day, code, flags)
        except swe.Error:
            if name not in OPTIONAL_BODIES:
                raise
            unavailable.append(name)
            continue
        longitudes[name] = position[0]
        if position[3] < 0:
            retrograde.append(name)
    longitudes["South_Node"] = (longitudes["North_Node"] + 180.0) % 360.0

    cusps, ascmc = swe.houses(julian_day, person.latitude, person.longitude, house_system.encode("ascii"))
    longitudes["Ascendant"] = ascmc[0]
    longitudes["Medium_Coeli"] = ascmc[1]
    longitudes["Descendant"] = (ascmc[0] + 180.0) % 360.0
    longitudes["Imum_Coeli"] = (ascmc[1] + 180.0) % 360.0
    longitudes["Vertex"] = ascmc[3]
    longitudes["East_Point"] = ascmc[4]
    return {
        "longitudes": longitudes,
        "retrograde": retrograde,
        "unavailable": unavailable,
        "cusps": list(cusps[:12]),
    }


def build_chart(person: Person, positions: Mapping[str, Any], house_system: str) -> dict[str, Any]:
    """Join one person's stated birth data to the positions a backend resolved."""

    _, offset = resolve_moment(person)
    return {
        "name": person.name,
        "birth_local": f"{person.date} {person.time}",
        "birth_place": person.birth_place,
        "residence": person.residence,
        "timezone": person.timezone,
        "utc_offset_hours": offset,
        "latitude": person.latitude,
        "longitude": person.longitude,
        "house_system": house_system,
        "longitudes": positions["longitudes"],
        "retrograde": positions.get("retrograde", ()),
        "unavailable": positions.get("unavailable", ()),
        "cusps": positions["cusps"],
    }


def output_name(left: Person, right: Person) -> str:
    return f"synastry_{_slug(left.name)}_{_slug(right.name)}.txt"


def _slug(name: str) -> str:
    """Keep the name readable in a filename without letting it steer the path."""

    return UNSAFE_IN_FILENAME.sub("-", name).strip("-") or "unnamed"


def main(argv: list[str] | None = None, backend: Callable[[Person], dict[str, Any]] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute a synastry data file for two people.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", help="path to a JSON request; '-' reads standard input")
    source.add_argument("--json", help="the JSON request inline")
    parser.add_argument("--out", default=".", help="directory to write the report into")
    parser.add_argument("--language", default="en", choices=["en", "zh"], help="report language")
    parser.add_argument("--major-orb", type=float, default=8.0, help="orb for the Ptolemaic aspects")
    parser.add_argument("--minor-orb", type=float, default=3.0, help="orb for the minor aspects")
    parser.add_argument(
        "--house-system",
        default="placidus",
        choices=sorted(HOUSE_SYSTEMS),
        help="house division to use for both charts",
    )
    parser.add_argument(
        "--ephemeris-path",
        help="directory holding the Swiss Ephemeris data files, when they are not on the default path",
    )
    arguments = parser.parse_args(argv)

    letter = HOUSE_SYSTEMS[arguments.house_system]
    resolve = backend or (lambda person: swiss_ephemeris(person, letter, arguments.ephemeris_path))
    try:
        left, right = parse_request(_load_payload(arguments))
        charts = [build_chart(person, resolve(person), arguments.house_system) for person in (left, right)]
    except RequestError as error:
        for problem in error.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"error: cannot read the request: {error}", file=sys.stderr)
        return 2

    document = render(
        charts[0],
        charts[1],
        language=arguments.language,
        major_orb=arguments.major_orb,
        minor_orb=arguments.minor_orb,
    )
    destination = Path(arguments.out).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    written = destination / output_name(left, right)
    written.write_text(document, encoding="utf-8")
    print(f"wrote {written}")
    return 0


def _load_payload(arguments: argparse.Namespace) -> Any:
    if arguments.json is not None:
        return json.loads(arguments.json)
    if arguments.request == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(arguments.request).expanduser().read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
