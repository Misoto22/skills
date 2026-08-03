from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EMAIL_SKILL = ROOT / "skills" / "email"
SCRIPT_DIR = EMAIL_SKILL / "scripts"
SKILL_PATH = EMAIL_SKILL / "SKILL.md"
POLICY_PATH = EMAIL_SKILL / "policy.example.json"
sys.path.insert(0, str(SCRIPT_DIR))

from email_policy import load_policy  # noqa: E402


class SkillContractTests(unittest.TestCase):
    def test_skill_frontmatter_and_required_workflow(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")

        self.assertRegex(text, r"\A---\nname: email\n")
        for phrase in (
            "draft",
            "send",
            "validate_message.py",
            "verify_readback.py",
            "untrusted",
            "sent_and_verified",
        ):
            self.assertIn(phrase, text)
        self.assertLess(len(text.splitlines()), 500)

    def test_required_support_files_exist_and_are_linked(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        required = (
            "agents/openai.yaml",
            "policy.example.json",
            "assets/signature.example.txt",
            "references/policy-schema.md",
            "references/security-model.md",
            "references/humanizer-integration.md",
        )

        for relative in required:
            self.assertTrue((EMAIL_SKILL / relative).is_file(), relative)
        for reference in required[3:]:
            self.assertIn(reference, text)

    def test_runtime_skill_contains_no_original_hardcodes(self) -> None:
        text_suffixes = {".md", ".json", ".py", ".txt", ".yaml", ".yml"}
        runtime = "\n".join(
            path.read_text(encoding="utf-8")
            for path in EMAIL_SKILL.rglob("*")
            if path.is_file() and path.suffix in text_suffixes
        )

        for forbidden in (
            "/Users/",
            "/home/",
            "smtp.gmail.com",
            "provider-specific mail command",
        ):
            self.assertNotIn(forbidden, runtime)

    def test_example_policy_is_safe_and_uses_reserved_domains(self) -> None:
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy = load_policy(POLICY_PATH)

        self.assertFalse(raw["authorization"]["allow_automated_send"])
        self.assertEqual(raw["authorization"]["default_mode"], "draft")
        self.assertTrue(
            all(
                domain.endswith(".test")
                for domain in policy["identity"]["internal_domains"]
            )
        )

    def test_openai_interface_supports_model_invocation_without_implied_send(self) -> None:
        text = (EMAIL_SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn("allow_implicit_invocation: true", text)
        self.assertIn("default_prompt:", text)
        self.assertIn("draft", text.lower())


if __name__ == "__main__":
    unittest.main()
