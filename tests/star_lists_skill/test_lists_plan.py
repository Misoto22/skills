"""lists_plan: what makes a plan applicable, and the English-only rule for generated text."""

from __future__ import annotations

import unittest

from star_lists_skill import fakes
from star_lists_skill.fakes import account

lists_plan = fakes.load("lists_plan")


def plan_from(state: dict) -> dict:
    plan = lists_plan.snapshot_to_plan(state)
    plan["assignments"]["c/notes"] = ["tools"]
    return plan


class SnapshotToPlanTests(unittest.TestCase):
    def test_export_is_a_plan_that_round_trips(self) -> None:
        plan = lists_plan.snapshot_to_plan(account())
        self.assertEqual(plan["format"], lists_plan.FORMAT)
        self.assertEqual([item["key"] for item in plan["lists"]], ["tools", "fonts"])
        self.assertEqual(plan["assignments"], {"a/agent": ["tools"], "b/font": ["fonts"], "c/notes": []})
        self.assertEqual(plan["repos"]["b/font"]["topics"], ["font"])
        self.assertIs(lists_plan.load(plan), plan)

    def test_keys_stay_unique_when_slugs_collide(self) -> None:
        state = account()
        state["lists"][1]["slug"] = "tools"
        keys = [item["key"] for item in lists_plan.snapshot_to_plan(state)["lists"]]
        self.assertEqual(len(set(keys)), 2)


class ValidateTests(unittest.TestCase):
    def test_a_complete_plan_has_no_errors(self) -> None:
        self.assertEqual(lists_plan.validate(plan_from(account()), account()), [])

    def test_unassigned_repository_fails_unless_allowed(self) -> None:
        plan = lists_plan.snapshot_to_plan(account())
        self.assertEqual(lists_plan.validate(plan, account()), ["c/notes: starred but in no list"])
        self.assertEqual(lists_plan.validate(plan, account(), allow_unassigned=True), [])

    def test_unknown_repository_and_key_are_reported(self) -> None:
        plan = plan_from(account())
        plan["assignments"]["z/unstarred"] = ["tools"]
        plan["assignments"]["a/agent"] = ["nope"]
        errors = lists_plan.validate(plan, account())
        self.assertIn("z/unstarred: not starred by octo", errors)
        self.assertIn("a/agent: unknown list key 'nope'", errors)

    def test_cjk_names_and_descriptions_are_rejected(self) -> None:
        for field, value in (
            ("name", chr(0x5DE5) + chr(0x5177)),
            ("description", "AI " + chr(0x30C4)),
            ("name", chr(0xB3C4)),
        ):
            plan = plan_from(account())
            plan["lists"][0][field] = value
            errors = lists_plan.validate(plan, account())
            self.assertTrue(any("must be English" in error for error in errors), (field, value, errors))

    def test_latin_punctuation_stays_allowed(self) -> None:
        plan = plan_from(account())
        plan["lists"][0]["name"] = "AI · Agents & Apps"
        self.assertEqual(lists_plan.validate(plan, account()), [])

    def test_github_limits_are_enforced(self) -> None:
        plan = plan_from(account())
        plan["lists"][0]["name"] = "x" * (lists_plan.MAX_NAME_LENGTH + 1)
        plan["lists"][1]["description"] = "y" * (lists_plan.MAX_DESCRIPTION_LENGTH + 1)
        plan["lists"] += [{"key": f"k{n}", "name": f"List {n}"} for n in range(lists_plan.MAX_LISTS)]
        errors = " | ".join(lists_plan.validate(plan, account()))
        self.assertIn("longer than 32 characters", errors)
        self.assertIn("description is longer than 160", errors)
        self.assertIn("GitHub allows 32", errors)

    def test_duplicate_names_keys_and_ids(self) -> None:
        plan = plan_from(account())
        plan["lists"][1].update(name="tools", key="tools", id="L1")
        errors = " | ".join(lists_plan.validate(plan, account()))
        self.assertIn("duplicate key", errors)
        self.assertIn("duplicate name", errors)
        self.assertIn("same existing list id", errors)

    def test_plan_for_another_account_is_refused(self) -> None:
        plan = plan_from(account())
        plan["account"] = "someone-else"
        self.assertIn("gh is signed in as 'octo'", lists_plan.validate(plan, account())[0])

    def test_malformed_documents_raise(self) -> None:
        for document in (
            [],
            {"format": "other"},
            {"format": lists_plan.FORMAT, "lists": {}, "assignments": {}},
        ):
            with self.assertRaises(lists_plan.PlanError):
                lists_plan.load(document)

    def test_has_cjk(self) -> None:
        self.assertTrue(lists_plan.has_cjk("Tools " + chr(0xFF5C) + " Dev"))
        self.assertFalse(lists_plan.has_cjk("Tools · Dev — 2026"))


if __name__ == "__main__":
    unittest.main()
