from __future__ import annotations

import io
import json
import re
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "astrology" / "skills" / "synastry-reading"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "shared"))

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


class MarkdownValidationTests(unittest.TestCase):
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

        changed_problems = validate_markdown(changed, ledger(), "en", ())
        accepted = validate_markdown(uncertain_report, uncertain, "en", ())

        self.assertTrue(any("measurement does not match" in item for item in changed_problems))
        self.assertEqual(accepted, [])

    def test_correct_index_entry_does_not_mask_an_altered_directional_display(self) -> None:
        overlay = next(item for item in ledger().evidence if item.kind == "overlay")
        altered = overlay.citation.replace("house 1", "house 12").replace("house 5", "house 12")
        report = valid_report() + f"\n{altered}\n\n{overlay.citation}\n"

        problems = validate_markdown(report, ledger(), "en", ())

        self.assertTrue(any("measurement does not match" in item for item in problems))


class ValidatedWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_validated_reading_write_is_exclusive_atomic_and_user_only(self) -> None:
        destination = self.directory / "synastry_reading_abc123def456.md"

        written = write_validated_markdown(valid_report(), ledger(), destination, "en", ())

        self.assertEqual(written, destination)
        self.assertEqual(written.read_text(encoding="utf-8"), valid_report())
        self.assertEqual(stat.S_IMODE(written.stat().st_mode), 0o600)
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            write_validated_markdown(valid_report(), ledger(), destination, "en", ())

    def test_invalid_markdown_and_source_json_destination_are_never_written(self) -> None:
        destination = self.directory / "invalid.md"
        with self.assertRaises(ReadingError):
            write_validated_markdown("# Incomplete", ledger(), destination, "en", ())
        self.assertFalse(destination.exists())

        with self.assertRaisesRegex(ValueError, "source JSON"):
            write_validated_markdown(
                valid_report(), ledger(), FIXTURES / "neutral.json", "en", (), overwrite=True
            )

    def test_explicit_overwrite_atomically_replaces_the_reading(self) -> None:
        destination = self.directory / "reading.md"
        write_validated_markdown(valid_report(), ledger(), destination, "en", ())
        changed = valid_report() + "\n"

        written = write_validated_markdown(changed, ledger(), destination, "en", (), overwrite=True)

        self.assertEqual(written.read_text(encoding="utf-8"), changed)

    def test_cli_returns_zero_or_two_without_a_traceback(self) -> None:
        draft = self.directory / "draft.md"
        draft.write_text(valid_report(), encoding="utf-8")
        output = self.directory / "final.md"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            valid_code = main([str(FIXTURES / "neutral.json"), str(draft), "--out", str(output)])
            invalid_code = main([str(FIXTURES / "neutral.json"), str(output)])

        self.assertEqual((valid_code, invalid_code), (0, 0))
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
