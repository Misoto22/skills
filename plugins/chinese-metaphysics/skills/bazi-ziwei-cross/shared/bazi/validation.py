"""What a reading requires of an artifact, beyond its envelope being intact.

`validate_envelope` answers one question: is this the file the calculator wrote?
A reading needs a second answer, and it is the one its own prose kept asking for
— are the fields it is about to cite actually present and self-consistent. A
chart missing its hour pillar, a comparison whose weights no longer produce its
own score, a chart with eleven palaces: every one of those passes a checksum,
because whatever assembled it hashed it too. Only a hand-built or hand-edited
source reaches a reading that way, which is exactly the source a reading cannot
detect by reading.

Two rules shape every check here:

- **Collect, do not stop.** One run reports the whole picture, so a person
  repairing a source sees all of it rather than the first thing that tripped.
- **Structure before hash.** "the hour pillar is missing" tells someone what to
  fix; "the hash no longer matches" tells them only that something did. An
  edited artifact produces both, so the useful one is reported first.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise
from typing import Any

from .artifacts import (
    CHART_SCHEMA,
    COMPATIBILITY_SCHEMA,
    SCHEMAS,
    ZIWEI_SCHEMA,
    ArtifactError,
    validate_envelope,
)

CHART = "chart"
COMPATIBILITY = "compatibility"
ZIWEI = "ziwei"

SCHEMA_FOR_KIND = {
    CHART: CHART_SCHEMA,
    COMPATIBILITY: COMPATIBILITY_SCHEMA,
    ZIWEI: ZIWEI_SCHEMA,
}

POSITIONS = ("year", "month", "day", "hour")
PALACE_COUNT = 12
ELEMENT_COUNT = 5
# The five the model always calculates. A comparison carrying four of them, or a
# sixth nobody weighted, is not this model's output whatever it hashes to.
GENERAL_DIMENSIONS = (
    "element_complementarity",
    "directional_day_master_support",
    "stem_branch_interactions",
    "day_pillar_core",
    "structural_stability",
)
# Scores round to two decimals, so a recomputation that lands within a cent of
# the stored figure agrees with it. Anything wider is arithmetic, not rounding.
ARITHMETIC_TOLERANCE = 0.01
# Percentages are stored rounded per element, so five of them can miss 100 by a
# few hundredths honestly. Half a point cannot happen without a dropped element.
DISTRIBUTION_TOLERANCE = 0.5


class ArtifactDefect(ValueError):
    """An artifact is not complete enough to read, whatever its checksum says."""


def defects(envelope: Mapping[str, Any], kind: str) -> list[str]:
    """Return every independent defect in one artifact of the named kind."""

    expected = SCHEMA_FOR_KIND.get(kind)
    if expected is None:
        raise ArtifactDefect(f"unsupported artifact kind {kind!r}")

    # A wrong schema or version stops the run rather than joining the list. Every
    # shape check below then describes an artifact this is not, and twelve
    # defects about a chart nobody supplied bury the one that matters.
    schema = envelope.get("schema")
    if schema != expected:
        return [f"schema: expected {expected!r}, got {schema!r}"]
    version = envelope.get("schema_version")
    if version != SCHEMAS[expected]:
        return [f"schema_version: expected {SCHEMAS[expected]}, got {version!r}"]

    return _SHAPE_CHECKS[kind](envelope)


def validate(envelope: Mapping[str, Any], kind: str) -> dict[str, Any]:
    """Return the artifact once its shape and its checksum both hold."""

    problems = defects(envelope, kind)
    if problems:
        raise ArtifactDefect("; ".join(problems))
    try:
        return validate_envelope(envelope)
    except ArtifactError as error:
        raise ArtifactDefect(str(error)) from error


def pairing_defects(chart: Mapping[str, Any], ziwei: Mapping[str, Any]) -> list[str]:
    """Return why two intact charts do not describe one person at one moment.

    A cross-reading is the one place this can go wrong invisibly: each artifact
    is impeccable on its own, and comparing two different moments produces a
    report that reads as authoritative and means nothing.
    """

    problems: list[str] = []
    if _get(chart, "input", "name") != _get(ziwei, "input", "name"):
        problems.append(
            f"input.name: the BaZi chart is for {_get(chart, 'input', 'name')!r} and the "
            f"Zi Wei chart for {_get(ziwei, 'input', 'name')!r}"
        )

    # The resolved date rather than the entered one: a lunar-entered BaZi and a
    # gregorian-entered Zi Wei for the same birth are the same moment, and
    # comparing what was typed would refuse that pair for no reason.
    left_date = _get(chart, "calendar", "resolved_gregorian_date")
    right_date = _get(ziwei, "calendar", "resolved_gregorian_date")
    if left_date != right_date:
        problems.append(
            f"calendar.resolved_gregorian_date: {left_date!r} against {right_date!r}; "
            "two charts for different days cannot be crossed"
        )

    for field in ("birth_time", "timezone", "latitude", "longitude"):
        left, right = _get(chart, "input", field), _get(ziwei, "input", field)
        if left != right:
            problems.append(f"input.{field}: {left!r} against {right!r}")

    # Both systems emit an alternate on exactly a 23:00-23:59 true solar hour, so
    # one chart having one and the other not means they were not built from the
    # same moment, however well each validates alone.
    left_alternate = bool(_get(chart, "sensitivity", "alternate_day_boundary"))
    right_alternate = bool(_get(ziwei, "sensitivity", "alternate_day_boundary"))
    if left_alternate != right_alternate:
        carrier = "BaZi" if left_alternate else "Zi Wei"
        problems.append(
            f"sensitivity.alternate_day_boundary: only the {carrier} chart carries a boundary "
            "alternate, and both derive from the same true solar time"
        )
    return problems


def _chart_defects(envelope: Mapping[str, Any]) -> list[str]:
    problems = _identity_defects(envelope)
    problems.extend(_pillar_defects(envelope, "primary"))
    problems.extend(_fact_defects(envelope, "primary"))
    problems.extend(_score_defects(envelope, "primary"))

    for field in ("calendar_model", "scoring_model"):
        if not _get(envelope, "methodology", field):
            problems.append(f"methodology.{field}: a reading names the model it read")
    if not _get(envelope, "time", "true_solar"):
        problems.append("time.true_solar: the day and hour pillars rest on it")

    declared = _sensitivity_flag(envelope, problems)
    for block in ("pillars", "facts", "scores"):
        present = _get(envelope, block, "alternate") is not None
        if declared and not present:
            problems.append(f"{block}.alternate: declared by sensitivity, and missing")
        if not declared and present:
            problems.append(f"{block}.alternate: present, and sensitivity does not declare it")
    if declared:
        problems.extend(_pillar_defects(envelope, "alternate"))
        problems.extend(_fact_defects(envelope, "alternate"))
        problems.extend(_score_defects(envelope, "alternate"))
    return problems


def _sensitivity_flag(envelope: Mapping[str, Any], problems: list[str]) -> bool:
    """Return whether a boundary alternate is declared, and require it to say so.

    A source that omits the flag entirely reads as "no alternate", which is the
    one wrong answer: every reading skill has to tell a person whether the
    boundary choice moved their chart, and silence is indistinguishable from a
    confident no.
    """

    flag = _get(envelope, "sensitivity", "alternate_day_boundary")
    if not isinstance(flag, bool):
        problems.append(
            "sensitivity.alternate_day_boundary: required, and true or false; "
            "an absent flag reads as a confident no"
        )
    return flag is True


def _identity_defects(envelope: Mapping[str, Any]) -> list[str]:
    if not str(_get(envelope, "input", "name") or "").strip():
        return ["input.name: a chart with no identity cannot be filed or cited"]
    return []


def _pillar_defects(envelope: Mapping[str, Any], key: str) -> list[str]:
    block = _get(envelope, "pillars", key)
    if not isinstance(block, Mapping):
        return [f"pillars.{key}: required"]

    problems: list[str] = []
    for position in POSITIONS:
        pillar = block.get(position)
        if not isinstance(pillar, Mapping):
            problems.append(f"pillars.{key}.{position}: a BaZi chart has four pillars")
            continue
        for field in ("stem", "branch", "text"):
            if not str(pillar.get(field) or "").strip():
                problems.append(f"pillars.{key}.{position}.{field}: required")
    if not _get(block, "boundaries", "day_boundary"):
        problems.append(f"pillars.{key}.boundaries.day_boundary: the day and hour pillars depend on it")
    return problems


def _fact_defects(envelope: Mapping[str, Any], key: str) -> list[str]:
    block = _get(envelope, "facts", key)
    if not isinstance(block, Mapping):
        return [f"facts.{key}: required"]

    problems: list[str] = []
    if not isinstance(block.get("interactions"), list):
        problems.append(f"facts.{key}.interactions: expected a list, empty when the chart has none")
    pillars = block.get("pillars")
    if not isinstance(pillars, Mapping) or set(pillars) != set(POSITIONS):
        problems.append(f"facts.{key}.pillars: expected one entry per pillar")
    if not block.get("model_version"):
        problems.append(f"facts.{key}.model_version: required")
    return problems


def _score_defects(envelope: Mapping[str, Any], key: str) -> list[str]:
    block = _get(envelope, "scores", key)
    if not isinstance(block, Mapping):
        return [f"scores.{key}: required"]

    problems: list[str] = []
    elements: list[set[str]] = []
    for name in ("base_distribution", "adjusted_distribution"):
        distribution = block.get(name)
        if not isinstance(distribution, Mapping) or not distribution:
            problems.append(f"scores.{key}.{name}: required")
            continue
        elements.append(set(distribution))
        # Counted, not only summed. An element whose share rounded to zero drops
        # out of the total without moving it, and a reading then never mentions
        # the one element the chart has none of — which is most of what a reader
        # came for.
        if len(distribution) != ELEMENT_COUNT:
            problems.append(
                f"scores.{key}.{name}: five elements are always scored, found {len(distribution)}"
            )
        values = [_number(value) for value in distribution.values()]
        if None in values:
            problems.append(f"scores.{key}.{name}: every element carries a number")
            continue
        total = sum(value for value in values if value is not None)
        if abs(total - 100.0) > DISTRIBUTION_TOLERANCE:
            problems.append(f"scores.{key}.{name}: sums to {total:.2f}, not 100")
    if len(elements) == 2 and elements[0] != elements[1]:
        problems.append(f"scores.{key}: the base and adjusted distributions score different elements")

    strength = block.get("day_master_strength")
    if not isinstance(strength, Mapping):
        problems.append(f"scores.{key}.day_master_strength: a natal reading is built on it")
    else:
        for field in ("score", "classification", "ledger"):
            if strength.get(field) in (None, "", []):
                problems.append(f"scores.{key}.day_master_strength.{field}: required")

    if not block.get("ledger"):
        problems.append(f"scores.{key}.ledger: a reading cites it, so an empty one is a defect")
    if not _get(block, "confidence", "level"):
        problems.append(f"scores.{key}.confidence.level: required")
    return problems


def _compatibility_defects(envelope: Mapping[str, Any]) -> list[str]:
    problems = _people_defects(envelope)
    scores = _weighted_dimensions(envelope, problems)
    problems.extend(_general_score_defects(envelope, scores))
    problems.extend(_contextual_defects(envelope, scores))
    problems.extend(_sensitivity_defects(envelope))

    if not _get(envelope, "confidence", "level"):
        problems.append("confidence.level: required")
    if not envelope.get("model_version"):
        problems.append("model_version: a reading names the model that produced the scores")
    return problems


def _people_defects(envelope: Mapping[str, Any]) -> list[str]:
    people = envelope.get("people")
    if not isinstance(people, Mapping) or set(people) != {"left", "right"}:
        return ["people: a comparison names exactly a left and a right"]

    problems: list[str] = []
    checksums: list[str] = []
    for side in ("left", "right"):
        person = people[side]
        if not isinstance(person, Mapping):
            problems.append(f"people.{side}: required")
            continue
        if not str(person.get("name") or "").strip():
            problems.append(f"people.{side}.name: a directional claim names both people")
        checksum = str(person.get("chart_checksum") or "").strip()
        if not checksum:
            problems.append(f"people.{side}.chart_checksum: a comparison cites the charts it read")
        else:
            checksums.append(checksum)
    if len(checksums) == 2 and checksums[0] == checksums[1]:
        problems.append("people: both sides name one chart; this compares someone with themselves")
    return problems


def _weighted_dimensions(envelope: Mapping[str, Any], problems: list[str]) -> dict[str, tuple[float, float]]:
    """Return each sound dimension's (score, weight), appending what was wrong."""

    dimensions = envelope.get("dimensions")
    if not isinstance(dimensions, list):
        problems.append("dimensions: required")
        return {}

    declared = _get(envelope, "methodology", "general_weights")
    sound: dict[str, tuple[float, float]] = {}
    for index, dimension in enumerate(dimensions):
        if not isinstance(dimension, Mapping):
            problems.append(f"dimensions[{index}]: expected an object")
            continue
        identifier = str(dimension.get("id") or "")
        label = identifier or f"[{index}]"
        for field in ("id", "name", "weight", "score", "ledger"):
            if field not in dimension:
                problems.append(f"dimensions.{label}.{field}: required")
        if not dimension.get("ledger"):
            problems.append(f"dimensions.{label}.ledger: a dimension with no ledger cannot be cited")
        score, weight = _number(dimension.get("score")), _number(dimension.get("weight"))
        if score is None or not 0.0 <= score <= 100.0:
            problems.append(f"dimensions.{label}.score: expected a number from 0 to 100")
        if weight is None:
            problems.append(f"dimensions.{label}.weight: expected a number")
        if isinstance(declared, Mapping) and identifier in declared:
            stated = _number(declared[identifier])
            if weight is not None and stated is not None and abs(weight - stated) > ARITHMETIC_TOLERANCE:
                problems.append(f"dimensions.{label}.weight: {weight:g}, and methodology declares {stated:g}")
        if identifier and score is not None and weight is not None:
            sound[identifier] = (score, weight)

    missing = sorted(set(GENERAL_DIMENSIONS) - {str(item.get("id")) for item in _objects(dimensions)})
    if missing:
        problems.append(f"dimensions: the model always calculates all five; missing {', '.join(missing)}")
    total = sum(weight for _, weight in sound.values())
    if len(sound) == len(GENERAL_DIMENSIONS) and abs(total - 100.0) > ARITHMETIC_TOLERANCE:
        problems.append(f"dimensions: weights sum to {total:g}, not 100")
    return sound


