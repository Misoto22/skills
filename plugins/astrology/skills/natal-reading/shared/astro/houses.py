"""The house systems a chart may be cast in, each with its Swiss Ephemeris code.

One table, so a request cannot accept a system the ephemeris does not know how
to cast, and the artifact schema accepts exactly the names a request may name.
"""

from __future__ import annotations

from collections.abc import Mapping

HOUSE_SYSTEMS: Mapping[str, bytes] = {
    "placidus": b"P",
    "koch": b"K",
    "campanus": b"C",
    "regiomontanus": b"R",
    "equal": b"E",
    "whole-sign": b"W",
}
HOUSE_SYSTEM_NAMES = frozenset(HOUSE_SYSTEMS)
