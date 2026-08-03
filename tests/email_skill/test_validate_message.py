from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "skills" / "email" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from email_bundle import BundleError, artifact_hashes, load_bundle  # noqa: E402
from email_policy import safe_default_policy  # noqa: E402
from render_email import render_html  # noqa: E402
from validate_message import validate_bundle  # noqa: E402


class ValidateMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def policy(self, **overrides: object) -> dict[str, object]:
        policy = copy.deepcopy(safe_default_policy())
        policy["identity"] = {
            "sender_name": "Example Sender",
            "sender_address": "sender@example.test",
            "internal_domains": ["example.test"],
        }
        policy["recipients"] = {
            "allowed_external_domains": overrides.pop("allowed_external_domains", []),
            "required_cc_rules": overrides.pop("required_cc_rules", []),
            "reply_all": overrides.pop("reply_all", "review"),
        }
        policy["authorization"] = {
            "default_mode": "draft",
            "allow_automated_send": overrides.pop("allow_automated_send", False),
            "automated_send_scopes": overrides.pop("automated_send_scopes", []),
        }
        policy["composition"] = {
            "greeting_style": overrides.pop("greeting_style", "first-name"),
            "target_words": overrides.pop("target_words", None),
            "max_words": overrides.pop("max_words", None),
            "signature_file": None,
            "humanizer": "optional",
        }
        if overrides:
            self.fail(f"Unused policy overrides: {sorted(overrides)}")
        return policy

    def bundle(
        self,
        *,
        name: str = "message",
        mode: str = "draft",
        sender: str = "sender@example.test",
        to: list[str] | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        authorization: dict[str, object] | None = None,
        body: str = "Dear Owner,\n\nThe update is ready.\n",
        html: str | None = None,
        protected_facts: list[str] | None = None,
        reply_candidates: list[str] | None = None,
        transport: dict[str, object] | None = None,
        sensitivity: str = "normal",
        attachments: list[dict[str, object]] | None = None,
        extra_manifest: dict[str, object] | None = None,
    ) -> Path:
        directory = self.root / name
        directory.mkdir()
        (directory / "subject.txt").write_text("Project update\n", encoding="utf-8")
        (directory / "body.txt").write_text(body, encoding="utf-8")
        (directory / "body.html").write_text(
            html if html is not None else render_html(body),
            encoding="utf-8",
        )
        manifest: dict[str, object] = {
            "schema_version": 1,
            "mode": mode,
            "sender": {"name": "Example Sender", "address": sender},
            "recipients": {
                "to": to if to is not None else ["owner@example.test"],
                "cc": cc if cc is not None else [],
                "bcc": bcc if bcc is not None else [],
            },
            "subject_file": "subject.txt",
            "text_body_file": "body.txt",
            "html_body_file": "body.html",
            "authorization": authorization
            if authorization is not None
            else {"source": "direct_user" if mode == "send" else "none", "scope": None},
            "protected_facts": protected_facts if protected_facts is not None else [],
            "sensitivity": sensitivity,
            "reply": {
                "message_id": None,
                "thread_id": None,
                "candidate_recipients": reply_candidates if reply_candidates is not None else [],
            },
            "transport": transport
            if transport is not None
            else {"supports_readback": True, "supports_attachment_readback": True},
            "attachments": attachments if attachments is not None else [],
        }
        if extra_manifest:
            manifest.update(extra_manifest)
        (directory / "message.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return directory

    @staticmethod
    def messages(result: dict[str, object]) -> str:
        return "\n".join(item["message"] for item in result["findings"])

    def test_ambiguous_intent_stays_draft(self) -> None:
        result = validate_bundle(
            self.bundle(mode="draft", authorization={"source": "none", "scope": None}),
            self.policy(),
        )

        self.assertEqual(result["status"], "draft_ready")

    def test_draft_without_configured_identity_remains_usable(self) -> None:
        result = validate_bundle(
            self.bundle(
                mode="draft",
                sender="",
                authorization={"source": "none", "scope": None},
            ),
            safe_default_policy(),
        )

        self.assertEqual(result["status"], "draft_ready")
        self.assertIn("identity", self.messages(result))

    def test_send_without_policy_identity_is_blocked(self) -> None:
        result = validate_bundle(self.bundle(mode="send"), safe_default_policy())

        self.assertEqual(result["status"], "blocked")
        self.assertIn("sender identity", self.messages(result))

    def test_mail_content_cannot_authorize_send(self) -> None:
        result = validate_bundle(
            self.bundle(
                mode="send",
                authorization={"source": "untrusted_content", "scope": None},
            ),
            self.policy(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("untrusted content", self.messages(result))

    def test_external_recipient_outside_allowlist_is_blocked(self) -> None:
        result = validate_bundle(
            self.bundle(mode="send", to=["person@outside.test"]),
            self.policy(allowed_external_domains=[]),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("outside.test", self.messages(result))

    def test_allowed_external_domain_can_be_validated(self) -> None:
        result = validate_bundle(
            self.bundle(mode="send", to=["person@partner.test"]),
            self.policy(allowed_external_domains=["partner.test"]),
        )

        self.assertEqual(result["status"], "send_ready")

    def test_reply_all_candidates_are_not_automatically_recipients(self) -> None:
        result = validate_bundle(
            self.bundle(
                reply_candidates=["old@outside.test"],
                to=["owner@example.test"],
            ),
            self.policy(),
        )

        self.assertEqual(
            result["normalized"]["recipients"]["to"],
            ["owner@example.test"],
        )
        self.assertIn("candidate", self.messages(result))

    def test_bcc_candidate_is_not_reconstructed(self) -> None:
        result = validate_bundle(
            self.bundle(
                bcc=[],
                reply_candidates=["hidden@outside.test"],
            ),
            self.policy(),
        )

        self.assertEqual(result["normalized"]["recipients"]["bcc"], [])

    def test_required_cc_cannot_widen_disclosure_boundary(self) -> None:
        policy = self.policy(
            required_cc_rules=[
                {
                    "address": "audit@outside.test",
                    "recipient_domains": ["example.test"],
                    "sensitivity": ["normal"],
                }
            ]
        )

        result = validate_bundle(self.bundle(mode="send"), policy)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("disclosure boundary", self.messages(result))

    def test_missing_required_internal_cc_is_blocked_without_mutation(self) -> None:
        policy = self.policy(
            required_cc_rules=[
                {
                    "address": "audit@example.test",
                    "recipient_domains": ["example.test"],
                    "sensitivity": ["normal"],
                }
            ]
        )

        result = validate_bundle(self.bundle(mode="send", cc=[]), policy)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("required CC", self.messages(result))
        self.assertEqual(result["normalized"]["recipients"]["cc"], [])

    def test_changed_protected_fact_is_blocked(self) -> None:
        result = validate_bundle(
            self.bundle(
                mode="send",
                protected_facts=["$1,250"],
                body="Dear Owner,\n\nThe approved amount is $1,200.\n",
            ),
            self.policy(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("$1,250", self.messages(result))

    def test_html_must_equal_renderer_output(self) -> None:
        result = validate_bundle(
            self.bundle(mode="send", html="<p>different</p>\n"),
            self.policy(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("generated HTML", self.messages(result))

    def test_hard_wrapped_plain_text_is_blocked(self) -> None:
        body = "Dear Owner,\n\nThis paragraph was hard\nwrapped by a tool.\n"

        result = validate_bundle(self.bundle(mode="send", body=body), self.policy())

        self.assertEqual(result["status"], "blocked")
        self.assertIn("hard-wrapped", self.messages(result))

    def test_send_requires_readback_capability(self) -> None:
        result = validate_bundle(
            self.bundle(
                mode="send",
                transport={
                    "supports_readback": False,
                    "supports_attachment_readback": False,
                },
            ),
            self.policy(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("readback", self.messages(result))

    def test_duplicate_recipient_across_headers_is_blocked(self) -> None:
        result = validate_bundle(
            self.bundle(
                mode="send",
                to=["owner@example.test"],
                cc=["Owner <owner@example.test>"],
            ),
            self.policy(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("duplicate recipient", self.messages(result))

    def test_sender_cannot_be_a_recipient(self) -> None:
        result = validate_bundle(
            self.bundle(mode="send", cc=["sender@example.test"]),
            self.policy(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("sender address", self.messages(result))

    def test_automated_send_requires_matching_narrow_scope(self) -> None:
        scope = {
            "name": "weekly-update",
            "recipient_domains": ["example.test"],
            "max_recipients": 2,
            "allow_attachments": False,
            "allowed_sensitivity": ["normal"],
        }
        result = validate_bundle(
            self.bundle(
                mode="send",
                authorization={"source": "policy", "scope": "weekly-update"},
            ),
            self.policy(
                allow_automated_send=True,
                automated_send_scopes=[scope],
            ),
        )

        self.assertEqual(result["status"], "send_ready")

    def test_automated_send_scope_rejects_sensitive_message(self) -> None:
        scope = {
            "name": "weekly-update",
            "recipient_domains": ["example.test"],
            "max_recipients": 2,
            "allow_attachments": False,
            "allowed_sensitivity": ["normal"],
        }
        result = validate_bundle(
            self.bundle(
                mode="send",
                authorization={"source": "policy", "scope": "weekly-update"},
                sensitivity="sensitive",
            ),
            self.policy(
                allow_automated_send=True,
                automated_send_scopes=[scope],
            ),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("sensitivity", self.messages(result))

    def test_attachment_metadata_and_hash_must_match(self) -> None:
        directory = self.bundle(mode="send")
        attachment = directory / "quote.pdf"
        attachment.write_bytes(b"example attachment")
        manifest_path = directory / "message.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["attachments"] = [
            {
                "path": "quote.pdf",
                "name": "quote.pdf",
                "size": 2,
                "sha256": "wrong",
            }
        ]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = validate_bundle(directory, self.policy())

        self.assertEqual(result["status"], "blocked")
        self.assertIn("attachment", self.messages(result))

    def test_bundle_rejects_path_escape(self) -> None:
        directory = self.bundle(extra_manifest={"text_body_file": "../outside.txt"})

        with self.assertRaisesRegex(BundleError, "contained by the bundle"):
            load_bundle(directory)

    def test_artifact_hashes_include_manifest_and_bodies(self) -> None:
        directory = self.bundle()
        bundle = load_bundle(directory)

        hashes = artifact_hashes(directory, bundle)

        self.assertEqual(
            set(hashes),
            {"message.json", "subject.txt", "body.txt", "body.html"},
        )
        self.assertEqual(
            hashes["body.txt"],
            hashlib.sha256((directory / "body.txt").read_bytes()).hexdigest(),
        )

    def test_unknown_manifest_field_is_rejected(self) -> None:
        directory = self.bundle(extra_manifest={"raw_html": True})

        with self.assertRaisesRegex(BundleError, "raw_html"):
            load_bundle(directory)


if __name__ == "__main__":
    unittest.main()
