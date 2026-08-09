"""Evaluate versioned structural BaZi rules without interpreting them."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from itertools import combinations
from typing import Any

from .pillars import BRANCHES, FourPillars, Pillar

POSITIONS = ("year", "month", "day", "hour")


def ten_god(day_stem: str, other_stem: str, rules: Mapping[str, Any]) -> str:
    """Derive one Ten-God label from element flow and polarity."""

    elements = rules["stem_elements"]
    polarities = rules["stem_polarities"]
    produces = rules["element_produces"]
    controls = rules["element_controls"]
    source = elements[day_stem]
    other = elements[other_stem]
    polarity = "same" if polarities[day_stem] == polarities[other_stem] else "opposite"
    if source == other:
        relation = "same"
    elif produces[source] == other:
        relation = "produces"
    elif controls[source] == other:
        relation = "controls"
    elif controls[other] == source:
        relation = "controlled_by"
    elif produces[other] == source:
        relation = "produced_by"
    else:  # pragma: no cover - the five-element graph is exhaustive
        raise ValueError(f"unresolved element relationship {source} -> {other}")
    return rules["ten_gods"][f"{relation}_{polarity}"]


def derive_chart_facts(pillars: FourPillars, rules: Mapping[str, Any]) -> dict[str, Any]:
    """Produce auditable structural facts from four already-calculated pillars."""

    day_stem = pillars.day.stem
    pillar_map = {position: getattr(pillars, position) for position in POSITIONS}
    expanded = {
        position: _pillar_facts(position, pillar, day_stem, rules) for position, pillar in pillar_map.items()
    }
    interactions = _interactions(pillar_map, rules)
    return {
        "model_version": rules["model_version"],
        "pillars": expanded,
        "xun_kong": list(rules["xun_kong"][pillars.day.cycle_index // 10]),
        "interactions": interactions,
        "shen_sha": _shen_sha(pillar_map, rules),
    }


def _pillar_facts(
    position: str,
    pillar: Pillar,
    day_stem: str,
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    start = BRANCHES.index(rules["twelve_stage_start"][day_stem])
    direction = rules["twelve_stage_direction"][day_stem]
    stage_index = ((pillar.branch_index - start) * direction) % 12
    return {
        "position": position,
        "stem": pillar.stem,
        "branch": pillar.branch,
        "text": pillar.text,
        "stem_element": rules["stem_elements"][pillar.stem],
        "stem_polarity": rules["stem_polarities"][pillar.stem],
        "visible_ten_god": "日主" if position == "day" else ten_god(day_stem, pillar.stem, rules),
        "hidden_stems": [
            {"stem": stem, "ten_god": ten_god(day_stem, stem, rules)}
            for stem in rules["hidden_stems"][pillar.branch]
        ],
        "nayin": rules["nayin"][pillar.text],
        "twelve_stage": rules["twelve_stages"][stage_index],
    }


def _interactions(pillars: Mapping[str, Pillar], rules: Mapping[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stems = {position: pillar.stem for position, pillar in pillars.items()}
    branches = {position: pillar.branch for position, pillar in pillars.items()}
    relations = rules["relations"]

    _match_pairs(found, "stem_combination", stems, relations["stem_combination"], pillars, rules)
    _match_pairs(
        found,
        "branch_six_combination",
        branches,
        relations["branch_six_combination"],
        pillars,
        rules,
    )
    for relation_type in ("branch_clash", "branch_harm", "branch_break"):
        _match_pairs(found, relation_type, branches, relations[relation_type], pillars, rules)
    for relation_type in ("branch_three_combination", "branch_three_meeting"):
        _match_groups(found, relation_type, branches, relations[relation_type], pillars, rules)
    _match_groups(
        found,
        "branch_punishment",
        branches,
        relations["branch_punishment"],
        pillars,
        rules,
    )

    counts = Counter(branches.values())
    for branch in relations["branch_self_punishment"]:
        if counts[branch] >= 2:
            positions = [position for position, value in branches.items() if value == branch]
            found.append(
                {
                    "type": "branch_punishment",
                    "members": [branch, branch],
                    "positions": positions[:2],
                    "kind": "自刑",
                }
            )

    found.sort(key=lambda item: (item["type"], item["positions"], item["members"]))
    for index, item in enumerate(found, 1):
        item["id"] = f"interaction-{index:03d}"
    return found


def _match_pairs(
    found: list[dict[str, Any]],
    relation_type: str,
    values: Mapping[str, str],
    definitions: list[Any],
    pillars: Mapping[str, Pillar],
    rules: Mapping[str, Any],
) -> None:
    for left, right in combinations(POSITIONS, 2):
        actual = {values[left], values[right]}
        for raw in definitions:
            definition = raw if isinstance(raw, dict) else {"members": raw}
            if actual == set(definition["members"]):
                item: dict[str, Any] = {
                    "type": relation_type,
                    "members": list(definition["members"]),
                    "positions": [left, right],
                }
                for key in ("element", "kind"):
                    if key in definition:
                        item[key] = definition[key]
                if "element" in definition:
                    item["transformation"] = _transformation(
                        definition["members"], definition["element"], pillars, rules
                    )
                found.append(item)


def _match_groups(
    found: list[dict[str, Any]],
    relation_type: str,
    values: Mapping[str, str],
    definitions: list[Mapping[str, Any]],
    pillars: Mapping[str, Pillar],
    rules: Mapping[str, Any],
) -> None:
    present = set(values.values())
    for definition in definitions:
        members = definition["members"]
        if set(members).issubset(present):
            positions = [
                next(position for position, value in values.items() if value == member) for member in members
            ]
            item: dict[str, Any] = {
                "type": relation_type,
                "members": list(members),
                "positions": positions,
            }
            for key in ("element", "kind"):
                if key in definition:
                    item[key] = definition[key]
            if "element" in definition:
                item["transformation"] = _transformation(members, definition["element"], pillars, rules)
            found.append(item)


def _transformation(
    members: list[str],
    element: str,
    pillars: Mapping[str, Pillar],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    branch_members = {member for member in members if member in BRANCHES}
    month_main_stem = rules["hidden_stems"][pillars["month"].branch][0]
    month_support = rules["stem_elements"][month_main_stem] == element
    all_branches = [pillar.branch for pillar in pillars.values()]
    outside = [branch for branch in all_branches if branch not in branch_members]
    clashes = [set(pair) for pair in rules["relations"]["branch_clash"]]
    undisrupted = not any({member, other} in clashes for member in branch_members for other in outside)
    prerequisites = {
        "all_members": True,
        "month_support": month_support,
        "undisrupted": undisrupted,
    }
    return {
        "element": element,
        "status": "formed" if all(prerequisites.values()) else "candidate",
        "prerequisites": prerequisites,
    }


def _shen_sha(pillars: Mapping[str, Pillar], rules: Mapping[str, Any]) -> list[dict[str, Any]]:
    day_branch = pillars["day"].branch
    chart_branches = {pillar.branch for pillar in pillars.values()}
    result = []
    for definition in rules.get("shen_sha", []):
        for group, target in definition["day_groups"].items():
            if day_branch in group and target in chart_branches:
                result.append(
                    {
                        "name": definition["name"],
                        "target": target,
                        "basis": f"day:{day_branch}",
                        "evidence_level": "secondary",
                    }
                )
                break
    return result
