"""Hold every declared model id to living in exactly one place.

An artifact names the model that produced it, and that name was written twice:
once in the rules file the engine loads, once as a literal in the engine. The two
agreed only because nobody had bumped a rules file yet — after which the artifact
would have named two different versions of itself, with nothing comparing them.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
RULES = SHARED / "rules"
sys.path.insert(0, str(SHARED))

DECLARED = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(RULES.glob("*.json"))}


class RulesFilesTests(unittest.TestCase):
    def test_every_rules_file_declares_its_id_under_one_key(self) -> None:
        """Three key names for one concept meant no helper could read them all."""

        self.assertTrue(DECLARED, "no rules files found")
        for name, rules in DECLARED.items():
            with self.subTest(rules=name):
                self.assertIn("model_id", rules)
                self.assertTrue(str(rules["model_id"]).strip())
                for retired in ("model_version", "id"):
                    self.assertNotIn(retired, rules, f"{name} still carries the old key {retired!r}")

    def test_model_ids_are_distinct(self) -> None:
        ids = [rules["model_id"] for rules in DECLARED.values()]
        self.assertEqual(len(ids), len(set(ids)), "two rules files claim the same model id")


class NoLiteralsTests(unittest.TestCase):
    def test_no_engine_writes_a_model_id_as_a_literal(self) -> None:
        """The rules file is the source; a literal beside it is a second one."""

        declared = {rules["model_id"] for rules in DECLARED.values()}
        for path in sorted((SHARED / "bazi").glob("*.py")) + sorted((SHARED / "ziwei").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for model_id in declared:
                with self.subTest(file=path.name, model_id=model_id):
                    self.assertNotRegex(
                        source,
                        rf'["\']{re.escape(model_id)}["\']',
                        f"{path.name} writes {model_id!r} as a literal; read it from the rules file",
                    )


class ProducedArtifactTests(unittest.TestCase):
    """The ids in a real artifact must trace back to the rules that produced it."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from bazi.ephemeris import EphemerisUnavailable, SwissEphemeris
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("shared engine unavailable") from None
        try:
            ephemeris = SwissEphemeris()
        except EphemerisUnavailable:
            raise unittest.SkipTest("pyswisseph is not installed") from None

        from bazi.engine import build_chart
        from ziwei.engine import build_chart as build_ziwei

        request = {
            "name": "Subject A",
            "birth_place": "Shanghai, China",
            "birth_date": "1988-04-11",
            "birth_time": "09:15",
            "calendar": "gregorian",
            "timezone": "Asia/Shanghai",
            "latitude": 31.23,
            "longitude": 121.47,
        }
        cls.bazi = build_chart(dict(request), ephemeris)
        cls.ziwei = build_ziwei(dict(request) | {"gender": "male"}, ephemeris)

    def test_the_bazi_artifact_names_the_rules_that_built_it(self) -> None:
        methodology = self.bazi["methodology"]
        self.assertEqual(methodology["calendar_model"], DECLARED["chart-v1.json"]["model_id"])
        self.assertEqual(methodology["scoring_model"], DECLARED["scoring-v1.json"]["model_id"])

    def test_it_names_the_same_model_everywhere_it_names_one(self) -> None:
        """The failure this prevents: one artifact claiming two model versions."""

        self.assertEqual(
            self.bazi["facts"]["primary"]["model_version"],
            self.bazi["methodology"]["calendar_model"],
        )
        self.assertEqual(
            self.bazi["scores"]["primary"]["model_version"],
            self.bazi["methodology"]["scoring_model"],
        )

    def test_the_ziwei_artifact_names_the_rules_that_built_it(self) -> None:
        self.assertEqual(
            self.ziwei["methodology"]["placement_model"],
            DECLARED["ziwei-v1.json"]["model_id"],
        )


class SharedCycleTests(unittest.TestCase):
    def test_the_sexagenary_cycle_is_defined_once(self) -> None:
        """Zi Wei counts palaces where BaZi counts pillars; the cycle is the same."""

        from bazi.pillars import BRANCHES, STEMS
        from ziwei.palaces import BRANCHES as PALACE_BRANCHES
        from ziwei.palaces import STEMS as PALACE_STEMS

        self.assertIs(BRANCHES, PALACE_BRANCHES)
        self.assertIs(STEMS, PALACE_STEMS)

    def test_no_module_redefines_the_cycle(self) -> None:
        for path in sorted((SHARED / "ziwei").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotRegex(source, r"(?m)^(BRANCHES|STEMS)\s*=\s*tuple\(")


if __name__ == "__main__":
    unittest.main()
