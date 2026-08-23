"""Compose validated inputs, the lunar calendar, palaces, and stars into one chart."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from bazi.artifacts import add_checksum
from bazi.calendar import LunarDate, gregorian_to_lunar, lunar_to_gregorian
from bazi.ephemeris import Ephemeris
from bazi.models import BirthInput
from bazi.pillars import BRANCHES as PILLAR_BRANCHES
from bazi.pillars import Pillar
from bazi.timekeeping import apply_true_solar_time, resolve_civil_time

from .palaces import (
    Palace,
    ZiweiError,
    body_palace_index,
    build_palaces,
    bureau_for,
    decade_cycles,
    life_palace_index,
)
from .stars import Star, place_stars, stars_by_palace, unplaced_transformations

SHARED_ROOT = Path(__file__).resolve().parents[1]


def build_chart(payload: dict[str, Any], ephemeris: Ephemeris) -> dict[str, Any]:
    """Build one canonical Zi Wei chart envelope without writing or interpreting it."""

    birth = BirthInput.from_mapping(payload)
    if birth.gender not in ("male", "female"):
        raise ZiweiError(
            "gender: Zi Wei decade cycles are direction-dependent, so this skill "
            "requires an explicit 'male' or 'female'; never infer it"
        )

    resolved = _resolve_calendar(birth, ephemeris)
    civil = resolve_civil_time(resolved)
    jd = ephemeris.julian_day(civil.utc)
    normalized = apply_true_solar_time(resolved, civil, ephemeris.equation_of_time(jd))
    rules = _load_rules("ziwei-v1.json") | {"nayin": _load_rules("chart-v1.json")["nayin"]}

    primary = _place(normalized.true_solar, resolved, rules, ephemeris, day_boundary="23:00")
    alternate = (
        _place(normalized.true_solar, resolved, rules, ephemeris, day_boundary="00:00")
        if normalized.true_solar.hour == 23
        else None
    )

    envelope = {
        "schema": "chinese-metaphysics.ziwei-chart",
        "schema_version": 1,
        "input": birth.to_mapping(),
        "calendar": {
            "input_calendar": birth.calendar,
            "input_date": birth.birth_date,
            "input_leap_month": birth.leap_month,
            "resolved_gregorian_date": resolved.birth_date,
            "rules": "GB/T 33661-2017",
        },
        "time": {
            "civil_local": civil.local.isoformat(),
            "utc": civil.utc.isoformat(),
            "utc_offset_minutes": civil.utc_offset_minutes,
            "offset_source": civil.source,
            "fold": civil.fold,
            "longitude_correction_minutes": normalized.longitude_correction_minutes,
            "equation_of_time_minutes": normalized.equation_of_time_minutes,
            "true_solar": normalized.true_solar.isoformat(),
        },
        "chart": {"primary": primary, "alternate": alternate},
        "sensitivity": {
            "alternate_day_boundary": alternate is not None,
            "primary_day_boundary": "23:00",
            "alternate_day_boundary_rule": "00:00" if alternate else None,
            "note": (
                "A 23:00-23:59 birth shifts the lunar day, which moves 紫微 and every "
                "star anchored to it. Read the two charts separately; never average them."
            )
            if alternate
            else None,
        },
        "methodology": {
            "placement_model": "ziwei-chart-rules-v1",
            "school": rules["school"],
            "school_notes": rules["notes"],
            "time_basis": "true solar time, matching this plugin's BaZi charts",
            "ephemeris": type(ephemeris).__name__,
            "limits": [
                "static natal chart plus decade ranges",
                "no annual or monthly transformation",
                "no event timing",
                "no self-transformation (自化)",
                "no 神煞 beyond the recorded support and malefic stars",
            ],
        },
    }
    return add_checksum(envelope)


def _place(
    true_solar: Any,
    birth: BirthInput,
    rules: dict[str, Any],
    ephemeris: Ephemeris,
    *,
    day_boundary: str,
) -> dict[str, Any]:
    """Place one complete chart under the requested day boundary."""

    hour_branch = ((true_solar.hour + 1) // 2) % 12
    placement_date = true_solar.date()
    if day_boundary == "23:00" and true_solar.hour >= 23:
        placement_date = date.fromordinal(placement_date.toordinal() + 1)
    lunar = gregorian_to_lunar(placement_date, ephemeris)

    year_pillar = _year_pillar(lunar)
    life_index = life_palace_index(lunar.month, hour_branch)
    body_index = body_palace_index(lunar.month, hour_branch)
    bureau = bureau_for(life_index, year_pillar.stem_index, rules)
    palaces = build_palaces(life_index, body_index, year_pillar.stem_index, rules)
    stars = place_stars(
        bureau=bureau,
        lunar_month=lunar.month,
        lunar_day=lunar.day,
        hour_branch=hour_branch,
        year_stem=year_pillar.stem,
        rules=rules,
    )
    grouped = stars_by_palace(stars)

    return {
        "day_boundary": day_boundary,
        "lunar": {
            "year": lunar.year,
            "month": lunar.month,
            "day": lunar.day,
            "leap_month": lunar.leap,
            "text": lunar.text,
            "hour_branch": PILLAR_BRANCHES[hour_branch],
            "hour_branch_index": hour_branch,
        },
        "year_pillar": {
            "stem": year_pillar.stem,
            "branch": year_pillar.branch,
            "text": year_pillar.text,
            "polarity": "阳" if year_pillar.stem_index % 2 == 0 else "阴",
        },
        "bureau": {"element": bureau.element, "name": bureau.name, "value": bureau.value},
        "life_palace": {"index": life_index, "branch": PILLAR_BRANCHES[life_index]},
        "body_palace": {
            "index": body_index,
            "branch": PILLAR_BRANCHES[body_index],
            "palace_name": palaces[body_index].name,
        },
        "palaces": [_serialize_palace(palace, grouped[palace.index]) for palace in palaces],
        "transformations": {
            "year_stem": year_pillar.stem,
            "placed": [
                {
                    "star": star.name,
                    "label": star.transformation,
                    "palace": PILLAR_BRANCHES[star.palace_index],
                }
                for star in stars
                if star.transformation
            ],
            "unplaced": unplaced_transformations(stars, rules, year_pillar.stem),
        },
        "decades": list(
            decade_cycles(life_index, bureau, year_pillar.stem_index, str(birth.gender), palaces)
        ),
    }


def _serialize_palace(palace: Palace, stars: list[Star]) -> dict[str, Any]:
    return {
        "index": palace.index,
        "branch": palace.branch,
        "stem": palace.stem,
        "name": palace.name,
        "is_life_palace": palace.is_life,
        "is_body_palace": palace.is_body,
        "stars": [
            {
                "name": star.name,
                "category": star.category,
                "brightness": star.brightness,
                "transformation": star.transformation,
            }
            for star in stars
        ],
        "empty": not stars,
    }


def _year_pillar(lunar: LunarDate) -> Pillar:
    """Return the year pillar Zi Wei uses — the lunar year, not the Li Chun year.

    BaZi changes the year at Li Chun; Zi Wei changes it at lunar new year. A
    January or early-February birth therefore carries a different year stem in
    the two systems, and a cross-reading must not silently reconcile them.
    """

    return Pillar.from_cycle((lunar.year - 4) % 60)


def _resolve_calendar(birth: BirthInput, ephemeris: Ephemeris) -> BirthInput:
    if birth.calendar == "gregorian":
        return birth
    gregorian = lunar_to_gregorian(birth.year, birth.month, birth.day, bool(birth.leap_month), ephemeris)
    mapping = birth.to_mapping()
    mapping["birth_date"] = gregorian.isoformat()
    mapping["calendar"] = "gregorian"
    mapping.pop("leap_month", None)
    return BirthInput.from_mapping(mapping)


@lru_cache(maxsize=4)
def _load_rules(filename: str) -> dict[str, Any]:
    return json.loads((SHARED_ROOT / "rules" / filename).read_text(encoding="utf-8"))