def _general_score_defects(
    envelope: Mapping[str, Any],
    scores: dict[str, tuple[float, float]],
) -> list[str]:
    general = _number(_get(envelope, "scores", "general"))
    if general is None:
        return ["scores.general: required"]
    if len(scores) != len(GENERAL_DIMENSIONS):
        return []
    expected = sum(score * weight / 100.0 for score, weight in scores.values())
    if abs(expected - general) > ARITHMETIC_TOLERANCE:
        return [f"scores.general: {general:g} is not what its own dimensions produce ({expected:.2f})"]
    return []


def _contextual_defects(
    envelope: Mapping[str, Any],
    scores: dict[str, tuple[float, float]],
) -> list[str]:
    block = envelope.get("scores")
    if not isinstance(block, Mapping):
        return ["scores: required"]

    problems: list[str] = []
    for field in ("contextual", "contextual_profile"):
        if field not in block:
            problems.append(f"scores.{field}: required, and null when no context was selected")
    relationship = envelope.get("relationship_type")
    contextual, profile = block.get("contextual"), block.get("contextual_profile")

    if relationship is None:
        if contextual is not None or profile is not None:
            problems.append(
                "scores.contextual: a contextual score with no relationship_type; a reading would "
                "have to invent the lens it answers"
            )
        return problems

    if not isinstance(profile, Mapping):
        problems.append("scores.contextual_profile: a contextual score without its weights cannot be audited")
        return problems
    value = _number(contextual)
    if value is None:
        problems.append(f"scores.contextual: required, {relationship!r} was selected")
        return problems
    weights = {name: _number(weight) for name, weight in profile.items()}
    auditable = (
        len(scores) == len(GENERAL_DIMENSIONS)
        and set(weights) <= set(scores)
        and None not in weights.values()
    )
    if auditable:
        expected = sum(scores[name][0] * weight / 100.0 for name, weight in weights.items() if weight)
        if abs(expected - value) > ARITHMETIC_TOLERANCE:
            problems.append(
                f"scores.contextual: {value:g} is not what its own profile produces ({expected:.2f})"
            )
    return problems


