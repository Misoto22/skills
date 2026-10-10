"""Render a plan as a self-contained HTML page for a person to review and edit.

The page needs no server and no network: the plan is embedded, every repository
can be toggled into any number of lists, and the page saves the edited plan as
a JSON file that `apply` accepts.
"""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "review.html"
PLACEHOLDER = "/*__PLAN__*/null"


def render(plan: dict) -> str:
    """Return the review page with the plan embedded."""
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise RuntimeError(f"{TEMPLATE} has lost its {PLACEHOLDER} marker")
    # "</" inside an inline script would end the script element early.
    payload = json.dumps(plan, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, payload)
