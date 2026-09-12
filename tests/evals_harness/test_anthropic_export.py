"""Contract tests for the Claude plugin eval exporter."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.evals.anthropic_export import export_suite

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_BARE = ROOT / "tests/evals_harness/fixtures/claude-plugin-eval-bare-2.1.269"


class ClaudeExportTests(unittest.TestCase):
    def _suite(self, root: Path, data: dict) -> Path:
        suite = root / "evals" / data["skill"]
        suite.mkdir(parents=True)
        path = suite / "evals.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    @staticmethod
    def _data() -> dict:
        return {
            "skill": "example",
            "triggers": [{"id": "route", "prompt": "Route", "expected": "Fires"}],
            "non_triggers": [],
            "behaviors": [
                {"id": "tune", "prompt": "Tune prompt", "expectations": ["First", "Second"]},
                {
                    "id": "held",
                    "prompt": "HELD SECRET PROMPT",
                    "expectations": ["HELD SECRET CRITERION"],
                    "holdout": True,
                },
            ],
        }

    def test_export_matches_verified_bare_template_and_exports_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._suite(root, self._data())
            output = root / "tuning"
            manifest = export_suite(source, output, split="tuning")

            prompt = (output / "tune" / "prompt.md").read_text(encoding="utf-8")
            criteria = (output / "tune" / "graders" / "criteria.md").read_text(encoding="utf-8")
            prompt_template = (OFFICIAL_BARE / "prompt.md").read_text(encoding="utf-8")
            criteria_template = (OFFICIAL_BARE / "graders/criteria.md").read_text(encoding="utf-8")
            self.assertEqual(
                prompt,
                prompt_template.replace("TODO: describe what the agent should do", "Tune prompt"),
            )
            self.assertEqual(
                criteria,
                criteria_template.replace(
                    "TODO: describe what a successful response looks like",
                    "1. First\n2. Second",
                ),
            )
            self.assertEqual(manifest["source"], "evals/example/evals.json")
            self.assertEqual(manifest["cases"][0]["source_pointer"], "/behaviors/0")
            self.assertEqual(manifest["split"], "tuning")

    def test_verified_template_provenance_is_pinned_to_the_official_package(self) -> None:
        provenance = json.loads((OFFICIAL_BARE / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["package"], "@anthropic-ai/claude-code")
        self.assertEqual(provenance["version"], "2.1.269")
        self.assertEqual(
            provenance["npm_dist_integrity"],
            "sha512-osSbRU1KjlAfhVSgso7g+KxCr5DLNlfm7xeRPpm/c9s+7HGqQLHbkUYvjepbe6TiHJa9iSeirW/t7vW4sZhTIQ==",
        )
        self.assertEqual(provenance["captured_date"], "2026-09-12")
        self.assertEqual(
            hashlib.sha256((OFFICIAL_BARE / "prompt.md").read_bytes()).hexdigest(),
            provenance["prompt_sha256"],
        )
        self.assertEqual(
            hashlib.sha256((OFFICIAL_BARE / "graders/criteria.md").read_bytes()).hexdigest(),
            provenance["criteria_sha256"],
        )

    def test_tuning_export_contains_no_holdout_prompt_or_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "tuning"
            export_suite(self._suite(root, self._data()), output, split="tuning")
            rendered = "\n".join(
                path.read_text(encoding="utf-8") for path in output.rglob("*") if path.is_file()
            )
            self.assertNotIn("HELD SECRET", rendered)
            self.assertFalse((output / "held").exists())

    def test_fixture_is_copied_and_referenced_without_absolute_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = self._data()
            data["behaviors"] = [
                {
                    "id": "fixture-case",
                    "prompt": "Read it",
                    "expectations": ["Uses the fixture"],
                    "fixture": "fixtures/input.json",
                    "language": "zh",
                    "modules": ["work"],
                }
            ]
            source = self._suite(root, data)
            fixture = source.parent / "fixtures" / "input.json"
            fixture.parent.mkdir()
            fixture.write_text('{"safe": true}\n', encoding="utf-8")
            output = root / "out"
            manifest = export_suite(source, output, split="tuning")

            copied = output / "fixture-case" / "resources" / "input.json"
            self.assertEqual(copied.read_text(encoding="utf-8"), '{"safe": true}\n')
            prompt = (output / "fixture-case" / "prompt.md").read_text(encoding="utf-8")
            self.assertIn("resources/input.json", prompt)
            self.assertIn("Requested output language: zh.", prompt)
            self.assertNotIn(str(root), json.dumps(manifest))
            self.assertIn("fixture_hash", manifest["cases"][0])

    def test_existing_output_is_never_removed_or_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._suite(root, self._data())
            output = root / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("mine", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                export_suite(source, output, split="tuning")
            self.assertEqual(marker.read_text(encoding="utf-8"), "mine")

    def test_case_id_cannot_escape_the_output_and_failed_export_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = self._data()
            data["behaviors"] = [{"id": "../../escape", "prompt": "x", "expectations": ["y"]}]
            output = root / "out"
            with self.assertRaisesRegex(ValueError, "kebab-case"):
                export_suite(self._suite(root, data), output, split="tuning")
            self.assertFalse(output.exists())
            self.assertFalse((root / "escape").exists())

    def test_fixture_must_stay_inside_the_suite_and_must_not_be_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            data = self._data()
            data["behaviors"] = [
                {"id": "fixture-case", "prompt": "x", "expectations": ["y"], "fixture": "fixtures/link.json"}
            ]
            source = self._suite(root, data)
            fixtures = source.parent / "fixtures"
            fixtures.mkdir()
            (fixtures / "link.json").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "escapes|link"):
                export_suite(source, root / "out", split="tuning")

    def test_unsupported_sections_and_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._suite(root, self._data())
            with self.assertRaisesRegex(ValueError, "only behavior"):
                export_suite(source, root / "routing", split="tuning", section="triggers")

            data = self._data()
            data["behaviors"][0]["artifact"] = "fixtures/generated.json"
            with self.assertRaisesRegex(ValueError, "unsupported fields: artifact"):
                export_suite(self._suite(root / "second", data), root / "unsupported", split="tuning")

    def test_split_is_required_and_must_have_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._suite(root, self._data())
            with self.assertRaisesRegex(ValueError, "split"):
                export_suite(source, root / "bad", split="all")
            data = self._data()
            data["behaviors"] = [data["behaviors"][0]]
            with self.assertRaisesRegex(ValueError, "no holdout"):
                export_suite(self._suite(root / "second", data), root / "empty", split="holdout")


if __name__ == "__main__":
    unittest.main()