def _sensitivity_defects(envelope: Mapping[str, Any]) -> list[str]:
    block = envelope.get("sensitivity")
    if not isinstance(block, Mapping):
        return ["sensitivity: required"]

    problems: list[str] = []
    if not block.get("variants"):
        problems.append("sensitivity.variants: at least the primary-primary comparison")
    minimum, maximum = _number(block.get("minimum")), _number(block.get("maximum"))
    spread = _number(block.get("spread"))
    if minimum is None or maximum is None or spread is None:
        problems.append("sensitivity: minimum, maximum, and spread are all required")
        return problems
    if abs((maximum - minimum) - spread) > ARITHMETIC_TOLERANCE:
        problems.append(f"sensitivity.spread: {spread:g} is not maximum minus minimum")
    general = _number(_get(envelope, "scores", "general"))
    low, high = minimum - ARITHMETIC_TOLERANCE, maximum + ARITHMETIC_TOLERANCE
    if general is not None and not low <= general <= high:
        problems.append(f"sensitivity: the displayed score {general:g} sits outside its own range")
    return problems


def _ziwei_defects(envelope: Mapping[str, Any]) -> list[str]:
    problems = _identity_defects(envelope)
    problems.extend(_palace_defects(envelope, "primary"))

    if not _get(envelope, "methodology", "placement_model"):
        problems.append("methodology.placement_model: a reading names the lineage it read")
    if not _get(envelope, "time", "true_solar"):
        problems.append("time.true_solar: the hour branch rests on it")

    declared = _sensitivity_flag(envelope, problems)
    present = _get(envelope, "chart", "alternate") is not None
    if declared and not present:
        problems.append("chart.alternate: declared by sensitivity, and missing")
    if not declared and present:
        problems.append("chart.alternate: present, and sensitivity does not declare it")
    if declared:
        problems.extend(_palace_defects(envelope, "alternate"))
    return problems


