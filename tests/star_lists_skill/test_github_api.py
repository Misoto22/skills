"""github_api: paging, retrying only throttled calls, and the gh subprocess boundary."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from star_lists_skill import fakes

github_api = fakes.load("github_api")


def page(nodes: list, cursor: str | None) -> dict:
    return {"pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}, "nodes": nodes}


def star(name: str) -> dict:
    return {
        "id": "R-" + name,
        "nameWithOwner": name,
        "description": None,
        "primaryLanguage": None,
        "isArchived": False,
        "repositoryTopics": {"nodes": [{"topic": {"name": "cli"}}]},
    }


class ScriptedRunner:
    """Answers each GraphQL call from a queue and records what was asked."""

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.bodies: list[dict] = []

    def __call__(self, body: dict) -> dict:
        self.bodies.append(body)
        return self.replies.pop(0)


class SnapshotTests(unittest.TestCase):
    def test_pages_stars_and_list_items(self) -> None:
        big_list = {
            "id": "L1",
            "name": "Tools",
            "slug": "tools",
            "description": None,
            "isPrivate": False,
            "items": page([{"nameWithOwner": "a/one"}], "i1"),
        }
        runner = ScriptedRunner(
            [
                {"data": {"viewer": {"login": "octo", "starredRepositories": page([star("a/one")], "s1")}}},
                {"data": {"viewer": {"login": "octo", "starredRepositories": page([star("b/two")], None)}}},
                {"data": {"viewer": {"lists": page([big_list], None)}}},
                {
                    "data": {
                        "node": {
                            "items": page([{"nameWithOwner": "a/one"}, {"nameWithOwner": "b/two"}], None)
                        }
                    }
                },
            ]
        )
        snapshot = github_api.GitHub(runner, sleep=lambda _: None).snapshot()
        self.assertEqual(snapshot["login"], "octo")
        self.assertEqual([repo["name"] for repo in snapshot["stars"]], ["a/one", "b/two"])
        self.assertEqual(snapshot["stars"][0]["topics"], ["cli"])
        self.assertEqual(snapshot["lists"][0]["items"], ["a/one", "b/two"])
        self.assertEqual(runner.bodies[1]["variables"]["after"], "s1")


class RetryTests(unittest.TestCase):
    def test_throttled_calls_back_off_then_succeed(self) -> None:
        sleeps: list[float] = []
        runner = ScriptedRunner(
            [
                {"errors": [{"message": "You have exceeded a secondary rate limit"}]},
                {"data": {"ok": True}},
            ]
        )
        data = github_api.GitHub(runner, sleep=sleeps.append).call("query { ok }")
        self.assertEqual(data, {"ok": True})
        self.assertEqual(sleeps, [github_api.RETRY_DELAYS[0]])

    def test_other_errors_fail_at_once(self) -> None:
        runner = ScriptedRunner([{"errors": [{"message": "Could not resolve to a node"}]}])
        with self.assertRaisesRegex(github_api.GitHubError, "Could not resolve"):
            github_api.GitHub(runner, sleep=lambda _: None).call("query { x }")

    def test_throttling_that_never_ends_gives_up(self) -> None:
        throttled = {"errors": [{"message": "was submitted too quickly"}]}
        runner = ScriptedRunner([throttled] * (len(github_api.RETRY_DELAYS) + 1))
        with self.assertRaises(github_api.GitHubError):
            github_api.GitHub(runner, sleep=lambda _: None).call("mutation { x }")


class MutationTests(unittest.TestCase):
    def test_writes_send_the_documented_variables(self) -> None:
        runner = ScriptedRunner(
            [
                {"data": {"createUserList": {"list": {"id": "L9"}}}},
                {"data": {"updateUserList": {"list": {"id": "L9"}}}},
                {"data": {"updateUserListsForItem": {"clientMutationId": None}}},
                {"data": {"deleteUserList": {"clientMutationId": None}}},
            ]
        )
        github = github_api.GitHub(runner, sleep=lambda _: None)
        self.assertEqual(github.create_list("AI", "Agents", True), "L9")
        github.update_list("L9", "AI Tools", "", False)
        github.set_item_lists("R1", ["L9"])
        github.delete_list("L9")
        variables = [body["variables"] for body in runner.bodies]
        self.assertEqual(variables[0], {"name": "AI", "description": "Agents", "private": True})
        self.assertEqual(variables[2], {"item": "R1", "lists": ["L9"]})
        self.assertEqual(variables[3], {"id": "L9"})


class GhRunnerTests(unittest.TestCase):
    def test_gh_failure_without_output_raises(self) -> None:
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="gh: not logged in")
        with (
            mock.patch.object(github_api.subprocess, "run", return_value=failed),
            self.assertRaisesRegex(github_api.GitHubError, "not logged in"),
        ):
            github_api.gh_runner({"query": "query { x }"})

    def test_graphql_errors_with_exit_code_still_decode(self) -> None:
        replied = subprocess.CompletedProcess([], 1, stdout='{"errors":[{"message":"bad"}]}', stderr="")
        with mock.patch.object(github_api.subprocess, "run", return_value=replied) as run:
            self.assertEqual(github_api.gh_runner({"query": "q"}), {"errors": [{"message": "bad"}]})
        self.assertEqual(run.call_args.args[0], ["gh", "api", "graphql", "--input", "-"])


if __name__ == "__main__":
    unittest.main()
