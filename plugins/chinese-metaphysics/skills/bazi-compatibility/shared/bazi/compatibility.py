"""Symmetric, ledger-backed comparison of two canonical BaZi charts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .artifacts import CHART_SCHEMA, COMPATIBILITY_SCHEMA, SCHEMAS, add_checksum, validate_envelope

SHARED_ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ("year", "month", "day", "hour")


class CompatibilityError(ValueError):
    """Two source charts cannot be compared under the declared contract."""


def compare_charts(
    left: dict[str, Any],
    right: dict[str, Any],
    relationship_type: str | None,
) -> dict[str, Any]:
    """Compare two verified chart envelopes and preserve directional evidence."""

    try:
        left_chart = validate_envelope(left)
        right_chart = validate_envelope(right)
    except ValueError as error:
        raise CompatibilityError(str(error)) from error
    for chart in (left_chart, right_chart):
        if chart["schema"] != CHART_SCHEMA:
            raise CompatibilityError("compatibility requires two BaZi chart artifacts")
        _validate_chart_shape(chart)

    rules = _rules()
    profiles = rules["relationship_profiles"]
    if relationship_type is not None and relationship_type not in profiles:
        choices = ", ".join(profiles)
        raise CompatibilityError(f"relationship_type must be one of {choices}, or omitted")

    dimensions = _dimensions(left_chart, right_chart, False, False, rules)
    general = _weighted_score(dimensions, rules["general_weights"], rules["rounding_digits"])
    contextual = (
        _weighted_score(dimensions, profiles[relationship_type], rules["rounding_digits"])
        if relationship_type
        else None
    )
    variants = []
    for left_alternate in _alternate_options(left_chart):
        for right_alternate in _alternate_options(right_chart):
            variant_dimensions = _dimensions(left_chart, right_chart, left_alternate, right_alternate, rules)
            variants.append(
                {
                    "left": "alternate" if left_alternate else "primary",
                    "right": "alternate" if right_alternate else "primary",
                    "general": _weighted_score(
                        variant_dimensions,
                        rules["general_weights"],
                        rules["rounding_digits"],
                    ),
                }
            )
    variant_scores = [item["general"] for item in variants]
    spread = max(variant_scores) - min(variant_scores)
    confidence = _confidence(left_chart, right_chart, spread)
    result = {
        "schema": COMPATIBILITY_SCHEMA,
        "schema_version": SCHEMAS[COMPATIBILITY_SCHEMA],
        "model_version": rules["model_id"],
        "score_semantics": "versioned heuristic scores; not probabilities or relationship outcomes",
        "relationship_type": relationship_type,
        "people": {
            "left": {"name": left_chart["input"]["name"], "chart_checksum": left_chart["checksum"]},
            "right": {"name": right_chart["input"]["name"], "chart_checksum": right_chart["checksum"]},
        },
        "dimensions": dimensions,
        "scores": {
            "general": general,
            "contextual": contextual,
            "contextual_profile": profiles.get(relationship_type),
        },
        "sensitivity": {
            "minimum": min(variant_scores),
            "maximum": max(variant_scores),
            "spread": round(spread, rules["rounding_digits"]),
            "variants": variants,
        },
        "confidence": confidence,
        "methodology": {
            "general_weights": rules["general_weights"],
            "secondary_evidence_excluded": ["shen_sha"],
        },
    }
    return add_checksum(result)


def _dimensions(
    left: dict[str, Any],
    right: dict[str, Any],
    left_alternate: bool,
    right_alternate: bool,
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    left_view = _view(left, left_alternate, "left")
    right_view = _view(right, right_alternate, "right")
    weights = rules["general_weights"]
    calculators = (
        ("element_complementarity", _element_complementarity),
        ("directional_day_master_support", _directional_support),
        ("stem_branch_interactions", _cross_interactions),
        ("day_pillar_core", _day_core),
        ("structural_stability", _structural_stability),
    )
    result = []
    for identifier, calculator in calculators:
        score, ledger = calculator(left_view, right_view, rules)
        result.append(
            {
                "id": identifier,
                "name": identifier.replace("_", " "),
                "weight": weights[identifier],
                "score": round(score, rules["rounding_digits"]),
                "ledger": ledger,
            }
        )
    return result


def _element_complementarity(left: dict[str, Any], right: dict[str, Any], rules: dict[str, Any]):
    combined = {
        element: (left["distribution"][element] + right["distribution"][element]) / 2.0
        for element in rules["elements"]
    }
    deviation = sum(abs(value - 20.0) for value in combined.values())
    score = _clamp(100.0 - deviation * 0.625)
    ledger = [
        {
            "id": f"combined.{element}",
            "element": element,
            "combined_percent": value,
            "target_percent": 20.0,
            "deviation": abs(value - 20.0),
        }
        for element, value in combined.items()
    ]
    return score, ledger


def _directional_support(left: dict[str, Any], right: dict[str, Any], rules: dict[str, Any]):
    left_score, left_entry = _support_received(left, right, rules)
    right_score, right_entry = _support_received(right, left, rules)
    return (left_score + right_score) / 2.0, [left_entry, right_entry]


def _support_received(receiver: dict[str, Any], provider: dict[str, Any], rules: dict[str, Any]):
    day_element = rules["stem_elements"][receiver["pillars"]["day"]["stem"]]
    resource = next(
        element for element, produced in rules["element_produces"].items() if produced == day_element
    )
    peer_percent = provider["distribution"][day_element]
    resource_percent = provider["distribution"][resource]
    score = _clamp((peer_percent + resource_percent) * 2.5)
    return score, {
        "id": f"support.received.{receiver['side']}",
        "owner": receiver["name"],
        "provider": provider["name"],
        "day_element": day_element,
        "peer_percent": peer_percent,
        "resource_element": resource,
        "resource_percent": resource_percent,
        "score": score,
    }


def _cross_interactions(left: dict[str, Any], right: dict[str, Any], rules: dict[str, Any]):
    score = 50.0
    ledger = [{"id": "interactions.base", "amount": 50.0, "kind": "base"}]
    adjustments = rules["interaction_adjustments"]
    pairs = (
        ("stem_combination", rules["stem_combinations"], "stem"),
        ("branch_combination", rules["branch_combinations"], "branch"),
        ("branch_clash", rules["branch_clashes"], "branch"),
        ("branch_harm", rules["branch_harms"], "branch"),
        ("branch_break", rules["branch_breaks"], "branch"),
    )
    for relation, definitions, field in pairs:
        definition_sets = [set(item) for item in definitions]
        for left_position in POSITIONS:
            for right_position in POSITIONS:
                members = {
                    left["pillars"][left_position][field],
                    right["pillars"][right_position][field],
                }
                if members in definition_sets:
                    amount = float(adjustments[relation])
                    score += amount
                    ledger.append(
                        {
                            "id": f"cross.{relation}.{left_position}.{right_position}",
                            "kind": relation,
                            "members": sorted(members),
                            "positions": [f"left.{left_position}", f"right.{right_position}"],
                            "amount": amount,
                        }
                    )
    return _clamp(score), ledger


def _day_core(left: dict[str, Any], right: dict[str, Any], rules: dict[str, Any]):
    config = rules["day_core"]
    left_day = left["pillars"]["day"]
    right_day = right["pillars"]["day"]
    left_element = rules["stem_elements"][left_day["stem"]]
    right_element = rules["stem_elements"][right_day["stem"]]
    if left_element == right_element:
        stem_score = float(config["same_element"])
        stem_relation = "same_element"
    elif (
        rules["element_produces"][left_element] == right_element
        or rules["element_produces"][right_element] == left_element
    ):
        stem_score = float(config["producing_relation"])
        stem_relation = "producing_relation"
    else:
        stem_score = float(config["neutral_control_relation"])
        stem_relation = "control_relation"
    score = stem_score
    ledger = [
        {
            "id": "day_core.stems",
            "kind": stem_relation,
            "members": [left_day["stem"], right_day["stem"]],
            "amount": stem_score,
        }
    ]
    branch_pair = {left_day["branch"], right_day["branch"]}
    branch_rules = (
        ("branch_combination", rules["branch_combinations"]),
        ("branch_clash", rules["branch_clashes"]),
        ("branch_harm", rules["branch_harms"]),
        ("branch_break", rules["branch_breaks"]),
    )
    if left_day["branch"] == right_day["branch"]:
        amount = float(config["same_branch"])
        score += amount
        ledger.append({"id": "day_core.same_branch", "kind": "same_branch", "amount": amount})
    for relation, definitions in branch_rules:
        if branch_pair in [set(item) for item in definitions]:
            amount = float(config[relation])
            score += amount
            ledger.append(
                {
                    "id": f"day_core.{relation}",
                    "kind": relation,
                    "members": sorted(branch_pair),
                    "amount": amount,
                }
            )
    return _clamp(score), ledger


def _structural_stability(left: dict[str, Any], right: dict[str, Any], rules: dict[str, Any]):
    config = rules["stability"]
    score = float(config["base"])
    ledger = [{"id": "stability.base", "amount": score, "kind": "base"}]
    for view in (left, right):
        candidates = sum(
            1
            for item in view["facts"]["interactions"]
            if item.get("transformation", {}).get("status") == "candidate"
        )
        negatives = sum(
            1
            for item in view["facts"]["interactions"]
            if item["type"] in {"branch_clash", "branch_harm", "branch_break", "branch_punishment"}
        )
        for kind, count, penalty_key in (
            ("candidate", candidates, "candidate_penalty"),
            ("negative_interaction", negatives, "negative_interaction_penalty"),
        ):
            amount = -float(config[penalty_key]) * count / 2.0
            score += amount
            ledger.append(
                {
                    "id": f"stability.{kind}.{view['side']}",
                    "owner": view["name"],
                    "kind": kind,
                    "count": count,
                    "amount": amount,
                }
            )
        confidence = view["scores"]["confidence"]["level"]
        penalty = 0.0
        if confidence == "low":
            penalty = -float(config["low_confidence_penalty"]) / 2.0
        elif confidence == "medium":
            penalty = -float(config["medium_confidence_penalty"]) / 2.0
        score += penalty
        ledger.append(
            {
                "id": f"stability.confidence.{view['side']}",
                "owner": view["name"],
                "kind": "source_confidence",
                "level": confidence,
                "amount": penalty,
            }
        )
    return _clamp(score), ledger


def _view(chart: dict[str, Any], alternate: bool, side: str) -> dict[str, Any]:
    key = "alternate" if alternate else "primary"
    return {
        "side": side,
        "name": chart["input"]["name"],
        "pillars": chart["pillars"][key],
        "facts": chart["facts"][key],
        "scores": chart["scores"][key],
        "distribution": chart["scores"][key]["adjusted_distribution"],
    }


def _alternate_options(chart: dict[str, Any]) -> tuple[bool, ...]:
    return (False, True) if chart["pillars"].get("alternate") is not None else (False,)


def _weighted_score(dimensions: list[dict[str, Any]], weights: dict[str, int], digits: int) -> float:
    by_id = {item["id"]: item["score"] for item in dimensions}
    return round(sum(by_id[identifier] * weight / 100.0 for identifier, weight in weights.items()), digits)


def _confidence(left: dict[str, Any], right: dict[str, Any], spread: float) -> dict[str, Any]:
    levels = [
        left["scores"]["primary"]["confidence"]["level"],
        right["scores"]["primary"]["confidence"]["level"],
    ]
    rank = {"high": 2, "medium": 1, "low": 0}
    level = min(levels, key=rank.__getitem__)
    if spread >= 15:
        level = "low"
    elif spread >= 7 and level == "high":
        level = "medium"
    return {"level": level, "source_levels": levels, "sensitivity_spread": round(spread, 2)}


def _validate_chart_shape(chart: dict[str, Any]) -> None:
    try:
        for key in ("primary",):
            for position in POSITIONS:
                chart["pillars"][key][position]["stem"]
                chart["pillars"][key][position]["branch"]
            chart["facts"][key]["interactions"]
            chart["scores"][key]["adjusted_distribution"]
            chart["scores"][key]["confidence"]["level"]
        if chart["pillars"].get("alternate") is not None:
            chart["facts"]["alternate"]["interactions"]
            chart["scores"]["alternate"]["adjusted_distribution"]
    except (KeyError, TypeError) as error:
        raise CompatibilityError(f"incomplete chart source: missing {error}") from error


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))


@lru_cache(maxsize=1)
def _rules() -> dict[str, Any]:
    return json.loads((SHARED_ROOT / "rules" / "compatibility-v1.json").read_text(encoding="utf-8"))
