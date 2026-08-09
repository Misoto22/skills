from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
READER_SKILL = SKILL / "SKILL.md"
TEMPLATE = SKILL / "references" / "output-template.md"
EDITORIAL = SKILL / "references" / "editorial-policy.md"
EXAMPLES = SKILL / "references" / "examples.md"
OPENAI = SKILL / "agents" / "openai.yaml"
EVALS = ROOT / "evals" / "synastry-reading" / "evals.json"
FIXTURE = Path(__file__).parent / "fixtures" / "neutral.json"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

from validate_reading import validate_markdown  # type: ignore[import-not-found]
from validate_synastry import load_ledger  # type: ignore[import-not-found]

UNIVERSAL_HEADINGS = (
    "Basis, provenance, and limitations",
    "Repeated interaction patterns",
    "Reciprocity and asymmetry",
    "Communication and coordination",
    "Tension, boundaries, and repair",
    "Growth and shared direction",
    "Requested or context-specific domains",
    "Overall synthesis",
    "Evidence index",
)


class ReaderSkillContractTests(unittest.TestCase):
    def test_frontmatter_names_the_skill_and_body_stays_short(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: synastry-reading\n")
        self.assertLess(len(text.splitlines()), 500)

    def test_reader_uses_universal_core_and_conditional_domains(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")
        self.assertIn("validate_synastry.py", text)
        self.assertIn("validate_reading.py", text)
        self.assertIn("explicit relationship context", text)
        self.assertNotIn("Use every fixed core heading", text)

    def test_reader_refuses_txt_and_finalizes_only_validated_markdown(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        for required in ("JSON v2", "draft", "synastry_reading_<chart-id>.md", "atomically"):
            self.assertIn(required, text)
        self.assertRegex(text, r"(?i)TXT[^\n]+(?:refus|recalculat|not supported)")
        self.assertIn("untrusted data", text)

    def test_documented_stateless_lifecycle_executes_for_attached_and_pasted_sources(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")
        source_validator = SKILL / "scripts" / "validate_synastry.py"
        reading_validator = SKILL / "scripts" / "validate_reading.py"
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))

        attached = subprocess.run(
            [sys.executable, str(source_validator), str(FIXTURE)],
            cwd=SKILL,
            capture_output=True,
            check=False,
            text=True,
        )
        pasted = subprocess.run(
            [sys.executable, str(source_validator), "-"],
            cwd=SKILL,
            input=json.dumps(source),
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual((attached.returncode, pasted.returncode), (0, 0))
        attached_ledger = json.loads(attached.stdout)
        pasted_ledger = json.loads(pasted.stdout)
        self.assertEqual(attached_ledger["chart_id"], pasted_ledger["chart_id"])
        self.assertEqual(attached_ledger["evidence"], pasted_ledger["evidence"])
        evidence = attached_ledger["evidence"][0]["citation"]
        lines = ["# Synastry reading"]
        for heading in UNIVERSAL_HEADINGS:
            lines.extend((f"## {heading}", evidence))
        report = "\n\n".join(lines) + "\n"

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            destination = directory / "synastry_reading_abc123def456.md"
            invalid = subprocess.run(
                [sys.executable, str(reading_validator), "-", "-", "--out", str(destination)],
                cwd=SKILL,
                input=json.dumps({"source": source, "draft": "# Invalid"}),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(list(directory.iterdir()), [])

            retried = subprocess.run(
                [sys.executable, str(reading_validator), "-", "-", "--out", str(destination)],
                cwd=SKILL,
                input=json.dumps({"source": source, "draft": report}),
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(retried.returncode, 0, retried.stderr)
            self.assertEqual(destination.read_text(encoding="utf-8"), report)
            self.assertEqual(list(directory.iterdir()), [destination])

        self.assertIn("standard output", text)
        self.assertIn("standard input", text)
        self.assertNotIn("draft_dir", text)
        self.assertNotIn("source_path", text)
        self.assertNotIn("mktemp", text)
        self.assertNotIn("trap ", text)

    def test_every_linked_reference_and_runtime_script_resolves(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        references = re.findall(r"\[[^]]+\]\((references/[^)]+)\)", text)
        scripts = re.findall(r"python3 (scripts/[^\s]+\.py)", text)

        self.assertEqual(len(references), 3)
        self.assertEqual(set(scripts), {"scripts/validate_synastry.py", "scripts/validate_reading.py"})
        for path in (*references, *scripts):
            with self.subTest(path=path):
                self.assertTrue((SKILL / path).is_file())

    def test_template_has_exact_universal_order_and_conditional_modules(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        for heading in UNIVERSAL_HEADINGS:
            self.assertIn(f"## {heading}", text)
        positions = [text.index(f"## {heading}") for heading in UNIVERSAL_HEADINGS]

        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("## Attraction, romance, and intimacy", text)
        for module in (
            "Romance and intimacy",
            "Friendship and community",
            "Family and care",
            "Work and creative collaboration",
            "Money and shared resources",
        ):
            self.assertIn(module, text)

    def test_progressive_references_cover_editorial_and_adversarial_cases(self) -> None:
        skill = READER_SKILL.read_text(encoding="utf-8")
        self.assertTrue(EDITORIAL.is_file(), "editorial policy reference is missing")
        editorial = EDITORIAL.read_text(encoding="utf-8")
        examples = EXAMPLES.read_text(encoding="utf-8")

        for path in (
            "references/output-template.md",
            "references/editorial-policy.md",
            "references/examples.md",
        ):
            self.assertIn(path, skill)
        for required in ("editorial-v1", "independent", "conditional", "confirmed", "possible"):
            self.assertIn(required, editorial)
        for required in ("neutral", "romantic", "weak", "adversarial", "TXT"):
            self.assertIn(required, examples)

        priority = editorial.split("## Evidence priority", 1)[1].split("## Independent support", 1)[0]
        self.assertNotRegex(priority, r"(?i)\b(?:angles?|lots?)\b")
        self.assertRegex(priority, r"(?i)\baspects?\b")
        self.assertRegex(priority, r"(?i)\boverlays?\b")

    def test_template_representatives_pass_the_bundled_validator(self) -> None:
        blocks = re.findall(r"```markdown\n(.*?)\n```", TEMPLATE.read_text(encoding="utf-8"), re.S)
        evidence = load_ledger(FIXTURE).evidence[0].citation

        for block, language, title, domains_heading, module in (
            (
                blocks[0],
                "en",
                "# Synastry Reading",
                "## Requested or context-specific domains",
                "Money and shared resources",
            ),
            (
                blocks[1],
                "zh",
                "# 双方合盘分析",
                "## 用户要求或关系背景领域",
                "金钱与共同资源",
            ),
        ):
            with self.subTest(language=language):
                lines = [title]
                for heading in (line for line in block.splitlines() if line.startswith("## ")):
                    lines.extend((heading, evidence))
                    if heading == domains_heading:
                        lines.extend((f"### {module}", evidence))
                report = "\n\n".join(lines) + "\n"

                self.assertEqual(validate_markdown(report, load_ledger(FIXTURE), language, (module,)), [])

    def test_metadata_matches_validated_json_v2_workflow(self) -> None:
        text = OPENAI.read_text(encoding="utf-8")

        self.assertIn("$synastry-reading", text)
        self.assertIn("JSON v2", text)
        self.assertIn("evidence", text)

    def test_eval_suite_covers_chinese_json_and_external_domain_authority(self) -> None:
        suite = json.loads(EVALS.read_text(encoding="utf-8"))
        triggers = {case["id"]: case for case in suite["triggers"]}
        behaviors = {case["id"]: case for case in suite["behaviors"]}

        chinese = triggers["chinese-json-v2-reading"]["prompt"]
        self.assertIn("合盘解读", chinese)
        self.assertIn("JSON v2", chinese)
        weak_domain = behaviors["weak-requested-domain"]["prompt"].casefold()
        self.assertTrue(
            "user explicitly requests" in weak_domain or "handoff explicitly requests" in weak_domain
        )
        self.assertNotIn("source explicitly requests", weak_domain)


if __name__ == "__main__":
    unittest.main()
