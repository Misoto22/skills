"""GitHub's stars and star-list GraphQL API, reached through the gh CLI.

Shared by the github-account skills. Lists have no REST endpoint; only GraphQL
exposes them. Going through
`gh api graphql` means gh owns authentication, so no token passes through this
code, its arguments, or its output.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable

Runner = Callable[[dict], dict]

RETRY_DELAYS = (2, 5, 15, 30, 60)
_THROTTLED = ("secondary rate limit", "submitted too quickly", "abuse detection", "rate limit exceeded")

STARS_QUERY = """query($after: String) { viewer { login starredRepositories(first: 100, after: $after) {
  pageInfo { hasNextPage endCursor }
  edges { starredAt node { id nameWithOwner description primaryLanguage { name } owner { login }
    isArchived isDisabled pushedAt repositoryTopics(first: 10) { nodes { topic { name } } } } } } } }"""

LISTS_QUERY = """query($after: String) { viewer { lists(first: 32, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { id name slug description isPrivate
    items(first: 100) { pageInfo { hasNextPage endCursor }
      nodes { ... on Repository { nameWithOwner } } } } } } }"""

ITEMS_QUERY = """query($id: ID!, $after: String) { node(id: $id) { ... on UserList {
  items(first: 100, after: $after) { pageInfo { hasNextPage endCursor }
    nodes { ... on Repository { nameWithOwner } } } } } }"""

CREATE = """mutation($name: String!, $description: String, $private: Boolean) {
  createUserList(input: {name: $name, description: $description, isPrivate: $private}) { list { id } } }"""

UPDATE = """mutation($id: ID!, $name: String, $description: String, $private: Boolean) {
  updateUserList(input: {listId: $id, name: $name, description: $description, isPrivate: $private}) {
    list { id } } }"""

DELETE = """mutation($id: ID!) { deleteUserList(input: {listId: $id}) { clientMutationId } }"""

ADD_STAR = """mutation($id: ID!) { addStar(input: {starrableId: $id}) { clientMutationId } }"""

REMOVE_STAR = """mutation($id: ID!) { removeStar(input: {starrableId: $id}) { clientMutationId } }"""

SET_ITEM_LISTS = """mutation($item: ID!, $lists: [ID!]!) {
  updateUserListsForItem(input: {itemId: $item, listIds: $lists}) { clientMutationId } }"""


def _star(edge: dict) -> dict:
    node = edge["node"]
    return {
        "id": node["id"],
        "name": node["nameWithOwner"],
        "owner": node["owner"]["login"],
        "description": node["description"] or "",
        "language": (node["primaryLanguage"] or {}).get("name", ""),
        "topics": [entry["topic"]["name"] for entry in node["repositoryTopics"]["nodes"]],
        "archived": node["isArchived"],
        "disabled": node["isDisabled"],
        "pushed_at": node["pushedAt"] or "",
        "starred_at": edge["starredAt"],
    }


class GitHubError(RuntimeError):
    """A GraphQL call failed for a reason retrying will not fix."""


def gh_runner(body: dict) -> dict:
    """Send one GraphQL request through `gh api graphql` and return the decoded reply."""
    result = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 and not result.stdout.strip():
        raise GitHubError(result.stderr.strip() or f"gh exited with {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise GitHubError(f"gh returned something that is not JSON: {result.stdout[:200]!r}") from error


class GitHub:
    """Typed calls over a GraphQL runner, retrying only when GitHub says to slow down."""

    def __init__(self, runner: Runner = gh_runner, sleep: Callable[[float], None] = time.sleep):
        self._runner = runner
        self._sleep = sleep

    def call(self, query: str, **variables: object) -> dict:
        """Run one query, retrying throttled calls, and return its data."""
        for delay in (*RETRY_DELAYS, None):
            reply = self._runner({"query": query, "variables": variables})
            errors = reply.get("errors") or []
            if not errors:
                return reply["data"]
            message = "; ".join(str(error.get("message", error)) for error in errors)
            if delay is None or not any(marker in message.lower() for marker in _THROTTLED):
                raise GitHubError(message)
            self._sleep(delay)
        raise AssertionError("unreachable")

    def _pages(
        self, query: str, pick: Callable[[dict], dict], key: str = "nodes", **variables: object
    ) -> list[dict]:
        nodes: list[dict] = []
        after = None
        while True:
            connection = pick(self.call(query, after=after, **variables))
            nodes.extend(node for node in connection[key] if node)
            if not connection["pageInfo"]["hasNextPage"]:
                return nodes
            after = connection["pageInfo"]["endCursor"]

    def snapshot(self) -> dict:
        """Read the signed-in account's stars, lists, and list memberships.

        A star carries id, name, owner, description, language, topics, archived,
        disabled, pushed_at and starred_at; a list carries id, name, slug,
        description, private and the names of its items.
        """
        seen: dict[str, str] = {}

        def stars_page(data: dict) -> dict:
            seen["login"] = data["viewer"]["login"]
            return data["viewer"]["starredRepositories"]

        stars = [_star(edge) for edge in self._pages(STARS_QUERY, stars_page, key="edges")]
        lists = []
        for node in self._pages(LISTS_QUERY, lambda data: data["viewer"]["lists"]):
            items = [item for item in node["items"]["nodes"] if item]
            if node["items"]["pageInfo"]["hasNextPage"]:
                # Only a list past its first hundred items costs extra calls.
                items = self._pages(ITEMS_QUERY, lambda data: data["node"]["items"], id=node["id"])
            lists.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "slug": node["slug"],
                    "description": node["description"] or "",
                    "private": node["isPrivate"],
                    "items": [item["nameWithOwner"] for item in items if "nameWithOwner" in item],
                }
            )
        return {"login": seen["login"], "stars": stars, "lists": lists}

    def create_list(self, name: str, description: str, private: bool) -> str:
        """Create a list and return its id."""
        data = self.call(CREATE, name=name, description=description, private=private)
        return data["createUserList"]["list"]["id"]

    def update_list(self, list_id: str, name: str, description: str, private: bool) -> None:
        """Rename a list or change its description or visibility."""
        self.call(UPDATE, id=list_id, name=name, description=description, private=private)

    def delete_list(self, list_id: str) -> None:
        """Delete a list. Its repositories stay starred."""
        self.call(DELETE, id=list_id)

    def add_star(self, repo_id: str) -> None:
        """Star a repository."""
        self.call(ADD_STAR, id=repo_id)

    def remove_star(self, repo_id: str) -> None:
        """Unstar a repository. Its list memberships go with the star."""
        self.call(REMOVE_STAR, id=repo_id)

    def set_item_lists(self, repo_id: str, list_ids: list[str]) -> None:
        """Replace the full set of lists one starred repository belongs to."""
        self.call(SET_ITEM_LISTS, item=repo_id, lists=list_ids)
