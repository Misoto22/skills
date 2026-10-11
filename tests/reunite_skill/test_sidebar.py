"""Planning the copy of one account's sidebar layout onto the others' scopes."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/dev/skills/reunite/scripts"))

import sidebar

A, B, C = "acct-a", "acct-b", "acct-c"
SCOPE_A, SCOPE_B, SCOPE_C = f"{A}/org-a", f"{B}/org-b", f"{C}/org-c"


def section(kind: str, order: int, **extra) -> dict:
    return {"id": f"{kind}-{order}", "kind": kind, "name": "", "order": order, "collapsed": False, **extra}


def document() -> dict:
    layout = {
        "sections": [
            section("pinned", 0),
            section("manual", 1, name="Work", members=["code:local_1", "code:local_gone", "cowork:x"]),
            section("manual", 2, name="Play", members=["code:local_2"], collapsed=True),
            section("sessions", 3),
        ],
        "migratedFrom": 1,
        "prefsSeeded": True,
    }
    return {
        "state": {
            "collapsed": False,
            sidebar.SECTIONS_BY_SCOPE: {
                SCOPE_A: layout,
                SCOPE_B: {"sections": [section("pinned", 0)], "migratedFrom": 1, "prefsSeeded": True},
            },
            sidebar.GROUPS_BY_SCOPE: {SCOPE_A: {"groups": [{"id": "manual-1", "name": "Work"}]}},
            "sidebarRowCountsByScope": {SCOPE_B: {"code.recents": 9}},
        },
        "version": 3,
    }


class EncodingTests(unittest.TestCase):
    def test_latin1_round_trip_matches_the_compact_form(self) -> None:
        raw = b'\x01{"state":{"name":"caf\xe9"},"version":0}'
        self.assertEqual(sidebar.encode(sidebar.decode(raw)), raw)

    def test_text_outside_latin1_is_stored_as_utf16(self) -> None:
        doc = {"state": {"name": "会话"}, "version": 0}
        raw = sidebar.encode(doc)
        self.assertEqual(raw[:1], sidebar.UTF16)
        self.assertEqual(raw[1:].decode("utf-16-le"), '{"state":{"name":"会话"},"version":0}')
        self.assertEqual(sidebar.decode(raw), doc)

    def test_unreadable_values_are_refused(self) -> None:
        for raw in (b"\x02{}", b"\x01not json", b'\x01{"version":0}', b"\x01[]", b"\x00\x00\xd8"):
            with self.subTest(raw=raw), self.assertRaises(sidebar.SidebarError):
                sidebar.decode(raw)


class SourceScopeTests(unittest.TestCase):
    def test_the_landing_scope_is_preferred(self) -> None:
        state = {sidebar.SECTIONS_BY_SCOPE: {SCOPE_A: {}, f"{A}/other": {}}}
        self.assertEqual(sidebar.source_scope(state, A, SCOPE_A), SCOPE_A)

    def test_a_single_scope_of_the_account_is_used_when_the_landing_one_is_absent(self) -> None:
        state = {sidebar.SECTIONS_BY_SCOPE: {f"{A}/other": {}, SCOPE_B: {}}}
        self.assertEqual(sidebar.source_scope(state, A, SCOPE_A), f"{A}/other")

    def test_ambiguous_or_missing_scopes_are_refused(self) -> None:
        for state in (
            {sidebar.SECTIONS_BY_SCOPE: {f"{A}/x": {}, f"{A}/y": {}}},
            {sidebar.SECTIONS_BY_SCOPE: {SCOPE_B: {}}},
            {},
        ):
            with self.subTest(state=state), self.assertRaises(sidebar.SidebarError):
                sidebar.source_scope(state, A, SCOPE_A)


class PruneTests(unittest.TestCase):
    def test_drops_only_manual_members_missing_from_the_index(self) -> None:
        layout = document()["state"][sidebar.SECTIONS_BY_SCOPE][SCOPE_A]
        original = copy.deepcopy(layout)

        pruned, dropped = sidebar.prune(layout, {"local_1"})

        self.assertEqual(dropped, 2)
        self.assertEqual(pruned["sections"][1]["members"], ["code:local_1", "cowork:x"])
        self.assertEqual(pruned["sections"][2]["members"], [])
        self.assertEqual(layout, original)

    def test_counts_manual_groups(self) -> None:
        layout = document()["state"][sidebar.SECTIONS_BY_SCOPE][SCOPE_A]
        self.assertEqual(sidebar.manual_count(layout), 2)
        self.assertEqual(sidebar.manual_count(None), 0)
        self.assertEqual(sidebar.sections_of({"sections": "nonsense"}), [])


class PlanLayoutTests(unittest.TestCase):
    def plan(self, doc: dict, held: dict[str, set[str]] | None = None):
        scopes = {A: SCOPE_A, B: SCOPE_B, C: SCOPE_C}
        everything = {"local_1", "local_2", "local_gone"}
        return sidebar.plan_layout(doc, SCOPE_A, A, scopes, held or dict.fromkeys(scopes, everything))

    def test_copies_the_layout_to_every_other_scope_and_creates_missing_ones(self) -> None:
        doc = document()
        updated, changes = self.plan(doc, {B: {"local_1", "local_2"}, C: {"local_1"}})

        sections = updated["state"][sidebar.SECTIONS_BY_SCOPE]
        self.assertEqual([c.scope for c in changes], [SCOPE_B, SCOPE_C])
        self.assertEqual([c.created for c in changes], [False, True])
        self.assertEqual([c.dropped for c in changes], [1, 2])
        self.assertEqual([(c.manual_before, c.manual_after) for c in changes], [(0, 2), (0, 2)])
        self.assertEqual(sections[SCOPE_C]["sections"][2]["members"], [])
        self.assertEqual(sections[SCOPE_A], doc["state"][sidebar.SECTIONS_BY_SCOPE][SCOPE_A])
        groups = updated["state"][sidebar.GROUPS_BY_SCOPE]
        self.assertEqual(groups[SCOPE_B], groups[SCOPE_A])
        self.assertEqual(updated["state"]["sidebarRowCountsByScope"], doc["state"]["sidebarRowCountsByScope"])
        self.assertEqual(updated["version"], 3)
        self.assertNotIn(SCOPE_C, doc["state"][sidebar.SECTIONS_BY_SCOPE])

    def test_a_scope_that_already_matches_is_unchanged(self) -> None:
        updated, _ = self.plan(document())
        _, changes = self.plan(updated)
        self.assertFalse(any(c.changed for c in changes))

    def test_a_source_without_group_names_leaves_them_alone(self) -> None:
        doc = document()
        del doc["state"][sidebar.GROUPS_BY_SCOPE]
        updated, changes = self.plan(doc)
        self.assertNotIn(sidebar.GROUPS_BY_SCOPE, updated["state"])
        self.assertTrue(all(c.changed for c in changes))


if __name__ == "__main__":
    unittest.main()
