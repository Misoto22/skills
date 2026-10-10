"""lists_changes: the diff between plan and account, and an apply order GitHub accepts."""

from __future__ import annotations

import unittest

from star_lists_skill import fakes
from star_lists_skill.fakes import FakeGitHub, account

lists_changes = fakes.load("lists_changes")
lists_plan = fakes.load("lists_plan")


def base_plan() -> dict:
    plan = lists_plan.snapshot_to_plan(account())
    plan["assignments"]["c/notes"] = ["tools"]
    return plan


def run(plan: dict, github: FakeGitHub | None = None) -> FakeGitHub:
    github = github or FakeGitHub()
    snapshot = github.snapshot()
    changes = lists_changes.compute(plan, snapshot)
    lists_changes.apply(github, plan, snapshot, changes, log=lambda _: None)
    return github


class ComputeTests(unittest.TestCase):
    def test_export_of_the_account_changes_nothing(self) -> None:
        plan = lists_plan.snapshot_to_plan(account())
        changes = lists_changes.compute(plan, account())
        self.assertTrue(changes.empty())
        self.assertIn("No changes", lists_changes.render(changes))

    def test_every_kind_of_change_is_found_and_rendered(self) -> None:
        plan = base_plan()
        plan["lists"][0].update(name="Dev Tools", description="CLI")
        plan["lists"] = [plan["lists"][0], {"key": "ai", "name": "AI", "description": "", "private": False}]
        plan["assignments"] = {"a/agent": ["ai", "tools"], "b/font": ["tools"], "c/notes": ["tools"]}
        changes = lists_changes.compute(plan, account())
        self.assertEqual([item["id"] for item in changes.deletes], ["L2"])
        self.assertEqual(changes.updates[0][1]["name"], "Dev Tools")
        self.assertEqual([item["name"] for item in changes.creates], ["AI"])
        self.assertEqual(
            changes.moves,
            [
                ("a/agent", ["Tools"], ["AI", "Dev Tools"]),
                ("b/font", ["Fonts"], ["Dev Tools"]),
                ("c/notes", [], ["Dev Tools"]),
            ],
        )
        text = lists_changes.render(changes)
        for expected in (
            "Lists: 1 to create, 1 to update, 1 to delete. Repositories: 3 to move.",
            "delete  Fonts",
            "rename to 'Dev Tools'",
            "create  AI",
            "(none) -> Dev Tools",
        ):
            self.assertIn(expected, text)


class ApplyTests(unittest.TestCase):
    def test_apply_reaches_the_plan(self) -> None:
        plan = base_plan()
        plan["lists"].append({"key": "ai", "name": "AI", "description": "Agents", "private": True})
        plan["assignments"]["a/agent"] = ["ai", "tools"]
        github = run(plan)
        after = github.snapshot()
        ai = next(item for item in after["lists"] if item["name"] == "AI")
        self.assertEqual(sorted(ai["items"]), ["a/agent"])
        self.assertTrue(ai["private"])
        self.assertEqual(
            sorted(next(i for i in after["lists"] if i["id"] == "L1")["items"]), ["a/agent", "c/notes"]
        )

    def test_deletes_run_before_a_create_reuses_the_name(self) -> None:
        plan = base_plan()
        plan["lists"] = [plan["lists"][0], {"key": "fonts-new", "name": "Fonts", "private": False}]
        plan["assignments"]["b/font"] = ["fonts-new"]
        github = run(plan)
        self.assertEqual(github.calls[0], ("delete", "L2"))

    def test_two_lists_can_swap_names(self) -> None:
        plan = base_plan()
        plan["lists"][0]["name"], plan["lists"][1]["name"] = "Fonts", "Tools"
        github = run(plan)
        names = {item["id"]: item["name"] for item in github.snapshot()["lists"]}
        self.assertEqual(names, {"L1": "Fonts", "L2": "Tools"})

    def test_backup_with_a_deleted_list_recreates_it(self) -> None:
        backup = base_plan()
        github = FakeGitHub()
        github.delete_list("L2")
        run(backup, github)
        after = github.snapshot()
        fonts = next(item for item in after["lists"] if item["name"] == "Fonts")
        self.assertEqual(fonts["items"], ["b/font"])
        self.assertNotEqual(fonts["id"], "L2")

    def test_removing_every_list_from_a_repository_sends_an_empty_set(self) -> None:
        plan = base_plan()
        plan["assignments"]["c/notes"] = []
        plan["assignments"]["b/font"] = []
        github = run(plan)
        self.assertIn(("set", "R2", ()), github.calls)


if __name__ == "__main__":
    unittest.main()
