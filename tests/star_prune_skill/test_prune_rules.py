"""prune_rules: which stars are flagged, for what reason, and with which proposed action."""

from __future__ import annotations

import unittest

from star_prune_skill.helpers import NOW, account, load, star

prune_rules = load("prune_rules")


def by_name(candidates: list) -> dict:
    return {candidate["name"]: candidate for candidate in candidates}


class ClassifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.found = by_name(prune_rules.classify(account(), NOW))

    def test_healthy_and_owned_repositories_are_not_flagged(self) -> None:
        self.assertNotIn("live/tool", self.found)
        self.assertNotIn("octo/mine", self.found)

    def test_strong_reasons_propose_unstar(self) -> None:
        for name, reason in (
            ("old/archived", "archived"),
            ("gone/disabled", "disabled"),
            ("dep/text", "deprecated"),
        ):
            self.assertEqual(self.found[name]["reasons"][0], reason)
            self.assertEqual(self.found[name]["action"], "unstar")

    def test_deprecation_evidence_names_the_phrase_or_topic(self) -> None:
        self.assertEqual(self.found["dep/text"]["evidence"], "description says 'deprecated'")
        self.assertEqual(self.found["dep/topic"]["evidence"], "topic 'unmaintained'")

    def test_dormant_and_old_stars_are_kept_by_default(self) -> None:
        self.assertEqual(self.found["quiet/lib"]["reasons"], ["dormant"])
        self.assertEqual(self.found["quiet/lib"]["action"], "keep")
        self.assertEqual(self.found["forgot/it"]["reasons"], ["old-star"])
        self.assertEqual(self.found["forgot/it"]["action"], "keep")

    def test_archived_is_not_also_called_dormant(self) -> None:
        self.assertEqual(self.found["old/archived"]["reasons"], ["archived"])
        self.assertEqual(self.found["old/archived"]["lists"], ["Old", "Tools"])

    def test_thresholds_move_the_line(self) -> None:
        loose = by_name(prune_rules.classify(account(), NOW, dormant_years=5, old_star_years=10))
        self.assertNotIn("quiet/lib", loose)
        self.assertNotIn("forgot/it", loose)

    def test_a_listed_old_star_is_not_flagged(self) -> None:
        state = account()
        state["lists"][0]["items"].append("forgot/it")
        self.assertNotIn("forgot/it", by_name(prune_rules.classify(state, NOW)))

    def test_order_is_strongest_reason_first(self) -> None:
        order = [c["reasons"][0] for c in prune_rules.classify(account(), NOW)]
        self.assertEqual(order, sorted(order, key=prune_rules.REASONS.index))

    def test_phrases_that_are_not_deprecation_do_not_match(self) -> None:
        for text in ("A deprecation-free API", "We moved fast", "Supports removed devices"):
            self.assertEqual(prune_rules.deprecation_evidence(star("x/y", description=text)), "", text)
        self.assertTrue(prune_rules.deprecation_evidence(star("x/y", description="No longer maintained.")))

    def test_missing_timestamps_count_as_recent(self) -> None:
        self.assertEqual(prune_rules.years_since("", NOW), 0.0)


if __name__ == "__main__":
    unittest.main()