def _palace_defects(envelope: Mapping[str, Any], key: str) -> list[str]:
    chart = _get(envelope, "chart", key)
    if not isinstance(chart, Mapping):
        return [f"chart.{key}: required"]

    palaces = _objects(chart.get("palaces"))
    problems: list[str] = []
    if not isinstance(chart.get("palaces"), list) or len(chart["palaces"]) != PALACE_COUNT:
        found = len(chart["palaces"]) if isinstance(chart.get("palaces"), list) else 0
        problems.append(f"chart.{key}.palaces: a Zi Wei chart has twelve palaces, found {found}")

    stars_by_branch: dict[str, str] = {}
    for index, palace in enumerate(palaces):
        for field in ("branch", "stem", "name"):
            if not str(palace.get(field) or "").strip():
                problems.append(f"chart.{key}.palaces[{index}].{field}: required")
        if not isinstance(palace.get("stars"), list):
            problems.append(f"chart.{key}.palaces[{index}].stars: expected a list, empty when none sit there")
            continue
        for star in _objects(palace["stars"]):
            name = str(star.get("name") or "")
            if name:
                stars_by_branch[name] = str(palace.get("branch") or "")

    if len(palaces) == PALACE_COUNT:
        for field, label in (("name", "names"), ("branch", "branches")):
            if len({str(palace.get(field)) for palace in palaces}) != PALACE_COUNT:
                problems.append(f"chart.{key}.palaces: twelve palaces carry twelve distinct {label}")

    problems.extend(_marked_palace_defects(chart, key, palaces))
    problems.extend(_placement_defects(chart, key, stars_by_branch))
    problems.extend(_decade_defects(chart, key))
    return problems


