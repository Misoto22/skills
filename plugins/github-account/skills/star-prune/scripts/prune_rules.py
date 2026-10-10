"""Which starred repositories to flag, and why.

Every reason comes from a field GitHub returns for the star; nothing is looked up
elsewhere. Reasons are ordered strongest first, and only the strong ones propose
unstarring: a dormant repository is often finished, not dead.
"""

from __future__ import annotations

import re
from datetime import datetime

FORMAT = "github-star-prune/v1"

REASONS = ("disabled", "archived", "deprecated", "dormant", "old-star")
UNSTAR_REASONS = frozenset({"disabled", "archived", "deprecated"})
ACTIONS = ("unstar", "keep")

DEFAULT_DORMANT_YEARS = 2.0
DEFAULT_OLD_STAR_YEARS = 4.0

_DEPRECATED_TEXT = re.compile(
    r"\b(deprecated|unmaintained|no longer (?:maintained|supported|developed)|superseded by|moved to)\b",
    re.IGNORECASE,
)
_DEPRECATED_TOPICS = frozenset({"deprecated", "unmaintained", "abandoned", "obsolete"})


def years_since(timestamp: str, now: datetime) -> float:
    """Years from an ISO 8601 timestamp to now; 0 when the timestamp is missing."""
    if not timestamp:
        return 0.0
    then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (now - then).total_seconds() / (365.25 * 24 * 3600)


def deprecation_evidence(star: dict) -> str:
    """Return the phrase or topic that marks a repository deprecated, or an empty string."""
    match = _DEPRECATED_TEXT.search(star.get("description") or "")
    if match:
        return f"description says {match.group(0).lower()!r}"
    topics = sorted(_DEPRECATED_TOPICS.intersection(star.get("topics") or []))
    return f"topic {topics[0]!r}" if topics else ""


def reasons_for(star: dict, listed: bool, now: datetime, dormant_years: float, old_star_years: float) -> list:
    """Every reason that applies to one star, strongest first."""
    reasons = []
    if star.get("disabled"):
        reasons.append("disabled")
    if star.get("archived"):
        reasons.append("archived")
    if deprecation_evidence(star):
        reasons.append("deprecated")
    if not star.get("archived") and years_since(star.get("pushed_at", ""), now) > dormant_years:
        reasons.append("dormant")
    if not listed and years_since(star.get("starred_at", ""), now) > old_star_years:
        reasons.append("old-star")
    return reasons


def classify(
    snapshot: dict,
    now: datetime,
    dormant_years: float = DEFAULT_DORMANT_YEARS,
    old_star_years: float = DEFAULT_OLD_STAR_YEARS,
) -> list[dict]:
    """Flag the account's stars. Repositories the account owns are never flagged."""
    lists_of: dict[str, list[str]] = {}
    for item in snapshot["lists"]:
        for repo in item["items"]:
            lists_of.setdefault(repo, []).append(item["name"])
    candidates = []
    for star in snapshot["stars"]:
        if star.get("owner") == snapshot["login"]:
            continue
        lists = sorted(lists_of.get(star["name"], []))
        reasons = reasons_for(star, bool(lists), now, dormant_years, old_star_years)
        if not reasons:
            continue
        candidates.append(
            {
                "name": star["name"],
                "id": star["id"],
                "reasons": reasons,
                "evidence": deprecation_evidence(star),
                "action": "unstar" if UNSTAR_REASONS.intersection(reasons) else "keep",
                "pushed_at": star.get("pushed_at", ""),
                "starred_at": star.get("starred_at", ""),
                "lists": lists,
            }
        )
    candidates.sort(key=lambda c: (REASONS.index(c["reasons"][0]), c["name"].lower()))
    return candidates
