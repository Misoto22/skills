"""Ledger-first five-element and day-master heuristic scoring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .pillars import FourPillars

POSITIONS = ("year", "month", "day", "hour")


def score_chart(
    pillars: FourPillars,
    facts: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    """Score a chart from declared weights while retaining every arithmetic input."""

    elements = rules["elements"]
    raw_base = dict.fromkeys(elements, 0.0)
    ledger: list[dict[str, Any]] = []
    pillar_facts = facts["pillars"]
    for position in POSITIONS:
        visible_element = pillar_facts[position]["stem_element"]
        visible_amount = float(rules["visible_stem_weights"][position])
        raw_base[visible_element] += visible_amount
        ledger.append(
            _entry(
                f"base.visible.{position}",
                "base",
                visible_element,
                visible_amount,
                f"{position} visible stem",
            )
        )

        hidden = pillar_facts[position]["hidden_stems"]
        shares = rules["hidden_stem_shares"][str(len(hidden))]
        branch_weight = float(rules["hidden_branch_weights"][position])
        for index, (item, share) in enumerate(zip(hidden, shares, strict=True)):
            element = rules["stem_elements"][item["stem"]]
            amount = branch_weight * float(share)
            raw_base[element] += amount
            ledger.append(
                _entry(
                    f"base.hidden.{position}.{index}",
                    "base",
                    element,
                    amount,
                    f"{position} hidden stem {item['stem']} share {share:g}",
                )
            )

    month_main_stem = pillar_facts["month"]["hidden_stems"][0]["stem"]
    month_element = rules["stem_elements"][month_main_stem]
    raw_adjusted: dict[str, float] = {}
    for element in elements:
        status = _season_status(month_element, element, rules)
        multiplier = float(rules["seasonal_multipliers"][status])
        adjusted = raw_base[element] * multiplier
        raw_adjusted[element] = adjusted
        ledger.append(
            _entry(
                f"adjust.seasonal.{element}",
                "adjustment",
                element,
                adjusted - raw_base[element],
                f"month command {month_element}: {status} x {multiplier:g}",
            )
        )

    for interaction in facts.get("interactions", []):
        transformation = interaction.get("transformation")
        if transformation is None:
            continue
        applied = transformation["status"] == "formed"
        amount = float(rules["transformation_bonus"]) if applied else 0.0
        element = transformation["element"]
        raw_adjusted[element] += amount
        ledger.append(
            _entry(
                f"adjust.transform.{interaction['id']}",
                "adjustment",
                element,
                amount,
                f"{interaction['type']} {transformation['status']}",
                applied=applied,
            )
        )

    strength = _score_strength(pillars, facts, rules)
    unresolved = sum(
        1
        for item in facts.get("interactions", [])
        if item.get("transformation", {}).get("status") == "candidate"
    )
    confidence_rules = rules["confidence"]
    if unresolved <= confidence_rules["high_max_unresolved_transformations"]:
        confidence = "high"
    elif unresolved <= confidence_rules["medium_max_unresolved_transformations"]:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "model_version": rules["model_id"],
        "score_semantics": "versioned heuristic scores; not probabilities or official measurements",
        "pillars": {
            position: {
                "stem": getattr(pillars, position).stem,
                "branch": getattr(pillars, position).branch,
            }
            for position in POSITIONS
        },
        "base_distribution": _normalize(raw_base, rules["rounding_digits"]),
        "adjusted_distribution": _normalize(raw_adjusted, rules["rounding_digits"]),
        "day_master_strength": strength,
        "special_structure": {
            "status": "not_established",
            "reason": "no special structure is declared without a separate rule and every prerequisite",
        },
        "ledger": ledger,
        "confidence": {
            "level": confidence,
            "unresolved_transformations": unresolved,
        },
    }


def _score_strength(
    pillars: FourPillars,
    facts: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    config = rules["strength"]
    day_element = rules["stem_elements"][pillars.day.stem]
    month_main = facts["pillars"]["month"]["hidden_stems"][0]["stem"]
    month_element = rules["stem_elements"][month_main]
    details: list[dict[str, Any]] = []
    components: dict[str, float] = {
        "base": float(config["base"]),
        "seasonal": 0.0,
        "root": 0.0,
        "visible_support": 0.0,
        "control": 0.0,
        "production": 0.0,
        "drainage": 0.0,
        "structural": 0.0,
    }
    status = _season_status(month_element, day_element, rules)
    components["seasonal"] = float(config["seasonal"][status])
    details.append(
        {
            "id": "strength.seasonal",
            "component": "seasonal",
            "amount": components["seasonal"],
            "basis": status,
        }
    )

    for position in POSITIONS:
        hidden = facts["pillars"][position]["hidden_stems"]
        shares = rules["hidden_stem_shares"][str(len(hidden))]
        root_share = sum(
            float(share)
            for item, share in zip(hidden, shares, strict=True)
            if rules["stem_elements"][item["stem"]] == day_element
        )
        amount = float(config["root_position_weights"][position]) * root_share
        components["root"] += amount
        details.append(
            {
                "id": f"strength.root.{position}",
                "component": "root",
                "amount": amount,
                "basis": f"{root_share:g} day-element hidden share",
            }
        )

    for position in ("year", "month", "hour"):
        other = rules["stem_elements"][getattr(pillars, position).stem]
        component, weight = _visible_strength_relation(day_element, other, config, rules)
        components[component] += weight
        details.append(
            {
                "id": f"strength.visible.{position}",
                "component": component,
                "amount": weight,
                "basis": f"visible {other} relative to day element {day_element}",
            }
        )

    for interaction in facts.get("interactions", []):
        transformation = interaction.get("transformation")
        if not transformation or transformation["status"] != "formed":
            continue
        element = transformation["element"]
        if element == day_element or rules["element_produces"][element] == day_element:
            amount = float(config["structural_support"])
        elif rules["element_controls"][element] == day_element:
            amount = float(config["structural_pressure"])
        else:
            amount = 0.0
        components["structural"] += amount
        details.append(
            {
                "id": f"strength.structural.{interaction['id']}",
                "component": "structural",
                "amount": amount,
                "basis": transformation["element"],
            }
        )

    raw = sum(components.values())
    clamped = min(100.0, max(0.0, raw))
    thresholds = config["thresholds"]
    if clamped <= thresholds["weak_max"]:
        label = "weak"
    elif clamped >= thresholds["strong_min"]:
        label = "strong"
    else:
        label = "balanced"
    return {
        "score": round(clamped, rules["rounding_digits"]),
        "raw_score": round(raw, rules["rounding_digits"]),
        "classification": label,
        "clamped": clamped != raw,
        "ledger": [
            {"component": component, "amount": round(amount, rules["rounding_digits"])}
            for component, amount in components.items()
        ],
        "details": details,
    }


def _visible_strength_relation(
    day_element: str,
    other: str,
    config: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> tuple[str, float]:
    produces = rules["element_produces"]
    controls = rules["element_controls"]
    if other == day_element:
        return "visible_support", float(config["visible_support_same"])
    if produces[other] == day_element:
        return "visible_support", float(config["visible_support_resource"])
    if controls[other] == day_element:
        return "control", float(config["control_pressure"])
    if produces[day_element] == other:
        return "production", float(config["production_drain"])
    return "drainage", float(config["wealth_drain"])


def _season_status(
    month_element: str,
    target: str,
    rules: Mapping[str, Any],
) -> str:
    produces = rules["element_produces"]
    controls = rules["element_controls"]
    if target == month_element:
        return "旺"
    if produces[month_element] == target:
        return "相"
    if produces[target] == month_element:
        return "休"
    if controls[target] == month_element:
        return "囚"
    return "死"


def _normalize(raw: Mapping[str, float], digits: int) -> dict[str, float]:
    total = sum(raw.values())
    if total <= 0.0:
        raise ValueError("element distribution has no positive contributions")
    result = {key: round(value / total * 100.0, digits) for key, value in raw.items()}
    largest = max(raw, key=raw.__getitem__)
    result[largest] = round(result[largest] + (100.0 - sum(result.values())), digits)
    return result


def _entry(
    identifier: str,
    phase: str,
    element: str,
    amount: float,
    basis: str,
    *,
    applied: bool = True,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "phase": phase,
        "element": element,
        "amount": amount,
        "basis": basis,
        "applied": applied,
    }
