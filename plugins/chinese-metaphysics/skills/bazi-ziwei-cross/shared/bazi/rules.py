"""Load the externalized rule tables, each fact from the one file that declares it.

The chart rules own the cycle, the five elements and the stem and branch
relations. The scoring and compatibility rules own only their weights, and borrow
the rest here, so a lineage edit to an element or a clash is made once and every
model that reads it moves together. Each file keeps its own `model_id`: a model is
still named by the file that holds its weights.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_ROOT = Path(__file__).resolve().parents[1] / "rules"
CHART_RULES = "chart-v1.json"
SCORING_RULES = "scoring-v1.json"
COMPATIBILITY_RULES = "compatibility-v1.json"
ELEMENT_TABLES = ("elements", "stem_elements", "element_produces", "element_controls")


@lru_cache(maxsize=8)
def load_rules(filename: str) -> dict[str, Any]:
    """Return one rules file exactly as written, parsed once per process."""

    return json.loads((RULES_ROOT / filename).read_text(encoding="utf-8"))


def element_tables() -> dict[str, Any]:
    """Return the five-element tables every model reads, from the chart rules."""

    chart = load_rules(CHART_RULES)
    return {key: chart[key] for key in ELEMENT_TABLES}


def scoring_rules() -> dict[str, Any]:
    """Return the scoring weights joined with the element tables they apply to."""

    return element_tables() | load_rules(SCORING_RULES)
