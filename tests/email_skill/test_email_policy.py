from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "email" / "scripts"))

from email_policy import (  # noqa: E402
    PolicyError,
    classify_address,
    discover_policy,
    load_policy,
    safe_default_policy,
)


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_policy(self, value: object, name: str = "policy.json") -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def valid_policy(self, **overrides: object) -> dict[str, object]:
        policy = safe_default_policy()
        policy["identity"] = {
            "sender_name": "Example Sender",
            "sender_address": "sender@example.test",
            "internal_domains": overrides.pop("internal_domains", ["example.test"]),
        }
        policy["recipients"] = {
            "allowed_external_domains": overrides.pop("allowed_external_domains", []),
            "required_cc_rules": overrides.pop("required_cc_rules", []),
            "reply_all": overrides.pop("reply_all", "review"),
        }
        policy["authorization"] = {
            "default_mode": overrides.pop("default_mode", "draft"),
            "allow_automated_send": overrides.pop("allow_automated_send", False),
            "automated_send_scopes": overrides.pop("automated_send_scopes", []),
        }
        if overrides:
            self.fail(f"Unused policy overrides: {sorted(overrides)}")
        return policy

    def test_safe_defaults_allow_draft_and_block_automated_send(self) -> None:
        policy = safe_default_policy()

        self.assertEqual(policy["authorization"]["default_mode"], "draft")
        self.assertFalse(policy["authorization"]["allow_automated_send"])
        self.assertEqual(policy["identity"]["internal_domains"], [])

    def test_discovery_prefers_explicit_then_environment_then_project(self) -> None:
        explicit = self.write_policy({}, "explicit.json")
        environment = self.write_policy({}, "environment.json")
        project = self.write_policy({}, ".agents/email-policy.json")

        self.assertEqual(
            discover_policy(
                explicit,
                self.root,
                {"EMAIL_SKILL_POLICY": str(environment)},
            ),
            explicit,
        )
        self.assertEqual(
            discover_policy(
                None,
                self.root,
                {"EMAIL_SKILL_POLICY": str(environment)},
            ),
            environment,
        )
        self.assertEqual(discover_policy(None, self.root, {}), project)

    def test_discovery_rejects_missing_explicit_path(self) -> None:
        missing = self.root / "missing.json"

        with self.assertRaisesRegex(PolicyError, "does not exist"):
            discover_policy(missing, self.root, {})

    def test_environment_path_is_expanded_without_mutating_environment(self) -> None:
        policy_path = self.write_policy({}, "environment.json")
        environ = {"EMAIL_SKILL_POLICY": str(policy_path)}

        self.assertEqual(discover_policy(None, self.root, environ), policy_path)
        self.assertEqual(environ, {"EMAIL_SKILL_POLICY": str(policy_path)})

    def test_unknown_policy_field_is_rejected(self) -> None:
        path = self.write_policy({"schema_version": 1, "typo": True})

        with self.assertRaisesRegex(PolicyError, "unknown field.*typo"):
            load_policy(path)

    def test_unknown_nested_field_is_rejected(self) -> None:
        policy = self.valid_policy()
        policy["identity"]["sender_domain"] = "example.test"
        path = self.write_policy(policy)

        with self.assertRaisesRegex(PolicyError, "identity.*sender_domain"):
            load_policy(path)

    def test_target_words_cannot_exceed_max_words(self) -> None:
        policy = self.valid_policy()
        policy["composition"]["target_words"] = 500
        policy["composition"]["max_words"] = 400
        path = self.write_policy(policy)

        with self.assertRaisesRegex(PolicyError, "target_words"):
            load_policy(path)

    def test_relative_signature_path_is_resolved_from_policy_directory(self) -> None:
        signature = self.root / "assets" / "signature.txt"
        signature.parent.mkdir()
        signature.write_text("Regards,\nExample Sender\n", encoding="utf-8")
        policy = self.valid_policy()
        policy["composition"]["signature_file"] = "assets/signature.txt"

        loaded = load_policy(self.write_policy(policy))

        self.assertEqual(
            loaded["composition"]["_resolved_signature_file"],
            str(signature.resolve()),
        )

    def test_missing_signature_file_is_rejected(self) -> None:
        policy = self.valid_policy()
        policy["composition"]["signature_file"] = "missing.txt"

        with self.assertRaisesRegex(PolicyError, "signature_file"):
            load_policy(self.write_policy(policy))

    def test_domains_are_normalized_and_deduplicated(self) -> None:
        policy = self.valid_policy(
            internal_domains=["Example.Test", "example.test"],
            allowed_external_domains=["Partner.Test", "partner.test"],
        )

        loaded = load_policy(self.write_policy(policy))

        self.assertEqual(loaded["identity"]["internal_domains"], ["example.test"])
        self.assertEqual(
            loaded["recipients"]["allowed_external_domains"],
            ["partner.test"],
        )

    def test_address_classification_uses_domain_not_display_name(self) -> None:
        policy = self.valid_policy(internal_domains=["example.test"])

        self.assertEqual(
            classify_address("Person <user@example.test>", policy),
            "internal",
        )
        self.assertEqual(
            classify_address("Example Staff <user@outside.test>", policy),
            "external",
        )
        self.assertEqual(classify_address("not-an-address", policy), "invalid")

    def test_sender_address_must_be_valid(self) -> None:
        policy = self.valid_policy()
        policy["identity"]["sender_address"] = "invalid"

        with self.assertRaisesRegex(PolicyError, "sender_address"):
            load_policy(self.write_policy(policy))

    def test_automated_scope_must_be_narrow(self) -> None:
        policy = self.valid_policy(
            allow_automated_send=True,
            automated_send_scopes=[
                {
                    "name": "too-broad",
                    "recipient_domains": [],
                    "max_recipients": 0,
                    "allow_attachments": True,
                    "allowed_sensitivity": ["normal", "sensitive"],
                }
            ],
        )

        with self.assertRaisesRegex(PolicyError, "recipient_domains"):
            load_policy(self.write_policy(policy))


if __name__ == "__main__":
    unittest.main()
