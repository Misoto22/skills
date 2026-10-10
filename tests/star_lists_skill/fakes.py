"""An in-memory GitHub account that behaves like the list API where it matters."""

from __future__ import annotations

import copy
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "github-account" / "skills" / "star-lists"
SCRIPTS = SKILL / "scripts"
SHARED = SKILL / "shared"
for path in (SHARED, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load(name: str):
    """Import one of the skill's scripts by module name."""
    return importlib.import_module(name)


def account() -> dict:
    """A small account: three stars, two lists, one repository in no list."""
    return {
        "login": "octo",
        "stars": [
            {
                "id": "R1",
                "name": "a/agent",
                "description": "An agent",
                "language": "Python",
                "topics": [],
                "archived": False,
            },
            {
                "id": "R2",
                "name": "b/font",
                "description": "A font",
                "language": "",
                "topics": ["font"],
                "archived": False,
            },
            {
                "id": "R3",
                "name": "c/notes",
                "description": "",
                "language": "Go",
                "topics": [],
                "archived": False,
            },
        ],
        "lists": [
            {
                "id": "L1",
                "name": "Tools",
                "slug": "tools",
                "description": "",
                "private": False,
                "items": ["a/agent"],
            },
            {
                "id": "L2",
                "name": "Fonts",
                "slug": "fonts",
                "description": "",
                "private": True,
                "items": ["b/font"],
            },
        ],
    }


class FakeGitHub:
    """Applies writes to a snapshot and refuses two lists with one name, as GitHub does."""

    def __init__(self, state: dict | None = None):
        self.state = copy.deepcopy(state or account())
        self.calls: list[tuple] = []
        self.unstarred: dict[str, dict] = {}
        self._next = 100

    def snapshot(self) -> dict:
        return copy.deepcopy(self.state)

    def _by_id(self, list_id: str) -> dict:
        return next(item for item in self.state["lists"] if item["id"] == list_id)

    def _claim(self, name: str, list_id: str | None) -> None:
        for item in self.state["lists"]:
            if item["name"].casefold() == name.casefold() and item["id"] != list_id:
                raise AssertionError(f"name {name!r} already taken by {item['id']}")

    def create_list(self, name: str, description: str, private: bool) -> str:
        self.calls.append(("create", name))
        self._claim(name, None)
        self._next += 1
        list_id = f"L{self._next}"
        self.state["lists"].append(
            {
                "id": list_id,
                "name": name,
                "slug": name.lower(),
                "description": description,
                "private": private,
                "items": [],
            }
        )
        return list_id

    def update_list(self, list_id: str, name: str, description: str, private: bool) -> None:
        self.calls.append(("update", list_id, name))
        self._claim(name, list_id)
        self._by_id(list_id).update(name=name, description=description, private=private)

    def delete_list(self, list_id: str) -> None:
        self.calls.append(("delete", list_id))
        self.state["lists"] = [item for item in self.state["lists"] if item["id"] != list_id]

    def remove_star(self, repo_id: str) -> None:
        self.calls.append(("unstar", repo_id))
        star = next(star for star in self.state["stars"] if star["id"] == repo_id)
        self.unstarred[repo_id] = star
        self.state["stars"].remove(star)
        for item in self.state["lists"]:
            if star["name"] in item["items"]:
                item["items"].remove(star["name"])

    def add_star(self, repo_id: str) -> None:
        self.calls.append(("star", repo_id))
        if not any(star["id"] == repo_id for star in self.state["stars"]):
            self.state["stars"].append(self.unstarred.pop(repo_id))

    def set_item_lists(self, repo_id: str, list_ids: list[str]) -> None:
        self.calls.append(("set", repo_id, tuple(list_ids)))
        repo = next(star["name"] for star in self.state["stars"] if star["id"] == repo_id)
        for item in self.state["lists"]:
            if repo in item["items"]:
                item["items"].remove(repo)
            if item["id"] in list_ids:
                item["items"].append(repo)
