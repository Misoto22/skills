"""The plan file: the desired state of a GitHub account's star lists.

A plan names every list that should exist and the lists each starred repository
belongs to. An export of the live account is itself a valid plan, which is what
makes a backup restorable by applying it.
"""

from __future__ import annotations

import re

FORMAT = "github-star-lists/v1"

# GitHub documents none of these. They come from a community-maintained limits
# table (github.com/dead-claudia/github-limits), and checking them here stops a
# plan from failing halfway through an apply.
MAX_LISTS = 32
MAX_NAME_LENGTH = 32
MAX_DESCRIPTION_LENGTH = 160

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Generated text must be English. These ranges cover Han, kana, Hangul, CJK
# punctuation and fullwidth forms, which is what a non-English list name in
# this space actually contains. Latin punctuation such as "·" stays allowed.
_CJK = re.compile(
    r"[\u1100-\u11ff\u2e80-\u2fdf\u3000-\u30ff\u3100-\u31ff\u3200-\u9fff"
    r"\uac00-\ud7af\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef]"
)


class PlanError(ValueError):
    """Raised when a plan file cannot be read as a plan at all."""


def has_cjk(text: str) -> bool:
    """Return True when the text contains a CJK, kana, or Hangul character."""
    return bool(_CJK.search(text))


def slug_key(name: str) -> str:
    """Derive a stable plan key from a list name."""
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return key or "list"


def snapshot_to_plan(snapshot: dict) -> dict:
    """Express a live account snapshot as a plan that would leave it unchanged."""
    keys: dict[str, str] = {}
    lists = []
    for item in snapshot["lists"]:
        key = slug_key(item["slug"] or item["name"])
        while key in keys.values():
            key += "-x"
        keys[item["id"]] = key
        lists.append(
            {
                "key": key,
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "private": item["private"],
            }
        )
    assignments = {repo["name"]: [] for repo in snapshot["stars"]}
    for item in snapshot["lists"]:
        for repo in item["items"]:
            if repo in assignments:
                assignments[repo].append(keys[item["id"]])
    repos = {
        repo["name"]: {
            "description": repo["description"],
            "language": repo["language"],
            "topics": repo["topics"],
        }
        for repo in snapshot["stars"]
    }
    return {
        "format": FORMAT,
        "account": snapshot["login"],
        "lists": lists,
        "assignments": assignments,
        "repos": repos,
    }


def load(document: object) -> dict:
    """Check the plan's shape and return it; raise PlanError on a malformed file."""
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise PlanError(f'not a plan: expected "format": "{FORMAT}"')
    lists = document.get("lists")
    assignments = document.get("assignments")
    if not isinstance(lists, list) or not all(isinstance(item, dict) for item in lists):
        raise PlanError('"lists" must be an array of objects')
    if not isinstance(assignments, dict):
        raise PlanError('"assignments" must be an object mapping owner/repo to list keys')
    for repo, keys in assignments.items():
        if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
            raise PlanError(f'"assignments"["{repo}"] must be an array of list keys')
    return document


def _list_errors(lists: list[dict]) -> list[str]:
    errors = []
    seen_keys: set[str] = set()
    seen_names: set[str] = set()
    for index, item in enumerate(lists):
        label = f"lists[{index}]"
        key, name = item.get("key"), item.get("name")
        description = item.get("description") or ""
        if not isinstance(key, str) or not KEY_PATTERN.match(key):
            errors.append(f"{label}: key must be lowercase letters, digits and hyphens")
        elif key in seen_keys:
            errors.append(f"{label}: duplicate key {key!r}")
        seen_keys.add(str(key))
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label}: name is required")
            continue
        if name.casefold() in seen_names:
            errors.append(f"{label}: duplicate name {name!r}")
        seen_names.add(name.casefold())
        if len(name) > MAX_NAME_LENGTH:
            errors.append(f"{label}: name {name!r} is longer than {MAX_NAME_LENGTH} characters")
        if len(description) > MAX_DESCRIPTION_LENGTH:
            errors.append(f"{label}: description is longer than {MAX_DESCRIPTION_LENGTH} characters")
        if has_cjk(name) or has_cjk(description):
            errors.append(f"{label}: name and description must be English, found CJK text in {name!r}")
        if not isinstance(item.get("private", False), bool):
            errors.append(f"{label}: private must be true or false")
    if len(lists) > MAX_LISTS:
        errors.append(f"plan has {len(lists)} lists; GitHub allows {MAX_LISTS}")
    return errors


def validate(plan: dict, snapshot: dict, allow_unassigned: bool = False) -> list[str]:
    """Return every reason the plan cannot be applied to this account, empty when it can."""
    if plan.get("account") and plan["account"] != snapshot["login"]:
        return [f"plan is for {plan['account']!r} but gh is signed in as {snapshot['login']!r}"]
    errors = _list_errors(plan["lists"])
    ids = [item.get("id") for item in plan["lists"] if item.get("id")]
    if len(ids) != len(set(ids)):
        errors.append("two plan lists claim the same existing list id")
    keys = {item.get("key") for item in plan["lists"]}
    starred = {repo["name"] for repo in snapshot["stars"]}
    for repo, repo_keys in plan["assignments"].items():
        if repo not in starred:
            errors.append(f"{repo}: not starred by {snapshot['login']}")
        for key in repo_keys:
            if key not in keys:
                errors.append(f"{repo}: unknown list key {key!r}")
    if not allow_unassigned:
        missing = sorted(repo for repo in starred if not plan["assignments"].get(repo))
        errors.extend(f"{repo}: starred but in no list" for repo in missing)
    return errors
