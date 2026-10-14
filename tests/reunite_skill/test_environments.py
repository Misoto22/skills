"""Every account must hold the same environments, and a deleted one must never come back."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import environments
import environments_sync
import manifest

from tests.reunite_skill.test_merge import merge

A, B, C = "account-a", "account-b", "account-c"
NOW = 5_000_000


def preset(pid: str, name: str | None = None, created: int = 1_000, used: int = 1_000, **extra) -> dict:
    return {
        "id": pid,
        "name": name or pid.upper(),
        "target": {"kind": "local", "cwd": f"/work/{pid}"},
        "createdAt": created,
        "lastUsedAt": used,
        **extra,
    }


def doc(**accounts: dict) -> dict:
    return {"byAccount": {account.replace("_", "-"): entry for account, entry in accounts.items()}}


def ids(document: dict, account: str) -> list[str]:
    entry = document["byAccount"].get(account)
    return [p["id"] for p in entry["presets"]] if entry else []


class PlanTests(unittest.TestCase):
    def plan(self, document: dict, targets=(A, B, C), baseline=None, now: int = NOW):
        return environments.plan_environments(copy.deepcopy(document), list(targets), baseline, now)

    def test_every_target_receives_the_union_in_the_lead_accounts_order(self) -> None:
        source = doc(
            account_a={"presets": [preset("p2", used=9_000), preset("p1")], "seededFromDraft": True},
            account_c={"presets": [preset("p3")]},
        )

        plan = self.plan(source)

        for account in (A, B, C):
            self.assertEqual(ids(plan.document, account), ["p2", "p1", "p3"], account)
        counts = {c.account: (c.added, c.updated, c.removed, c.created) for c in plan.changes}
        self.assertEqual(counts, {A: (1, 0, 0, False), B: (3, 0, 0, True), C: (2, 0, 0, False)})

    def test_the_most_recently_used_copy_of_a_preset_wins_then_the_newest_created(self) -> None:
        source = doc(
            account_a={"presets": [preset("p1", name="old", used=1_000)]},
            account_b={"presets": [preset("p1", name="new", used=2_000)]},
            account_c={"presets": [preset("p1", name="recreated", used=2_000, created=3_000)]},
        )

        plan = self.plan(source)

        for account in (A, B, C):
            self.assertEqual(plan.document["byAccount"][account]["presets"][0]["name"], "recreated")

    def test_builtins_and_draft_seeding_are_kept_and_only_filled_in_when_absent(self) -> None:
        source = doc(
            account_a={"presets": [preset("p1", used=9_000)], "builtIns": {"x": 1}, "seededFromDraft": True},
            account_b={"presets": [], "builtIns": {"own": 2}},
        )

        plan = self.plan(source)

        self.assertEqual(plan.document["byAccount"][B]["builtIns"], {"own": 2})
        self.assertTrue(plan.document["byAccount"][B]["seededFromDraft"])
        self.assertEqual(
            plan.document["byAccount"][C],
            {"presets": [preset("p1", used=9_000)], "builtIns": {"x": 1}, "seededFromDraft": True},
        )

    def test_a_preset_an_account_dropped_since_the_baseline_is_removed_everywhere(self) -> None:
        baseline = environments.EnvBaseline(held={A: ["p1", "p2"], B: ["p1", "p2"]}, deleted={})
        source = doc(
            account_a={"presets": [preset("p1")]},
            account_b={"presets": [preset("p1"), preset("p2", used=9_000)]},
        )

        plan = self.plan(source, (A, B), baseline)

        self.assertEqual(ids(plan.document, B), ["p1"])
        self.assertEqual(plan.newly_deleted, {"p2"})
        self.assertEqual(plan.baseline.deleted, {"p2": NOW})
        self.assertEqual([(c.account, c.removed) for c in plan.changes], [(B, 1)])

    def test_a_deleted_preset_is_never_copied_back_from_an_account_that_still_has_it(self) -> None:
        baseline = environments.EnvBaseline(held={A: ["p1"], B: ["p1"]}, deleted={"p2": NOW})
        source = doc(
            account_a={"presets": [preset("p1")]},
            account_b={"presets": [preset("p1")]},
            account_c={"presets": [preset("p2", created=NOW - 1, used=NOW + 10)]},
        )

        plan = self.plan(source, (A, B, C), baseline, now=NOW + 100)

        for account in (A, B, C):
            self.assertEqual(ids(plan.document, account), ["p1"], account)
        self.assertEqual(plan.baseline.deleted, {"p2": NOW})

    def test_a_preset_recreated_after_its_deletion_is_live_again(self) -> None:
        baseline = environments.EnvBaseline(held={A: ["p1"], B: ["p1"]}, deleted={"p2": NOW})
        source = doc(
            account_a={"presets": [preset("p1"), preset("p2", created=NOW + 50, used=NOW + 50)]},
            account_b={"presets": [preset("p1")]},
        )

        plan = self.plan(source, (A, B), baseline, now=NOW + 100)

        self.assertEqual(ids(plan.document, B), ["p1", "p2"])
        self.assertEqual(plan.baseline.deleted, {})

    def test_an_account_emptied_since_the_baseline_is_frozen_not_read_as_deletions(self) -> None:
        """An app reset or a corrupt-file recovery empties an account; that deletes nothing."""
        baseline = environments.EnvBaseline(held={A: ["p1", "p2"], B: ["p1", "p2"]}, deleted={})
        source = doc(account_a={"presets": []}, account_b={"presets": [preset("p1"), preset("p2")]})

        plan = self.plan(source, (A, B, C), baseline)

        self.assertEqual(plan.frozen, [A])
        self.assertEqual(ids(plan.document, A), [])
        self.assertEqual(ids(plan.document, C), ["p1", "p2"])
        self.assertEqual(plan.newly_deleted, set())
        self.assertEqual(plan.baseline.held[A], ["p1", "p2"])

    def test_an_account_missing_from_the_file_altogether_after_holding_presets_is_frozen(self) -> None:
        baseline = environments.EnvBaseline(held={A: ["p1"], B: ["p1"]}, deleted={})
        source = doc(account_b={"presets": [preset("p1")]})

        plan = self.plan(source, (A, B), baseline)

        self.assertEqual(plan.frozen, [A])
        self.assertNotIn(A, plan.document["byAccount"])
        self.assertFalse(plan.changed)

    def test_planning_on_its_own_result_changes_nothing(self) -> None:
        source = doc(
            account_a={"presets": [preset("p1"), preset("p2")]}, account_c={"presets": [preset("p3")]}
        )
        first = self.plan(source)

        second = self.plan(first.document, baseline=first.baseline, now=NOW + 1)

        self.assertFalse(second.changed)
        self.assertEqual(second.document, first.document)
        self.assertEqual(second.changes, [])

    def test_non_target_accounts_are_left_alone(self) -> None:
        source = doc(account_a={"presets": [preset("p1")]}, account_b={"presets": [preset("p2")]})

        plan = self.plan(source, (A,))

        self.assertEqual(ids(plan.document, A), ["p1", "p2"])
        self.assertEqual(ids(plan.document, B), ["p2"])

    def test_more_presets_than_the_app_accepts_is_refused(self) -> None:
        many = [preset(f"p{i}") for i in range(environments.MAX_PRESETS + 1)]
        with self.assertRaises(environments.EnvironmentsError):
            self.plan(doc(account_a={"presets": many}))

    def test_a_malformed_document_is_refused(self) -> None:
        for bad in ({}, {"byAccount": []}, {"byAccount": {A: {"presets": [{"name": "no id"}]}}}):
            with self.subTest(bad=bad), self.assertRaises(environments.EnvironmentsError):
                self.plan(bad)


class EnvironmentRunTests(unittest.TestCase):
    """Drive merge.main() with a presets file beside a temporary session index."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "sessions"
        self.app = self.home / "app"
        self.app.mkdir()
        for account in (A, B, C):
            (self.root / account / "org").mkdir(parents=True)
        (self.home / ".claude" / "projects").mkdir(parents=True)
        env = {
            "HOME": str(self.home),
            merge.SESSIONS_ROOT_ENV: str(self.root),
            environments_sync.APP_DIR_ENV: str(self.app),
        }
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(merge.CONFIG_DIR_ENV, None)
        self.file = self.app / environments_sync.PRESETS_NAME
        self.write(
            doc(account_a={"presets": [preset("p1", used=2_000), preset("p2")], "seededFromDraft": True})
        )
        os.chmod(self.file, 0o600)
        self.original = self.file.read_bytes()

    def write(self, document: dict) -> None:
        self.file.write_text(json.dumps(document, indent="\t"))

    def document(self) -> dict:
        return json.loads(self.file.read_text())

    def run_merge(self, *flags: str, code: int = 0) -> str:
        out = io.StringIO()
        with patch.object(sys, "argv", ["merge.py", *flags]), contextlib.redirect_stdout(out):
            self.assertEqual(merge.main(), code, out.getvalue())
        return out.getvalue()

    def test_report_only_counts_and_writes_nothing(self) -> None:
        report = self.run_merge()

        self.assertIn("environments: 4 to add, 0 to update, 0 removed", report)
        self.assertEqual(self.file.read_bytes(), self.original)
        self.assertFalse((self.root / environments_sync.BASELINE_NAME).exists())

    def test_apply_aligns_every_account_atomically_and_records_the_original(self) -> None:
        with patch.object(os, "replace", wraps=os.replace) as replace:
            report = self.run_merge("--apply")

        self.assertIn("Environments aligned: 2 presets in 3 account(s)", report)
        document = self.document()
        for account in (A, B, C):
            self.assertEqual(ids(document, account), ["p1", "p2"], account)
        self.assertTrue(document["byAccount"][B]["seededFromDraft"])
        self.assertTrue(any(Path(call.args[1]) == self.file for call in replace.call_args_list))
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.file.read_text().startswith('{\n\t"byAccount": {'))
        self.assertEqual([p.name for p in self.app.iterdir()], [environments_sync.PRESETS_NAME])
        records = json.loads((self.root / merge.MANIFEST_NAME).read_text())[manifest.ENVIRONMENTS_KEY]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["file"], str(self.file.resolve()))

    def test_a_second_apply_writes_nothing(self) -> None:
        self.run_merge("--apply")
        written = self.file.read_bytes()
        stamp = self.file.stat().st_mtime_ns
        baseline = (self.root / environments_sync.BASELINE_NAME).stat().st_mtime_ns

        report = self.run_merge("--apply")

        self.assertIn("environments: 0 to add, 0 to update, 0 removed", report)
        self.assertEqual(self.file.read_bytes(), written)
        self.assertEqual(self.file.stat().st_mtime_ns, stamp)
        self.assertEqual((self.root / environments_sync.BASELINE_NAME).stat().st_mtime_ns, baseline)

    def test_a_deletion_in_one_account_reaches_all_and_stays(self) -> None:
        self.run_merge("--apply")
        document = self.document()
        document["byAccount"][B]["presets"] = [
            p for p in document["byAccount"][B]["presets"] if p["id"] != "p2"
        ]
        self.write(document)

        report = self.run_merge("--apply")
        again = self.run_merge("--apply")

        self.assertIn("2 removed", report)
        for account in (A, B, C):
            self.assertEqual(ids(self.document(), account), ["p1"], account)
        self.assertIn("environments: 0 to add, 0 to update, 0 removed", again)

    def test_no_environments_leaves_the_file_alone(self) -> None:
        report = self.run_merge("--apply", "--no-environments")

        self.assertNotIn("environments:", report)
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_undo_restores_the_original_file_and_forgets_the_baseline(self) -> None:
        self.run_merge("--apply")
        self.run_merge("--apply")

        report = self.run_merge("--undo")

        self.assertIn("Restored the environments file", report)
        self.assertEqual(self.file.read_bytes(), self.original)
        self.assertFalse((self.root / environments_sync.BASELINE_NAME).exists())
        self.assertFalse((self.root / merge.MANIFEST_NAME).exists())

    def test_undo_refuses_a_backup_of_another_file(self) -> None:
        self.run_merge("--apply")
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir()

        with (
            patch.dict(os.environ, {environments_sync.APP_DIR_ENV: str(elsewhere)}),
            contextlib.redirect_stdout(io.StringIO()),
            patch.object(sys, "argv", ["merge.py", "--undo"]),
            self.assertRaises(SystemExit) as raised,
        ):
            merge.main()

        self.assertIn("Point it back", str(raised.exception.code))
        self.assertTrue((self.root / merge.MANIFEST_NAME).exists())

    def test_an_unreadable_file_is_reported_and_left_alone(self) -> None:
        self.file.write_text("{ not json")

        report = self.run_merge("--apply", code=1)

        self.assertIn("ENVIRONMENTS NOT ALIGNED", report)
        self.assertEqual(self.file.read_text(), "{ not json")

    def test_a_missing_file_is_skipped_quietly(self) -> None:
        self.file.unlink()

        report = self.run_merge("--apply")

        self.assertIn("no environments file", report)
        self.assertFalse(self.file.exists())

    def test_a_file_the_app_changed_mid_run_is_not_overwritten(self) -> None:
        real_plan = environments_sync.plan_step

        def plan_then_app_writes(*args, **kwargs):
            planned = real_plan(*args, **kwargs)
            self.write(doc(account_a={"presets": [preset("p9")]}))
            return planned

        with patch.object(environments_sync, "plan_step", plan_then_app_writes):
            report = self.run_merge("--apply", code=1)

        self.assertIn("changed while this run was planning", report)
        self.assertEqual(ids(self.document(), A), ["p9"])

    def test_the_default_location_is_beside_the_session_index(self) -> None:
        os.environ.pop(environments_sync.APP_DIR_ENV)

        self.assertEqual(
            environments_sync.presets_path(self.root), self.home / environments_sync.PRESETS_NAME
        )


if __name__ == "__main__":
    unittest.main()
