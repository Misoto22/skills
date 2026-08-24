"""Compose validated inputs, astronomy, pillars, facts, and scores."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .artifacts import add_checksum
from .calendar import lunar_to_gregorian
from .ephemeris import Ephemeris
from .models import BirthInput
from .pillars import FourPillars, Pillar, alternate_midnight_pillars, calculate_pillars
from .relations import derive_chart_facts
from .scoring import score_chart
from .timekeeping import apply_true_solar_time, resolve_civil_time

SHARED_ROOT = Path(__file__).resolve().parents[1]


def build_chart(payload: dict[str, Any], ephemeris: Ephemeris) -> dict[str, Any]:
    """Build one canonical chart envelope without writing or interpreting it."""

    original = BirthInput.from_mapping(payload)
    resolved = _resolve_calendar(original, ephemeris)
    civil = resolve_civil_time(resolved)
    jd = ephemeris.julian_day(civil.utc)
    normalized = apply_true_solar_time(resolved, civil, ephemeris.equation_of_time(jd))
    primary = calculate_pillars(resolved, normalized, ephemeris)
    alternate = alternate_midnight_pillars(resolved, normalized, ephemeris)
    chart_rules = _load_rules("chart-v1.json")
    scoring_rules = _load_rules("scoring-v1.json")
    primary_facts = derive_chart_facts(primary, chart_rules)
    primary_scores = score_chart(primary, primary_facts, scoring_rules)
    alternate_facts = derive_chart_facts(alternate, chart_rules) if alternate else None
    alternate_scores = (
        score_chart(alternate, alternate_facts, scoring_rules)
        if alternate is not None and alternate_facts is not None
        else None
    )

    envelope = {
        "schema": "chinese-metaphysics.bazi-chart",
        "schema_version": 1,
        "input": original.to_mapping(),
        "calendar": {
            "input_calendar": original.calendar,
            "input_date": original.birth_date,
            "input_leap_month": original.leap_month,
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
        "pillars": {
            "primary": _serialize_pillars(primary),
            "alternate": _serialize_pillars(alternate) if alternate else None,
        },
        "facts": {"primary": primary_facts, "alternate": alternate_facts},
        "scores": {"primary": primary_scores, "alternate": alternate_scores},
        "sensitivity": {
            "alternate_day_boundary": alternate is not None,
            "primary_day_boundary": "23:00",
            "alternate_day_boundary_rule": "00:00" if alternate else None,
        },
        "methodology": {
            # Read from the rules files this chart was built with, never written
            # twice. A literal here would keep reporting v1 after the rules moved
            # to v2, and the artifact would name two different models for itself.
            "calendar_model": chart_rules["model_id"],
            "scoring_model": scoring_rules["model_id"],
            "ephemeris": type(ephemeris).__name__,
            "score_semantics": "versioned heuristics, not probabilities",
            "limits": ["static natal chart", "no Da Yun", "no annual forecast", "no event timing"],
        },
    }
    return add_checksum(envelope)


def _resolve_calendar(birth: BirthInput, ephemeris: Ephemeris) -> BirthInput:
    if birth.calendar == "gregorian":
        return birth
    gregorian = lunar_to_gregorian(
        birth.year,
        birth.month,
        birth.day,
        bool(birth.leap_month),
        ephemeris,
    )
    mapping = birth.to_mapping()
    mapping["birth_date"] = gregorian.isoformat()
    mapping["calendar"] = "gregorian"
    mapping.pop("leap_month", None)
    return BirthInput.from_mapping(mapping)


def _serialize_pillars(pillars: FourPillars) -> dict[str, Any]:
    return {
        position: _serialize_pillar(getattr(pillars, position))
        for position in ("year", "month", "day", "hour")
    } | {
        "boundaries": {
            "year_boundary_utc": (
                pillars.year_boundary_utc.isoformat() if pillars.year_boundary_utc else None
            ),
            "month_boundary_name": pillars.month_boundary_name,
            "month_boundary_utc": (
                pillars.month_boundary_utc.isoformat() if pillars.month_boundary_utc else None
            ),
            "day_boundary": pillars.day_boundary,
        }
    }


def _serialize_pillar(pillar: Pillar) -> dict[str, Any]:
    return {
        "stem": pillar.stem,
        "branch": pillar.branch,
        "text": pillar.text,
        "stem_index": pillar.stem_index,
        "branch_index": pillar.branch_index,
        "cycle_index": pillar.cycle_index,
    }


@lru_cache(maxsize=4)
def _load_rules(filename: str) -> dict[str, Any]:
    return json.loads((SHARED_ROOT / "rules" / filename).read_text(encoding="utf-8"))
