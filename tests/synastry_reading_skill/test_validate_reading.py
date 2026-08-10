from __future__ import annotations

import io
import json
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

import validate_synastry  # type: ignore[import-not-found]
from synastry_schema import attach_integrity  # type: ignore[import-not-found]
from validate_reading import (  # type: ignore[import-not-found]
    ReadingError,
    main,
    validate_markdown,
    write_validated_markdown,
)
from validate_synastry import EvidenceLedger, load_ledger  # type: ignore[import-not-found]

FIXTURES = Path(__file__).parent / "fixtures"
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


def ledger() -> EvidenceLedger:
    return load_ledger(FIXTURES / "neutral.json")


def valid_report(selected_modules: tuple[str, ...] = ()) -> str:
    item = ledger().evidence[0]
    lines = ["# Synastry reading"]
    for heading in UNIVERSAL_HEADINGS:
        lines.extend((f"## {heading}", item.citation))
        if heading == "Requested or context-specific domains":
            for module in selected_modules:
                lines.extend((f"### {module}", item.citation))
    return "\n\n".join(lines) + "\n"


def report_with(replacement: str) -> str:
    item = ledger().evidence[0]
    return valid_report().replace(item.citation, replacement, 1)


def ledger_with_limitations(language: str) -> EvidenceLedger:
    source = json.loads((FIXTURES / "neutral.json").read_text(encoding="utf-8"))
    source["configuration"]["language"] = language
    source["configuration"]["ephemeris_policy"] = "allow-moshier"
    source["provenance"].update(
        {
            "actual_backend": "moshier",
            "binding_version": "binding-v2",
            "return_flags": [2, 4],
            "software_version": "software-v1",
            "timezone_source": "timezone-source",
            "warnings": ["first warning", "second warning"],
        }
    )
    source["limitations"] = [
        {
            "affected_fields": ["charts[0].houses"],
            "code": "timing-window",
            "message": "Timing note: one source window crosses midnight.",
        },
        {
            "affected_fields": ["overlays"],
            "code": "missing-birth-time",
            "message": "One subject lacks a verified birth time.",
        },
    ]
    return load_ledger(attach_integrity(source))


def basis_entries(selected: EvidenceLedger, language: str) -> tuple[str, ...]:
    configuration = selected.configuration
    provenance = selected.provenance
    flags = ", ".join(str(value) for value in provenance["return_flags"])
    warnings = " | ".join(str(value) for value in provenance["warnings"])
    if language == "en":
        entries = (
            f"Source: validated synastry JSON v2, chart ID {selected.chart_id}",
            "Calculation and aspect profiles: "
            f"calculation {configuration['calculation_profile']}; "
            f"aspects {configuration['aspect_profile']}.",
            f"House system and configured orbs: {configuration['house_system']}; major 8°; minor 3°.",
            "Backend provenance: "
            f"requested {provenance['requested_backend']}; actual {provenance['actual_backend']}; "
            f"software {provenance['software_version']}; binding {provenance['binding_version']}; "
            f"timezone {provenance['timezone_source']}; return flags {flags}; "
            f"warnings {warnings or 'none'}.",
            "Explicit relationship context: Not stated",
        )
        limitation_label = "Data limitations: "
    else:
        entries = (
            f"数据来源\N{FULLWIDTH COLON}已验证的合盘 JSON v2"
            f"\N{FULLWIDTH SEMICOLON}图表 ID {selected.chart_id}",
            "计算与相位配置\N{FULLWIDTH COLON}"
            f"计算 {configuration['calculation_profile']}"
            f"\N{FULLWIDTH SEMICOLON}相位 {configuration['aspect_profile']}。",
            "宫位系统与相位容许度\N{FULLWIDTH COLON}"
            f"{configuration['house_system']}\N{FULLWIDTH SEMICOLON}主要相位 8°"
            f"\N{FULLWIDTH SEMICOLON}次要相位 3°。",
            "星历数据来源\N{FULLWIDTH COLON}"
            f"请求 {provenance['requested_backend']}"
            f"\N{FULLWIDTH SEMICOLON}实际 {provenance['actual_backend']}"
            f"\N{FULLWIDTH SEMICOLON}软件 {provenance['software_version']}"
            f"\N{FULLWIDTH SEMICOLON}绑定 {provenance['binding_version']}"
            f"\N{FULLWIDTH SEMICOLON}时区 {provenance['timezone_source']}"
            f"\N{FULLWIDTH SEMICOLON}返回标志 {flags}\N{FULLWIDTH SEMICOLON}"
            f"警告 {warnings or '无'}。",
            "用户明确提供的关系背景\N{FULLWIDTH COLON}未说明",
        )
        limitation_label = "数据限制\N{FULLWIDTH COLON}"
    return entries + tuple(
        f"{limitation_label}{limitation['message']}" for limitation in selected.limitations
    )