def _marked_palace_defects(chart: Mapping[str, Any], key: str, palaces: list[Mapping[str, Any]]) -> list[str]:
    problems: list[str] = []
    for flag, field, label in (
        ("is_life_palace", "life_palace", "the life palace"),
        ("is_body_palace", "body_palace", "the body palace"),
    ):
        marked = [palace for palace in palaces if palace.get(flag)]
        if len(marked) != 1:
            problems.append(f"chart.{key}.palaces: exactly one palace is marked {label}, found {len(marked)}")
            continue
        branch = _get(chart, field, "branch")
        if branch != marked[0].get("branch"):
            problems.append(
                f"chart.{key}.{field}.branch: {branch!r}, and {label} is marked on "
                f"{marked[0].get('branch')!r}"
            )
    for field in ("bureau", "lunar", "year_pillar"):
        if not isinstance(chart.get(field), Mapping) or not chart[field]:
            problems.append(f"chart.{key}.{field}: required")
    return problems


def _placement_defects(chart: Mapping[str, Any], key: str, stars_by_branch: dict[str, str]) -> list[str]:
    block = chart.get("transformations")
    if not isinstance(block, Mapping):
        return [f"chart.{key}.transformations: required"]

    problems: list[str] = []
    if not isinstance(block.get("unplaced"), list):
        problems.append(
            f"chart.{key}.transformations.unplaced: expected a list; a gap this release does not "
            "place is recorded, never dropped"
        )
    placed = block.get("placed")
    if not isinstance(placed, list):
        return [*problems, f"chart.{key}.transformations.placed: expected a list"]

    for index, item in enumerate(_objects(placed)):
        star = str(item.get("star") or "")
        if star not in stars_by_branch:
            problems.append(
                f"chart.{key}.transformations.placed[{index}]: names {star!r}, which sits in no palace"
            )
            continue
        if str(item.get("palace") or "") != stars_by_branch[star]:
            problems.append(
                f"chart.{key}.transformations.placed[{index}]: puts {star} in "
                f"{item.get('palace')!r}, and it is placed in {stars_by_branch[star]!r}"
            )
    return problems


