from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "plugins" / "chinese-metaphysics" / "shared"
sys.path.insert(0, str(SHARED))

from bazi.artifacts import (
    ArtifactError,
    add_checksum,
    slugify,
    validate_envelope,
    write_artifact_pair,
)


def envelope(name: str = "Example Person", marker: str = "one") -> dict:
    return add_checksum(
        {
            "schema": "chinese-metaphysics.bazi-chart",
            "schema_version": 1,
            "input": {"name": name, "marker": marker},
            "pillars": {"primary": {"year": {"text": "甲子"}}},
        }
    )


class ArtifactTests(unittest.TestCase):
    def test_unicode_slug_is_portable_and_cannot_traverse(self) -> None:
        self.assertEqual(slugify(" 张 三 / ../../ secrets "), "张-三-secrets")
        self.assertEqual(slugify("..."), "unnamed")

    def test_checksum_uses_canonical_content_and_detects_tampering(self) -> None:
        first = envelope()
        reordered = {key: first[key] for key in reversed(first)}

        self.assertEqual(validate_envelope(first)["checksum"], validate_envelope(reordered)["checksum"])
        corrupt = copy.deepcopy(first)
        corrupt["input"]["marker"] = "changed"
        with self.assertRaisesRegex(ArtifactError, "checksum"):
            validate_envelope(corrupt)

    def test_pair_writes_canonical_json_and_data_only_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path, markdown_path = write_artifact_pair(envelope("张三"), Path(directory), kind="chart")

            self.assertEqual(json_path.name, "bazi_张三.json")
            self.assertEqual(markdown_path.name, "bazi_张三.md")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(validate_envelope(parsed)["input"]["name"], "张三")
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("甲子", markdown)
            self.assertNotIn("personality", markdown.lower())
            self.assertNotIn("命运", markdown)

    def test_existing_same_content_is_reused_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            paths = write_artifact_pair(envelope(), output, kind="chart")
            original_mtime = paths[0].stat().st_mtime_ns
            repeated = write_artifact_pair(envelope(), output, kind="chart")

            self.assertEqual(paths, repeated)
            self.assertEqual(paths[0].stat().st_mtime_ns, original_mtime)

    def test_same_name_different_checksum_gets_a_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = write_artifact_pair(envelope(marker="one"), output, kind="chart")
            second_payload = envelope(marker="two")
            second = write_artifact_pair(second_payload, output, kind="chart")

            self.assertNotEqual(first, second)
            self.assertIn(second_payload["checksum"][:8], second[0].stem)
            self.assertEqual(json.loads(first[0].read_text(encoding="utf-8"))["input"]["marker"], "one")


if __name__ == "__main__":
    unittest.main()