def report_with_basis(
    selected: EvidenceLedger,
    language: str,
    entries: tuple[str, ...],
) -> str:
    headings = UNIVERSAL_HEADINGS if language == "en" else CHINESE_UNIVERSAL_HEADINGS
    title = "# Synastry reading" if language == "en" else "# 双方合盘分析"
    lines = [title]
    for index, heading in enumerate(headings):
        content = (
            "\n".join(f"- {entry}" for entry in entries) if index == 0 else selected.evidence[0].citation
        )
        lines.extend((f"## {heading}", content))
    return "\n\n".join(lines) + "\n"


class MarkdownValidationTests(unittest.TestCase):
    def test_complete_ledger_derived_basis_blocks_are_structural_in_english_and_chinese(
        self,
    ) -> None:
        for language in ("en", "zh"):
            with self.subTest(language=language):
                selected = ledger_with_limitations(language)
                entries = basis_entries(selected, language)

                problems = validate_markdown(
                    report_with_basis(selected, language, entries),
                    selected,
                    language,
                    (),
                )

                self.assertEqual(problems, [])

    def test_non_source_metadata_appends_require_direct_evidence_in_both_languages(self) -> None:
        append_variants = {
            "en": (
                ", this may create an unusually fluent emotional bond.",
                " and this may create an unusually fluent emotional bond.",
                "; this may create an unusually fluent emotional bond.",
                ": this may create an unusually fluent emotional bond.",
                " \N{EM DASH} this may create an unusually fluent emotional bond.",
                "\n  This may create an unusually fluent emotional bond.",
            ),
            "zh": (
                "\N{FULLWIDTH COMMA}这可能带来格外流畅的情感联结。",
                "而且这可能带来格外流畅的情感联结。",
                "并且这可能带来格外流畅的情感联结。",
                "\N{FULLWIDTH SEMICOLON}这可能带来格外流畅的情感联结。",
                "\N{FULLWIDTH COLON}这可能带来格外流畅的情感联结。",
                "\N{EM DASH}这可能带来格外流畅的情感联结。",
                "\n  这可能带来格外流畅的情感联结。",
            ),
        }
        for language, suffixes in append_variants.items():
            selected = ledger_with_limitations(language)
            entries = basis_entries(selected, language)
            for suffix in suffixes:
                with self.subTest(language=language, suffix=suffix):
                    appended = (entries[4] + suffix,)

                    problems = validate_markdown(
                        report_with_basis(selected, language, appended),
                        selected,
                        language,
                        (),
                    )

                    self.assertTrue(
                        any("substantive paragraph lacks valid evidence" in problem for problem in problems)
                    )

    def test_unknown_evidence_and_changed_orb_are_rejected(self) -> None:
        problems = validate_markdown(
            report_with("[E-ASPECT-FFFF] orb 9.99°"),
            ledger(),
            language="en",
            selected_modules=(),
        )

        self.assertTrue(any("unknown evidence" in item for item in problems))
        self.assertTrue(any("measurement does not match" in item for item in problems))

    def test_neutral_context_rejects_unrequested_romance_heading(self) -> None:
        report = valid_report().replace(
            "## Overall synthesis",
            "### Romance and intimacy\n\n" + ledger().evidence[0].citation + "\n\n## Overall synthesis",
        )

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("unselected module" in item for item in problems))

    def test_selected_module_is_required_and_accepted_without_context_inference(self) -> None:
        missing = validate_markdown(valid_report(), ledger(), "en", ("Romance and intimacy",))
        accepted = validate_markdown(
            valid_report(("Romance and intimacy",)), ledger(), "en", ("Romance and intimacy",)
        )

        self.assertTrue(any("selected module is missing" in item for item in missing))
        self.assertEqual(accepted, [])

    def test_universal_heading_order_and_placeholders_are_rejected(self) -> None:
        reversed_headings = (
            valid_report()
            .replace(
                "## Repeated interaction patterns",
                "## TEMP",
            )
            .replace(
                "## Reciprocity and asymmetry",
                "## Repeated interaction patterns",
            )
            .replace("## TEMP", "## Reciprocity and asymmetry")
        )
        placeholder = valid_report() + "\n<replace this>\n"

        order_problems = validate_markdown(reversed_headings, ledger(), "en", ())
        placeholder_problems = validate_markdown(placeholder, ledger(), "en", ())

        self.assertTrue(any("heading order" in item for item in order_problems))
        self.assertTrue(any("placeholder" in item for item in placeholder_problems))

    def test_scores_and_deterministic_prediction_phrases_are_rejected(self) -> None:
        scored = valid_report() + "\nCompatibility score: 92%\n"
        predicted = valid_report() + "\nThis relationship will definitely last.\n"

        score_problems = validate_markdown(scored, ledger(), "en", ())
        prediction_problems = validate_markdown(predicted, ledger(), "en", ())

        self.assertTrue(any("compatibility score" in item for item in score_problems))
        self.assertTrue(any("deterministic prediction" in item for item in prediction_problems))

    def test_exact_display_is_required_but_uncertain_evidence_range_is_accepted(self) -> None:
        changed_citation = re.sub(r"orb \d+(?:\.\d+)?°", "orb 9.98°", ledger().evidence[0].citation, count=1)
        changed = report_with(changed_citation)
        source = json.loads((FIXTURES / "neutral.json").read_text(encoding="utf-8"))
        source["subjects"][0]["birth"] = {
            "mode": "window",
            "utc_start": "1990-03-14T06:00:00Z",
            "utc_end": "1990-03-14T08:00:00Z",
        }
        source["charts"][0] = {
            "subject_id": "subject-a",
            "precision_mode": "window",
            "positions": {
                "Sun": {
                    "longitude_range": {
                        "start_degrees": 9.0,
                        "end_degrees": 11.0,
                        "wraps_zero": False,
                    },
                    "max_span_degrees": 2.0,
                    "signs": ["Ari"],
                    "retrograde_states": [False],
                }
            },
            "derived": {},
        }
        source["aspects"] = [
            {
                "source_subject_id": "subject-a",
                "target_subject_id": "subject-b",
                "source_body": "Sun",
                "target_body": "Moon",
                "kind": "trine",
                "certainty": "confirmed",
                "orb_range_degrees": {"minimum_degrees": 0.2, "maximum_degrees": 0.8},
            }
        ]
        source["overlays"] = []
        uncertain = load_ledger(attach_integrity(source))
        uncertain_report = valid_report().replace(
            ledger().evidence[0].citation, uncertain.evidence[0].citation
        )
        changed_range = uncertain_report.replace("0.2°-0.8°", "0.2°\N{EN DASH}0.9°", 1)
        changed_certainty = uncertain_report.replace("certainty confirmed", "certainty possible", 1)

        changed_problems = validate_markdown(changed, ledger(), "en", ())
        accepted = validate_markdown(uncertain_report, uncertain, "en", ())
        range_problems = validate_markdown(changed_range, uncertain, "en", ())
        certainty_problems = validate_markdown(changed_certainty, uncertain, "en", ())

        self.assertTrue(any("measurement does not match" in item for item in changed_problems))
        self.assertEqual(accepted, [])
        self.assertTrue(any("measurement does not match" in item for item in range_problems))
        self.assertTrue(any("claim does not match" in item for item in certainty_problems))

    def test_correct_index_entry_does_not_mask_an_altered_directional_display(self) -> None:
        overlay = next(item for item in ledger().evidence if item.kind == "overlay")
        altered = overlay.citation.replace("house 1", "house 12").replace("house 5", "house 12")
        report = valid_report() + f"\n{altered}\n\n{overlay.citation}\n"

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("measurement does not match" in item for item in problems))

    def test_valid_directional_overlay_display_is_accepted(self) -> None:
        overlay = next(item for item in ledger().evidence if item.kind == "overlay")
        aspect = ledger().evidence[0]
        report = valid_report().replace(aspect.citation, overlay.citation)

        self.assertEqual(validate_markdown(report, ledger(), "en", ()), [])

    def test_evidence_index_does_not_mask_an_uncited_substantive_section(self) -> None:
        citation = ledger().evidence[0].citation
        report = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            "## Repeated interaction patterns\n\nThis may create an easier rhythm.",
        )

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("substantive paragraph" in item for item in problems))

    def test_section_evidence_cannot_bind_a_conditional_paragraph(self) -> None:
        citation = ledger().evidence[0].citation
        report = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nThis may create an easier rhythm.\n\n{citation}",
        )

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("substantive paragraph lacks valid evidence" in item for item in problems))

    def test_only_an_exact_standalone_limitation_may_omit_evidence(self) -> None:
        citation = ledger().evidence[0].citation
        statement = (
            "The source does not support a confident money-specific interpretation "
            "because no directly relevant measurement is present."
        )
        standalone = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\n{statement}",
        )

        self.assertEqual(validate_markdown(standalone, ledger(), "en", ()), [])

        appended = standalone.replace(
            statement,
            f"{statement} This may create an easier rhythm.",
        )
        appended_problems = validate_markdown(appended, ledger(), "en", ())

        self.assertTrue(
            any("substantive paragraph lacks valid evidence" in item for item in appended_problems)
        )

        evidence_id = ledger().evidence[0].id
        cited = appended.replace(
            "This may create an easier rhythm.",
            f"This may create an easier rhythm. [{evidence_id}]",
        )

        self.assertEqual(validate_markdown(cited, ledger(), "en", ()), [])

    def test_metadata_and_index_exemptions_require_exact_standalone_entries(self) -> None:
        citation = ledger().evidence[0].citation
        basis_entry = "Source: attached JSON."
        standalone = valid_report().replace(citation, basis_entry, 1)

        self.assertEqual(validate_markdown(standalone, ledger(), "en", ()), [])
        for source in (
            "Source: pasted JSON.",
            f"Source: validated synastry JSON v2, chart ID {ledger().chart_id}.",
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    validate_markdown(standalone.replace(basis_entry, source), ledger(), "en", ()),
                    [],
                )

        bypasses = {
            "sentence append": standalone.replace(
                basis_entry, f"{basis_entry} This may create an unusually fluent emotional bond."
            ),
            "conjunction append": standalone.replace(
                basis_entry,
                "Source: attached JSON and this may create an unusually fluent emotional bond.",
            ),
            "semicolon append": standalone.replace(
                basis_entry,
                "Source: attached JSON; this may create an unusually fluent emotional bond.",
            ),
            "colon append": standalone.replace(
                basis_entry,
                "Source: attached JSON: this may create an unusually fluent emotional bond.",
            ),
            "dash append": standalone.replace(
                basis_entry,
                "Source: attached JSON — this may create an unusually fluent emotional bond.",
            ),
            "hyphen append": standalone.replace(
                basis_entry,
                "Source: attached JSON - this may create an unusually fluent emotional bond.",
            ),
            "mismatched chart ID": standalone.replace(
                basis_entry,
                "Source: validated synastry JSON v2, chart ID deadbeefcafe.",
            ),
            "basis interpretation": standalone.replace(
                basis_entry, "This may create an unusually fluent emotional bond."
            ),
            "index interpretation": valid_report().replace(
                f"## Evidence index\n\n{citation}",
                "## Evidence index\n\nThis may create an unusually fluent emotional bond.",
            ),
        }
        for name, report in bypasses.items():
            with self.subTest(name=name):
                problems = validate_markdown(report, ledger(), "en", ())

                self.assertTrue(
                    any("substantive paragraph lacks valid evidence" in item for item in problems)
                )

        evidence_id = ledger().evidence[0].id
        cited = standalone.replace(
            basis_entry,
            f"{basis_entry} This may create an unusually fluent emotional bond. [{evidence_id}]",
        )

        self.assertEqual(validate_markdown(cited, ledger(), "en", ()), [])

    def test_fenced_and_inline_content_cannot_supply_structure_or_evidence(self) -> None:
        citation = ledger().evidence[0].citation
        report = valid_report().replace("## Reciprocity and asymmetry", "## Missing section")
        report = report.replace(
            f"## Repeated interaction patterns\n\n{citation}",
            "## Repeated interaction patterns\n\nThis may create an easier rhythm. `" + citation + "`",
        )
        report += f"\n```markdown\n## Reciprocity and asymmetry\n{citation}\n```\n"

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("required universal heading" in item for item in problems))
        self.assertTrue(any("substantive paragraph" in item for item in problems))

    def test_unclosed_comments_quoted_fences_and_multiline_code_spans_are_nonrendered(self) -> None:
        citation = ledger().evidence[0].citation
        commented = "# Synastry reading\n\n<!-- never closed\n" + valid_report()
        quoted_code = "\n\n".join(f"## {heading}" for heading in UNIVERSAL_HEADINGS)
        quoted_code += f"\n\n> ```text\n> {citation}\n> ```\n"
        multiline_code = valid_report().replace(
            f"## Requested or context-specific domains\n\n{citation}",
            "## Requested or context-specific domains\n\n"
            "`hidden\n### Romance and intimacy\nstill hidden`\n\n"
            f"{citation}",
        )

        comment_problems = validate_markdown(commented, ledger(), "en", ())
        quoted_problems = validate_markdown(quoted_code, ledger(), "en", ())
        span_problems = validate_markdown(multiline_code, ledger(), "en", ("Romance and intimacy",))

        self.assertTrue(any("required universal heading" in item for item in comment_problems))
        self.assertTrue(any("no inline evidence" in item for item in quoted_problems))
        self.assertTrue(any("selected module is missing" in item for item in span_problems))

    def test_a_quoted_fence_ends_when_its_blockquote_container_ends(self) -> None:
        citation = ledger().evidence[0].citation
        report = valid_report().replace(
            f"## Requested or context-specific domains\n\n{citation}",
            f"## Requested or context-specific domains\n\n> ```text\n> hidden\n\n"
            f"### Romance and intimacy\n\n{citation}",
        )

        problems = validate_markdown(report, ledger(), "en", ("Romance and intimacy",))

        self.assertEqual(problems, [])

    def test_indented_code_cannot_supply_section_evidence(self) -> None:
        citation = ledger().evidence[0].citation
        report = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nThis may create an easier rhythm.\n\n    {citation}",
        )

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("substantive paragraph" in item for item in problems))

    def test_paragraph_claim_fields_must_match_its_bound_evidence(self) -> None:
        aspect = next(item for item in ledger().evidence if item.kind == "aspect")
        data = aspect.data
        wrong_direction = (
            f"This may show {data['target_subject_id']} {data['source_body']} -> "
            f"{data['source_subject_id']} {data['target_body']} as confirmed, {aspect.id}. "
            f"[{aspect.id}]"
        )
        citation = ledger().evidence[0].citation
        report = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\n{wrong_direction}\n\n{citation}",
        )

        problems = validate_markdown(report, ledger(), "en", ())

        altered_body = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nThis may emphasize Venus. [{aspect.id}]\n\n{citation}",
        )
        body_problems = validate_markdown(altered_body, ledger(), "en", ())
        ownership_variant = valid_report().replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nMoon of subject-a may flow from subject-a to subject-b. "
            f"[{aspect.id}]\n\n{citation}",
        )
        ownership_problems = validate_markdown(ownership_variant, ledger(), "en", ())

        self.assertTrue(any("claim does not match paragraph evidence" in item for item in problems))
        self.assertTrue(any("claim does not match paragraph evidence" in item for item in body_problems))
        self.assertTrue(any("claim does not match paragraph evidence" in item for item in ownership_problems))

    def test_modules_must_be_selected_canonical_headings_inside_the_domains_section(self) -> None:
        citation = ledger().evidence[0].citation
        fenced = valid_report() + f"\n```\n### Romance and intimacy\n{citation}\n```\n"
        misplaced = valid_report().replace(
            "## Repeated interaction patterns",
            f"### Romance and intimacy\n\n{citation}\n\n## Repeated interaction patterns",
        )
        alias = valid_report(("Attraction, romance, and intimacy",))

        fenced_problems = validate_markdown(fenced, ledger(), "en", ("Romance and intimacy",))
        misplaced_problems = validate_markdown(misplaced, ledger(), "en", ("Romance and intimacy",))
        alias_problems = validate_markdown(alias, ledger(), "en", ("Attraction, romance, and intimacy",))

        self.assertTrue(any("selected module is missing" in item for item in fenced_problems))
        self.assertTrue(any("outside" in item for item in misplaced_problems))
        self.assertTrue(any("canonical module" in item for item in alias_problems))

    def test_sensitive_modules_at_level_two_or_four_cannot_bypass_authorization(self) -> None:
        citation = ledger().evidence[0].citation
        level_two = valid_report().replace(
            "## Overall synthesis",
            f"## Romance and intimacy\n\n{citation}\n\n## Overall synthesis",
        )
        level_four = valid_report().replace(
            "## Overall synthesis",
            f"#### Romance and intimacy\n\n{citation}\n\n## Overall synthesis",
        )

        level_two_problems = validate_markdown(level_two, ledger(), "en", ())
        level_four_problems = validate_markdown(level_four, ledger(), "en", ())

        self.assertTrue(any("module" in item for item in level_two_problems))
        self.assertTrue(any("module" in item for item in level_four_problems))

    def test_higher_level_heading_resets_the_domains_section_ancestry(self) -> None:
        citation = ledger().evidence[0].citation
        report = valid_report().replace(
            "## Overall synthesis",
            f"# Separate document\n\n### Romance and intimacy\n\n{citation}\n\n## Overall synthesis",
        )

        problems = validate_markdown(report, ledger(), "en", ("Romance and intimacy",))

        self.assertTrue(any("outside" in item for item in problems))
        self.assertTrue(any("selected module is missing" in item for item in problems))

    def test_precision_language_and_conditional_wording_bypasses_are_rejected(self) -> None:
        aspect = next(item for item in ledger().evidence if item.kind == "aspect")
        overlay = next(item for item in ledger().evidence if item.kind == "overlay")
        base = valid_report()
        score = base + f"\nThis may rate compatibility at 92 points. [{aspect.id}]\n"
        prediction = base + f"\nThey are going to marry. [{aspect.id}]\n"
        measurement = base + f"\nThis may be exact at 1.234 degrees. [{aspect.id}]\n"
        house = base + f"\nThis may activate house 12. [{overlay.id}]\n"
        citation = ledger().evidence[0].citation
        unconditional = base.replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nThis creates emotional ease. [{aspect.id}]\n\n{citation}",
        )
        score_word = base + f"\nThis may rate compatibility at 92 percent. [{aspect.id}]\n"
        shall_predict = base + f"\nThey shall marry. [{aspect.id}]\n"
        short_degree = base + f"\nThis may be exact at 9.99 deg. [{aspect.id}]\n"
        word_house = base + f"\nThis may activate the twelfth house. [{overlay.id}]\n"
        incidental_may = base.replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nThis proves compatibility and communication may improve. "
            f"[{aspect.id}]\n\n{citation}",
        )
        alternative_may = base.replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nThis proves compatibility or communication may improve. "
            f"[{aspect.id}]\n\n{citation}",
        )
        concessive_may = base.replace(
            f"## Repeated interaction patterns\n\n{citation}",
            "## Repeated interaction patterns\n\n"
            "This proves compatibility, though communication may improve. "
            f"[{aspect.id}]\n\n{citation}",
        )
        participle_claim = base.replace(
            f"## Repeated interaction patterns\n\n{citation}",
            f"## Repeated interaction patterns\n\nCommunication may improve, proving compatibility. "
            f"[{aspect.id}]\n\n{citation}",
        )

        self.assertTrue(
            any("compatibility score" in item for item in validate_markdown(score, ledger(), "en", ()))
        )
        self.assertTrue(
            any(
                "deterministic prediction" in item
                for item in validate_markdown(prediction, ledger(), "en", ())
            )
        )
        self.assertTrue(
            any(
                "measurement does not match" in item
                for item in validate_markdown(measurement, ledger(), "en", ())
            )
        )
        self.assertTrue(
            any("measurement does not match" in item for item in validate_markdown(house, ledger(), "en", ()))
        )
        self.assertTrue(
            any(
                "conditional language" in item
                for item in validate_markdown(unconditional, ledger(), "en", ())
            )
        )
        self.assertTrue(
            any("compatibility score" in item for item in validate_markdown(score_word, ledger(), "en", ()))
        )
        self.assertTrue(
            any(
                "deterministic prediction" in item
                for item in validate_markdown(shall_predict, ledger(), "en", ())
            )
        )
        self.assertTrue(
            any(
                "measurement does not match" in item
                for item in validate_markdown(short_degree, ledger(), "en", ())
            )
        )
        self.assertTrue(
            any(
                "measurement does not match" in item
                for item in validate_markdown(word_house, ledger(), "en", ())
            )
        )
        self.assertTrue(
            any(
                "conditional language" in item
                for item in validate_markdown(incidental_may, ledger(), "en", ())
            )
        )
        for report in (alternative_may, concessive_may, participle_claim):
            with self.subTest(report=report):
                self.assertTrue(
                    any(
                        "conditional language" in item
                        for item in validate_markdown(report, ledger(), "en", ())
                    )
                )


class ValidatedWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_output_basename_is_bound_to_the_validated_chart_id(self) -> None:
        for basename in (
            "reading.md",
            "synastry_reading_ABC123DEF456.md",
            "synastry_reading_deadbeefcafe.md",
            "synastry_reading_abc123def456.md.extra",
        ):
            with self.subTest(basename=basename):
                destination = self.directory / basename

                with self.assertRaisesRegex(ValueError, "basename.*chart_id"):
                    write_validated_markdown(valid_report(), ledger(), destination, "en", ())

                self.assertFalse(destination.exists())

        destination = self.directory / "nested" / "synastry_reading_abc123def456.md"

        self.assertEqual(
            write_validated_markdown(valid_report(), ledger(), destination, "en", ()),
            destination,
        )

    def test_validated_reading_write_is_exclusive_atomic_and_user_only(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"

        written = write_validated_markdown(valid_report(), ledger(), destination, "en", ())

        self.assertEqual(written, destination)
        self.assertEqual(written.read_text(encoding="utf-8"), valid_report())
        self.assertEqual(stat.S_IMODE(written.stat().st_mode), 0o600)
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            write_validated_markdown(valid_report(), ledger(), destination, "en", ())

    def test_invalid_markdown_and_source_json_destination_are_never_written(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        with self.assertRaises(ReadingError):
            write_validated_markdown("# Incomplete", ledger(), destination, "en", ())
        self.assertFalse(destination.exists())

        with self.assertRaisesRegex(ValueError, "basename.*chart_id"):
            write_validated_markdown(
                valid_report(), ledger(), FIXTURES / "neutral.json", "en", (), overwrite=True
            )

    def test_explicit_overwrite_atomically_replaces_the_reading(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        write_validated_markdown(valid_report(), ledger(), destination, "en", ())
        changed = valid_report() + "\n"

        written = write_validated_markdown(changed, ledger(), destination, "en", (), overwrite=True)

        self.assertEqual(written.read_text(encoding="utf-8"), changed)

    def test_cli_returns_zero_or_two_without_a_traceback(self) -> None:
        draft = self.directory / "draft.md"
        draft.write_text(valid_report(), encoding="utf-8")
        output = self.directory / "synastry_reading_abc123def456.md"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            valid_code = main([str(FIXTURES / "neutral.json"), str(draft), "--out", str(output)])
            invalid_code = main([str(FIXTURES / "neutral.json"), str(output)])

        self.assertEqual((valid_code, invalid_code), (0, 0))
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_cli_errors_do_not_echo_paths_or_untrusted_reading_text(self) -> None:
        secret = "birth_1990-03-14_delete-files"
        missing = self.directory / f"{secret}.md"
        source = FIXTURES / "neutral.json"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            missing_code = main([str(source), str(missing)])

        draft = self.directory / "draft.md"
        draft.write_text(f"# {secret}\n\n[E-ASPECT-FFFF]", encoding="utf-8")
        with redirect_stdout(stdout), redirect_stderr(stderr):
            invalid_code = main([str(source), str(draft)])

        self.assertEqual((missing_code, invalid_code), (2, 2))
        self.assertNotIn(secret, stderr.getvalue())
        self.assertNotIn(str(missing), stderr.getvalue())

    def test_source_identity_rejects_hard_links_and_survives_source_symlink_swap(self) -> None:
        source = self.directory / "source.json"
        source.write_bytes((FIXTURES / "neutral.json").read_bytes())
        source_link = self.directory / "source-link.json"
        source_link.symlink_to(source)
        selected = load_ledger(source_link)
        source_link.unlink()
        decoy = self.directory / "decoy.json"
        decoy.write_bytes((FIXTURES / "neutral.json").read_bytes())
        source_link.symlink_to(decoy)
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.hardlink_to(source)

        with self.assertRaisesRegex(ValueError, "source JSON"):
            write_validated_markdown(valid_report(), selected, destination, "en", (), overwrite=True)

    def test_atomic_install_restores_source_alias_swapped_after_the_last_precheck(self) -> None:
        source = self.directory / "source.json"
        source.write_bytes((FIXTURES / "neutral.json").read_bytes())
        selected = load_ledger(source)
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")
        original_identity = validate_synastry._path_identity
        destination_checks = 0

        def swap_after_check(path: Path) -> tuple[int, int] | None:
            nonlocal destination_checks
            result = original_identity(path)
            if Path(path) == destination:
                destination_checks += 1
                if destination_checks == 2:
                    destination.unlink()
                    destination.hardlink_to(source)
            return result

        with (
            patch("validate_synastry._path_identity", side_effect=swap_after_check),
            self.assertRaisesRegex(ValueError, "source JSON"),
        ):
            write_validated_markdown(valid_report(), selected, destination, "en", (), overwrite=True)

        self.assertTrue(destination.samefile(source))
        self.assertEqual(source.read_bytes(), (FIXTURES / "neutral.json").read_bytes())

    def test_symlink_swapped_at_exchange_boundary_is_restored_after_rejection(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")
        symlink_target = self.directory / "raced-reading.md"
        symlink_target.write_text("raced reading", encoding="utf-8")
        original_exchange = validate_synastry._exchange_paths
        exchanges = 0

        def swap_then_exchange(first: Path, second: Path) -> None:
            nonlocal exchanges
            exchanges += 1
            if exchanges == 1:
                destination.unlink()
                destination.symlink_to(symlink_target)
            original_exchange(first, second)

        with (
            patch("validate_synastry._exchange_paths", side_effect=swap_then_exchange),
            self.assertRaises(OSError),
        ):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        self.assertTrue(destination.is_symlink())
        self.assertEqual(destination.readlink(), symlink_target)
        self.assertEqual(symlink_target.read_text(encoding="utf-8"), "raced reading")

    def test_directory_swapped_at_exchange_boundary_is_restored_after_rejection(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")
        raced_directory = self.directory / "raced-directory"
        raced_directory.mkdir()
        sentinel = raced_directory / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        original_exchange = validate_synastry._exchange_paths
        exchanges = 0

        def swap_then_exchange(first: Path, second: Path) -> None:
            nonlocal exchanges
            exchanges += 1
            if exchanges == 1:
                destination.unlink()
                raced_directory.rename(destination)
            original_exchange(first, second)

        with (
            patch("validate_synastry._exchange_paths", side_effect=swap_then_exchange),
            self.assertRaises(OSError),
        ):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        self.assertTrue(destination.is_dir())
        self.assertEqual((destination / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_overwrite_never_exchanges_or_replaces_a_directory(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")

        with self.assertRaises(OSError):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        self.assertTrue(destination.is_dir())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_rollback_does_not_depend_on_a_second_exchange_or_discard_displaced_data(self) -> None:
        source = self.directory / "source.json"
        source.write_bytes((FIXTURES / "neutral.json").read_bytes())
        selected = load_ledger(source)
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")
        original_identity = validate_synastry._path_identity
        original_exchange = validate_synastry._exchange_paths
        destination_checks = 0
        exchanges = 0

        def swap_after_check(path: Path) -> tuple[int, int] | None:
            nonlocal destination_checks
            result = original_identity(path)
            if Path(path) == destination:
                destination_checks += 1
                if destination_checks == 2:
                    destination.unlink()
                    destination.hardlink_to(source)
            return result

        def fail_a_rollback(first: Path, second: Path) -> None:
            nonlocal exchanges
            exchanges += 1
            if exchanges > 1:
                raise OSError("forced rollback failure")
            original_exchange(first, second)

        with (
            patch("validate_synastry._path_identity", side_effect=swap_after_check),
            patch("validate_synastry._exchange_paths", side_effect=fail_a_rollback),
            self.assertRaisesRegex(ValueError, "source JSON"),
        ):
            write_validated_markdown(valid_report(), selected, destination, "en", (), overwrite=True)

        self.assertTrue(destination.samefile(source))
        self.assertEqual(source.read_bytes(), (FIXTURES / "neutral.json").read_bytes())

    def test_failed_rollback_retains_the_displaced_regular_file(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")
        previous_identity = validate_synastry._path_identity(destination)
        original_identity = validate_synastry._path_identity
        original_exchange = validate_synastry._exchange_paths
        exchanges = 0

        def report_changed_displaced_identity(path: Path) -> tuple[int, int] | None:
            result = original_identity(path)
            if Path(path).name.startswith(".synastry-reading-") and result == previous_identity:
                return (0, 0)
            return result

        def fail_a_second_exchange(first: Path, second: Path) -> None:
            nonlocal exchanges
            exchanges += 1
            if exchanges > 1:
                raise OSError("forced rollback exchange failure")
            original_exchange(first, second)

        with (
            patch("validate_synastry._path_identity", side_effect=report_changed_displaced_identity),
            patch("validate_synastry._exchange_paths", side_effect=fail_a_second_exchange),
            patch("validate_synastry.os.replace", side_effect=OSError("forced restore failure")),
            self.assertRaises(OSError),
        ):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        retained = [
            path
            for path in self.directory.iterdir()
            if path.is_file() and path.read_text(encoding="utf-8") == "previous reading"
        ]
        self.assertTrue(retained)
        installed = destination.read_bytes() if destination.is_file() else None
        self.assertNotEqual(installed, valid_report().encode("utf-8"))

    def test_failed_recovery_move_restores_the_displaced_file_by_exchange(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")
        previous_identity = validate_synastry._path_identity(destination)
        original_identity = validate_synastry._path_identity

        def report_changed_displaced_identity(path: Path) -> tuple[int, int] | None:
            result = original_identity(path)
            if Path(path).name.startswith(".synastry-reading-") and result == previous_identity:
                return (0, 0)
            return result

        with (
            patch("validate_synastry._path_identity", side_effect=report_changed_displaced_identity),
            patch("validate_synastry.os.replace", side_effect=OSError("forced direct restore failure")),
            patch("validate_synastry.os.rename", side_effect=OSError("forced recovery move failure")),
            self.assertRaises(OSError),
        ):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        self.assertEqual(destination.read_text(encoding="utf-8"), "previous reading")

    def test_recovery_storage_failure_occurs_before_exchange_without_mutation(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")

        with (
            patch(
                "validate_synastry._allocate_recovery_directory",
                side_effect=OSError("forced recovery allocation failure"),
            ),
            self.assertRaises(OSError),
        ):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        self.assertEqual(destination.read_text(encoding="utf-8"), "previous reading")
        self.assertEqual(list(self.directory.glob(".synastry-*")), [])

    def test_unsupported_atomic_overwrite_fails_without_mutating_the_destination(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"
        destination.write_text("previous reading", encoding="utf-8")

        with (
            patch(
                "validate_synastry._exchange_paths",
                side_effect=OSError("atomic overwrite unsupported"),
            ),
            self.assertRaises(OSError),
        ):
            write_validated_markdown(valid_report(), ledger(), destination, "en", (), overwrite=True)

        self.assertEqual(destination.read_text(encoding="utf-8"), "previous reading")
        self.assertEqual(list(self.directory.glob(".synastry-*")), [])

    def test_output_collision_cli_error_does_not_echo_destination(self) -> None:
        secret_directory = self.directory / "secret-reading-name"
        secret_directory.mkdir()
        destination = secret_directory / "synastry_reading_abc123def456.md"
        destination.write_text("existing", encoding="utf-8")
        draft = self.directory / "draft.md"
        draft.write_text(valid_report(), encoding="utf-8")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main([str(FIXTURES / "neutral.json"), str(draft), "--out", str(destination)])

        self.assertEqual(code, 2)
        self.assertNotIn(str(destination), stderr.getvalue())

    def test_reading_validator_script_runs_directly_from_the_skill_directory(self) -> None:
        draft = self.directory / "draft.md"
        draft.write_text(valid_report(), encoding="utf-8")
        script = SKILL / "scripts" / "validate_reading.py"

        completed = subprocess.run(
            [sys.executable, str(script), str(FIXTURES / "neutral.json"), str(draft)],
            cwd=SKILL,
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_attached_source_and_draft_stdin_preserve_only_the_final_markdown(self) -> None:
        script = SKILL / "scripts" / "validate_reading.py"
        destination = self.directory / "synastry_reading_abc123def456.md"

        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                str(FIXTURES / "neutral.json"),
                "-",
                "--out",
                str(destination),
            ],
            cwd=SKILL,
            input=valid_report(),
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report())
        self.assertEqual(list(self.directory.iterdir()), [destination])

    def test_pasted_source_failure_and_retry_are_stateless(self) -> None:
        script = SKILL / "scripts" / "validate_reading.py"
        destination = self.directory / "synastry_reading_abc123def456.md"
        source = json.loads((FIXTURES / "neutral.json").read_text(encoding="utf-8"))

        failed = subprocess.run(
            [sys.executable, str(script), "-", "-", "--out", str(destination)],
            cwd=SKILL,
            input=json.dumps({"source": source, "draft": "# Invalid"}),
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(failed.returncode, 2)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.directory.iterdir()), [])

        retried = subprocess.run(
            [sys.executable, str(script), "-", "-", "--out", str(destination)],
            cwd=SKILL,
            input=json.dumps({"source": source, "draft": valid_report()}),
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual(destination.read_text(encoding="utf-8"), valid_report())
        self.assertEqual(list(self.directory.iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