def _decade_defects(chart: Mapping[str, Any], key: str) -> list[str]:
    decades = chart.get("decades")
    if not isinstance(decades, list) or len(decades) != PALACE_COUNT:
        found = len(decades) if isinstance(decades, list) else 0
        return [f"chart.{key}.decades: twelve decade ranges, found {found}"]

    problems: list[str] = []
    entries = _objects(decades)
    if len(entries) != PALACE_COUNT:
        return [f"chart.{key}.decades: every range is an object"]
    if [entry.get("order") for entry in entries] != list(range(1, PALACE_COUNT + 1)):
        problems.append(f"chart.{key}.decades: orders run 1 through 12")
    for index, entry in enumerate(entries):
        start, end = _number(entry.get("start_age")), _number(entry.get("end_age"))
        if start is None or end is None:
            problems.append(f"chart.{key}.decades[{index}]: start_age and end_age are required")
        elif end - start != 9:
            problems.append(f"chart.{key}.decades[{index}]: {start:g}-{end:g} is not a ten-year window")

    # One direction, always. Decades run forward or backward by the year's
    # polarity and the subject's gender, and a list that changes its mind halfway
    # is not a chart either rule produced.
    steps = set()
    for earlier, later in pairwise(entries):
        left, right = _number(earlier.get("palace_index")), _number(later.get("palace_index"))
        if left is None or right is None:
            problems.append(f"chart.{key}.decades: every range names the palace it occupies")
            return problems
        steps.add(int(right - left) % PALACE_COUNT)
    if steps not in ({1}, {PALACE_COUNT - 1}):
        problems.append(f"chart.{key}.decades: the twelve ranges do not run in one direction")
    return problems


def _objects(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _get(mapping: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(mapping, Mapping):
            return None
        mapping = mapping.get(key)
    return mapping


_SHAPE_CHECKS = {
    CHART: _chart_defects,
    COMPATIBILITY: _compatibility_defects,
    ZIWEI: _ziwei_defects,
}
