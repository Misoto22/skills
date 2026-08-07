#!/usr/bin/env python3
"""Positional astrology arithmetic: signs, houses, dignities, lots, and aspects.

Nothing here reads an ephemeris. It takes ecliptic longitudes a caller already
resolved and derives everything the report states from them, so the derivation
stays testable on a machine with no Swiss Ephemeris installed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NamedTuple

SIGNS = (
    "Ari",
    "Tau",
    "Gem",
    "Can",
    "Leo",
    "Vir",
    "Lib",
    "Sco",
    "Sag",
    "Cap",
    "Aqu",
    "Pis",
)

# Classical rulerships only. The modern assignments (Uranus to Aquarius, and so
# on) are a live disagreement between traditions, and a report stating one as
# fact asserts a school rather than a position.
DIGNITIES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "Sun": {"domicile": ("Leo",), "exaltation": ("Ari",), "detriment": ("Aqu",), "fall": ("Lib",)},
    "Moon": {"domicile": ("Can",), "exaltation": ("Tau",), "detriment": ("Cap",), "fall": ("Sco",)},
    "Mercury": {
        "domicile": ("Gem", "Vir"),
        "exaltation": ("Vir",),
        "detriment": ("Sag", "Pis"),
        "fall": ("Pis",),
    },
    "Venus": {
        "domicile": ("Tau", "Lib"),
        "exaltation": ("Pis",),
        "detriment": ("Sco", "Ari"),
        "fall": ("Vir",),
    },
    "Mars": {
        "domicile": ("Ari", "Sco"),
        "exaltation": ("Cap",),
        "detriment": ("Lib", "Tau"),
        "fall": ("Can",),
    },
    "Jupiter": {
        "domicile": ("Sag", "Pis"),
        "exaltation": ("Can",),
        "detriment": ("Gem", "Vir"),
        "fall": ("Cap",),
    },
    "Saturn": {
        "domicile": ("Cap", "Aqu"),
        "exaltation": ("Lib",),
        "detriment": ("Can", "Leo"),
        "fall": ("Ari",),
    },
}

DIGNITY_ORDER = ("domicile", "exaltation", "detriment", "fall")


class AspectKind(NamedTuple):
    name: str
    angle: float
    major: bool


# Ptolemaic aspects first, then the minor family. `major` decides which orb a
# hit is measured against: one orb for both lets the minor aspects outnumber the
# Ptolemaic ones and buries the pattern worth reading.
ASPECT_KINDS = (
    AspectKind("conjunction", 0.0, True),
    AspectKind("opposition", 180.0, True),
    AspectKind("trine", 120.0, True),
    AspectKind("square", 90.0, True),
    AspectKind("sextile", 60.0, True),
    AspectKind("semi-sextile", 30.0, False),
    AspectKind("semi-square", 45.0, False),
    AspectKind("quintile", 72.0, False),
    AspectKind("sesquiquadrate", 135.0, False),
    AspectKind("biquintile", 144.0, False),
    AspectKind("quincunx", 150.0, False),
)


class Aspect(NamedTuple):
    left: str
    right: str
    kind: str
    orb: float


def normalize(longitude: float) -> float:
    """Fold an ecliptic longitude into [0, 360)."""

    return longitude % 360.0


def sign_index(longitude: float) -> int:
    return int(normalize(longitude) // 30)


def sign_of(longitude: float) -> str:
    return SIGNS[sign_index(longitude)]


def degrees_in_sign(longitude: float) -> float:
    return normalize(longitude) - sign_index(longitude) * 30.0


def format_degrees(value: float) -> str:
    """Render degrees within a sign as `d<degree>mm'`, carrying a rounded 60 upward."""

    degrees = int(value)
    minutes = round((value - degrees) * 60)
    if minutes == 60:
        degrees, minutes = degrees + 1, 0
    return f"{degrees}°{minutes:02d}'"


def house_of(longitude: float, cusps: Sequence[float]) -> int:
    """Return the 1-based house holding `longitude`, given twelve cusp longitudes."""

    if len(cusps) != 12:
        raise ValueError(f"a chart has twelve house cusps; got {len(cusps)}")
    position = normalize(longitude)
    for index in range(12):
        start = normalize(cusps[index])
        end = normalize(cusps[(index + 1) % 12])
        if start <= end:
            if start <= position < end:
                return index + 1
        elif position >= start or position < end:
            return index + 1
    # Twelve distinct cusps tile the circle, so this is reachable only from
    # duplicated cusps — a backend defect worth surfacing rather than rounding away.
    raise ValueError("house cusps do not cover the ecliptic")


def separation(left: float, right: float) -> float:
    """Angular separation in [0, 180]."""

    difference = abs(normalize(left) - normalize(right)) % 360.0
    return 360.0 - difference if difference > 180.0 else difference


def dignities(body: str, sign: str) -> tuple[str, ...]:
    """Classical dignities held by `body` in `sign`, in a fixed order."""

    table = DIGNITIES.get(body)
    if table is None:
        return ()
    return tuple(state for state in DIGNITY_ORDER if sign in table[state])


def is_critical(longitude: float) -> bool:
    """The first and last degree of a sign, where a small time error changes the sign."""

    return int(degrees_in_sign(longitude)) in {0, 29}


def is_diurnal(sun_longitude: float, cusps: Sequence[float]) -> bool:
    """A chart is diurnal when the Sun is above the horizon — houses seven to twelve."""

    return house_of(sun_longitude, cusps) >= 7


def lots(
    *,
    ascendant: float,
    sun: float,
    moon: float,
    venus: float,
    jupiter: float,
    saturn: float,
    diurnal: bool,
) -> dict[str, float]:
    """The classical Lots, with the Sun and Moon swapped for a nocturnal chart."""

    if diurnal:
        fortune = ascendant + moon - sun
        spirit = ascendant + sun - moon
        marriage = ascendant + venus - sun
    else:
        fortune = ascendant + sun - moon
        spirit = ascendant + moon - sun
        marriage = ascendant + sun - venus
    return {
        "Lot_of_Spirit": normalize(spirit),
        "Lot_of_Fortune": normalize(fortune),
        "Lot_of_Marriage": normalize(marriage),
        "Lot_of_Death": normalize(ascendant + saturn - moon),
        "Lot_of_Sons": normalize(ascendant + jupiter - moon),
        "Lot_of_Daughters": normalize(ascendant + venus - moon),
    }


def find_aspects(
    left: Mapping[str, float],
    right: Mapping[str, float],
    *,
    major_orb: float = 8.0,
    minor_orb: float = 3.0,
) -> list[Aspect]:
    """Every aspect between two sets of longitudes, tightest orb first.

    Both sides are compared in full, so an asteroid-to-asteroid contact is found
    on the same pass as a Sun-to-Moon one. Ties break on the two names, so a
    rerun over the same input produces byte-identical output.
    """

    found: list[Aspect] = []
    for left_name, left_longitude in left.items():
        for right_name, right_longitude in right.items():
            arc = separation(left_longitude, right_longitude)
            for kind in ASPECT_KINDS:
                orb = abs(arc - kind.angle)
                if orb <= (major_orb if kind.major else minor_orb):
                    found.append(Aspect(left_name, right_name, kind.name, orb))
                    break
    found.sort(key=lambda aspect: (round(aspect.orb, 6), aspect.left, aspect.right))
    return found
