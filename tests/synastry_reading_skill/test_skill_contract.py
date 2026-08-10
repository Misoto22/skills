from __future__ import annotations

import json
import os
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

from synastry_schema import attach_integrity  # type: ignore[import-not-found]
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
CHINESE_UNIVERSAL_HEADINGS = (
    "分析基础、数据来源与限制",
    "反复出现的互动模式",
    "双向影响与不对称性",
    "沟通与协作",
    "张力、边界与修复",
    "成长与共同方向",
    "用户要求或关系背景领域",
    "整体总结",
    "证据索引",
)


def chinese_report(source: dict[str, object]) -> str:
    citation = load_ledger(source).evidence[0].citation
    lines = ["# 双方合盘分析"]
    for heading in CHINESE_UNIVERSAL_HEADINGS:
        lines.extend((f"## {heading}", citation))
    return "\n\n".join(lines) + "\n"


def documented_language_override() -> str | None:
    documented = re.search(
        r"```bash\npython3 scripts/reading_session\.py finalize <session-token>(.*?)\n```",
        READER_SKILL.read_text(encoding="utf-8"),
        re.S,
    )
    if documented is None:
        raise AssertionError("documented finalization command is missing")
    language = re.search(r"--language[ \t]+([^\s\\]+)", documented.group(1))
    return None if language is None else language.group(1)


def run_documented_default_finalization(
    source: dict[str, object],
    report: str,
) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str], str | None]:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        environment = os.environ | {
            "SYNASTRY_READING_SESSION_ROOT": str(directory / "sessions"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        helper = SKILL / "scripts" / "reading_session.py"
        started = subprocess.run(
            [sys.executable, str(helper), "start", "-"],
            cwd=SKILL,
            env=environment,
            input=json.dumps(source),
            capture_output=True,
            check=False,
            text=True,
        )
        status = json.loads(started.stdout)
        destination = directory / "synastry_reading_abc123def456.md"
        arguments = ["finalize", status["token"]]
        if (language := documented_language_override()) is not None:
            arguments.extend(("--language", language))
        arguments.extend(("--out", str(destination)))
        finalized = subprocess.run(
            [sys.executable, str(helper), *arguments],
            cwd=SKILL,
            env=environment,
            input=report,
            capture_output=True,
            check=False,
            text=True,
        )
        written = destination.read_text(encoding="utf-8") if destination.exists() else None
    return started, finalized, written


class ReaderSkillContractTests(unittest.TestCase):
    def test_frontmatter_names_the_skill_and_body_stays_short(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: synastry-reading\n")
        self.assertLess(len(text.splitlines()), 500)

    def test_reader_uses_universal_core_and_conditional_domains(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")
        self.assertIn("reading_session.py", text)
        self.assertIn("explicit relationship context", text)
        self.assertNotIn("Use every fixed core heading", text)

    def test_reader_refuses_txt_and_finalizes_only_validated_markdown(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        for required in ("JSON v2", "draft", "synastry_reading_<chart-id>.md", "atomically"):
            self.assertIn(required, text)
        self.assertRegex(text, r"(?i)TXT[^\n]+(?:refus|recalculat|not supported)")
        self.assertIn("untrusted data", text)

    def test_reader_documents_recoverable_commit_acknowledgement_and_truthful_cancel(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8").casefold()

        for required in (
            "exact bytes",
            "different content",
            "already complete",
            "cancel exits nonzero",
        ):
            self.assertIn(required, text)

    def test_documented_private_session_executes_for_attached_and_pasted_sources(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")
        session_helper = SKILL / "scripts" / "reading_session.py"
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            environment = os.environ | {
                "SYNASTRY_READING_SESSION_ROOT": str(directory / "sessions"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            attached = subprocess.run(
                [sys.executable, str(session_helper), "start", str(FIXTURE)],
                cwd=SKILL,
                env=environment,
                capture_output=True,
                check=False,
                text=True,
            )
            pasted = subprocess.run(
                [sys.executable, str(session_helper), "start", "-"],
                cwd=SKILL,
                env=environment,
                input=json.dumps(source),
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertEqual((attached.returncode, pasted.returncode), (0, 0))
            attached_status = json.loads(attached.stdout)
            pasted_status = json.loads(pasted.stdout)
            self.assertIn("pages_path", attached_status)
            self.assertIn("pages_path", pasted_status)
            attached_pages = Path(attached_status["pages_path"])
            pasted_pages = Path(pasted_status["pages_path"])
            attached_ledger = json.loads(
                b"".join(path.read_bytes() for path in sorted(attached_pages.iterdir()))
            )
            pasted_ledger = json.loads(b"".join(path.read_bytes() for path in sorted(pasted_pages.iterdir())))
            self.assertEqual(attached_ledger["evidence"], pasted_ledger["evidence"])
            self.assertNotIn("display_name", json.dumps(attached_ledger))
            for status in (attached_status, pasted_status):
                cancelled = subprocess.run(
                    [sys.executable, str(session_helper), "cancel", status["token"]],
                    cwd=SKILL,
                    env=environment,
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(cancelled.returncode, 0, cancelled.stderr)

        self.assertIn("bounded", text)
        self.assertIn("private", text)
        self.assertIn("expires", text)
        self.assertIn("reading_session.py", text)

    def test_documented_default_finalization_inherits_the_artifact_language(self) -> None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        source["configuration"]["language"] = "zh"
        source = attach_integrity(source)
        report = chinese_report(source)

        started, finalized, written = run_documented_default_finalization(source, report)

        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        self.assertEqual(written, report)

    def test_every_linked_reference_and_runtime_script_resolves(self) -> None:
        text = READER_SKILL.read_text(encoding="utf-8")

        references = re.findall(r"\[[^]]+\]\((references/[^)]+)\)", text)
        scripts = re.findall(r"python3 (scripts/[^\s]+\.py)", text)

        self.assertEqual(len(references), 3)
        self.assertEqual(set(scripts), {"scripts/reading_session.py"})
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
        selected_ledger = load_ledger(FIXTURE)
        evidence = selected_ledger.evidence[0].citation

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
                source_line = next(
                    line.removeprefix("- ").replace("<chart-id>", selected_ledger.chart_id)
                    for line in block.splitlines()
                    if line.startswith(("- Source:", "- 数据来源\N{FULLWIDTH COLON}"))
                )
                lines = [title]
                headings = [line for line in block.splitlines() if line.startswith("## ")]
                for index, heading in enumerate(headings):
                    lines.extend((heading, source_line if index == 0 else evidence))
                    if heading == domains_heading:
                        lines.extend((f"### {module}", evidence))
                report = "\n\n".join(lines) + "\n"

                self.assertEqual(validate_markdown(report, selected_ledger, language, (module,)), [])

    def test_metadata_matches_validated_json_v2_workflow(self) -> None:
        text = OPENAI.read_text(encoding="utf-8")

        self.assertIn("$synastry-reading", text)
        self.assertIn("JSON v2", text)
        self.assertIn("evidence", text)
        self.assertIn("private", text.casefold())

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
