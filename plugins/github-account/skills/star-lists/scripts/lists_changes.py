"""The difference between a plan and the live account, and the order to apply it in.

Order matters. Deleting first frees the names a rename may want; renames that
swap names go through temporary names; creates come after renames for the same
reason; memberships come last because they need the ids of created lists.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Changes:
    """Every write an apply would make, grouped by kind."""

    deletes: list[dict] = field(default_factory=list)
    updates: list[tuple[dict, dict]] = field(default_factory=list)
    creates: list[dict] = field(default_factory=list)
    moves: list[tuple[str, list[str], list[str]]] = field(default_factory=list)

    def empty(self) -> bool:
        """Return True when the plan already matches the account."""
        return not (self.deletes or self.updates or self.creates or self.moves)


def _differs(live: dict, planned: dict) -> bool:
    return (
        live["name"] != planned["name"]
        or live["description"] != (planned.get("description") or "")
        or live["private"] != bool(planned.get("private", False))
    )


def compute(plan: dict, snapshot: dict) -> Changes:
    """Work out the writes that turn the live account into the plan."""
    changes = Changes()
    live_by_id = {item["id"]: item for item in snapshot["lists"]}
    kept = {item["id"] for item in plan["lists"] if item.get("id")}
    changes.deletes = [item for item in snapshot["lists"] if item["id"] not in kept]
    for planned in plan["lists"]:
        live = live_by_id.get(planned.get("id") or "")
        if live is None:
            changes.creates.append(planned)
        elif _differs(live, planned):
            changes.updates.append((live, planned))
    name_by_key = {item["key"]: item["name"] for item in plan["lists"]}
    current: dict[str, list[str]] = {repo["name"]: [] for repo in snapshot["stars"]}
    for item in snapshot["lists"]:
        for repo in item["items"]:
            current.setdefault(repo, []).append(item["name"])
    for repo in sorted(current):
        target = sorted(name_by_key[key] for key in plan["assignments"].get(repo, []))
        if sorted(current[repo]) != target:
            changes.moves.append((repo, sorted(current[repo]), target))
    return changes


def render(changes: Changes) -> str:
    """Describe the changes in plain English, one line per write."""
    if changes.empty():
        return "No changes: the account already matches the plan."
    lines = [
        f"Lists: {len(changes.creates)} to create, {len(changes.updates)} to update, "
        f"{len(changes.deletes)} to delete. Repositories: {len(changes.moves)} to move."
    ]
    for item in changes.deletes:
        count = len(item["items"])
        noun = "repository stays" if count == 1 else "repositories stay"
        lines.append(f"  delete  {item['name']} ({count} {noun} starred)")
    for live, planned in changes.updates:
        what = [f"rename to {planned['name']!r}"] if live["name"] != planned["name"] else []
        if live["description"] != (planned.get("description") or ""):
            what.append("new description")
        if live["private"] != bool(planned.get("private", False)):
            what.append("make private" if planned.get("private") else "make public")
        lines.append(f"  update  {live['name']}: {', '.join(what)}")
    for item in changes.creates:
        lines.append(
            f"  create  {item['name']}"
            + (" (recreated: its old id no longer exists)" if item.get("id") else "")
        )
    for repo, before, after in changes.moves:
        lines.append(f"  move    {repo}: {', '.join(before) or '(none)'} -> {', '.join(after) or '(none)'}")
    return "\n".join(lines)


def _rename_all(github, updates: list[tuple[dict, dict]], log: Callable[[str], None]) -> None:
    final_names = {planned["name"].casefold() for _, planned in updates}
    renamed_ids = {live["id"] for live, planned in updates if live["name"] != planned["name"]}
    swapping = any(
        live["name"].casefold() in final_names and live["id"] in renamed_ids for live, _ in updates
    )
    if swapping:
        # Two lists trading names would collide mid-way, so park every renamed
        # list on a unique temporary name first.
        for live, planned in updates:
            if live["id"] in renamed_ids:
                temporary = f"tmp {planned['key']}"[:32]
                github.update_list(live["id"], temporary, live["description"], live["private"])
    for live, planned in updates:
        github.update_list(
            live["id"], planned["name"], planned.get("description") or "", bool(planned.get("private", False))
        )
        log(f"updated {planned['name']}")


def apply(github, plan: dict, snapshot: dict, changes: Changes, log: Callable[[str], None] = print) -> None:
    """Make every write in the order that keeps names unique and ids resolvable."""
    for item in changes.deletes:
        github.delete_list(item["id"])
        log(f"deleted {item['name']}")
    _rename_all(github, changes.updates, log)
    ids = {item["key"]: item["id"] for item in plan["lists"] if item.get("id")}
    for item in changes.creates:
        ids[item["key"]] = github.create_list(
            item["name"], item.get("description") or "", bool(item.get("private", False))
        )
        log(f"created {item['name']}")
    repo_ids = {repo["name"]: repo["id"] for repo in snapshot["stars"]}
    for repo, _, _ in changes.moves:
        github.set_item_lists(repo_ids[repo], [ids[key] for key in plan["assignments"].get(repo, [])])
    if changes.moves:
        log(f"moved {len(changes.moves)} repositories")
