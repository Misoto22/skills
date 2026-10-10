"""An account with stars in every state star-prune distinguishes."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone

from star_lists_skill.fakes import ROOT

SKILL = ROOT / "plugins" / "github-account" / "skills" / "star-prune"
SCRIPTS = SKILL / "scripts"
SHARED = SKILL / "shared"
for path in (SHARED, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)  # noqa: UP017 - the scripts run on Python 3.9


def load(name: str):
    """Import one of the skill's scripts by module name."""
    return importlib.import_module(name)


def star(name: str, **fields: object) -> dict:
    base = {
        "id": "R-" + name,
        "name": name,
        "owner": name.split("/")[0],
        "description": "",
        "language": "",
        "topics": [],
        "archived": False,
        "disabled": False,
        "pushed_at": "2026-09-01T00:00:00Z",
        "starred_at": "2026-01-01T00:00:00Z",
    }
    base.update(fields)
    return base


def account() -> dict:
    return {
        "login": "octo",
        "stars": [
            star("live/tool"),
            star("old/archived", archived=True, pushed_at="2020-01-01T00:00:00Z"),
            star("gone/disabled", disabled=True),
            star("dep/text", description="DEPRECATED: use new/thing instead"),
            star("dep/topic", topics=["cli", "unmaintained"]),
            star("quiet/lib", pushed_at="2023-06-01T00:00:00Z"),
            star("forgot/it", starred_at="2020-01-01T00:00:00Z"),
            star("octo/mine", archived=True),
        ],
        "lists": [
            {
                "id": "L1",
                "name": "Tools",
                "slug": "tools",
                "description": "",
                "private": False,
                "items": ["live/tool", "old/archived", "quiet/lib"],
            },
            {
                "id": "L2",
                "name": "Old",
                "slug": "old",
                "description": "",
                "private": False,
                "items": ["old/archived"],
            },
        ],
    }
