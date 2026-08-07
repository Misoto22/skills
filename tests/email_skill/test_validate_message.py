from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "plugins" / "writing" / "skills" / "email" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from email_bundle import BundleError, artifact_hashes, load_bundle
from email_policy import safe_default_policy
from render_email import render_html
from validate_message import validate_bundle


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


class AutomationScopeTests(ValidateMessageTests):
    """The scope is the only gate between a policy file and mail leaving unattended.

    Every other authorization source ends with a human deciding. `policy` does
    not, so each bound it declares — recipient count, recipient domains,
    attachments, sensitivity — has to be shown to actually stop a bundle that
    exceeds it, not merely to be written down.
    """

    SCOPE: ClassVar[dict] = {
        "name": "ops-alerts",
        "recipient_domains": ["example.test"],
        "max_recipients": 2,
        "allow_attachments": False,
        "allowed_sensitivity": ["normal"],
    }

    def scoped_policy(self, **scope_overrides: object) -> dict[str, object]:
        scope = {**self.SCOPE, **scope_overrides}
        return self.policy(
            allow_automated_send=True,
            automated_send_scopes=[scope],
            allowed_external_domains=["partner.test"],
        )

    def attachment(self) -> dict[str, object]:
        """A manifest entry for a file the bundle builder already writes."""

        payload = b"Project update\n"
        return {
            "path": "subject.txt",
            "name": "subject.txt",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    def scoped_bundle(self, *, name: str, **bundle_overrides: object) -> Path:
        return self.bundle(
            name=name,
            mode="send",
            authorization={"source": "policy", "scope": "ops-alerts"},
            **bundle_overrides,
        )

    def test_a_bundle_inside_every_bound_passes(self) -> None:
        """The baseline. Without it, a later block could be any bound failing."""

        result = validate_bundle(self.scoped_bundle(name="ok"), self.scoped_policy())

        self.assertNotEqual(result["status"], "blocked", self.messages(result))

    def test_each_declared_bound_actually_stops_a_bundle(self) -> None:
        cases = {
            "too-many": ({"to": ["a@example.test", "b@example.test", "c@example.test"]}, "recipient count"),
            "wrong-domain": ({"to": ["someone@partner.test"]}, "recipient domains"),
            "attached": ({"attachments": [self.attachment()]}, "attachments are not allowed"),
            "too-sensitive": ({"sensitivity": "sensitive"}, "sensitivity exceeds"),
        }
        for name, (overrides, expected) in cases.items():
            with self.subTest(bound=name):
                result = validate_bundle(self.scoped_bundle(name=name, **overrides), self.scoped_policy())
                self.assertEqual(result["status"], "blocked", self.messages(result))
                self.assertIn(expected, self.messages(result))

    def test_an_unconfigured_scope_name_is_not_a_scope(self) -> None:
        """Naming a scope the policy does not define must fail closed, not open."""

        bundle = self.bundle(
            name="unknown-scope",
            mode="send",
            authorization={"source": "policy", "scope": "does-not-exist"},
        )

        result = validate_bundle(bundle, self.scoped_policy())

        self.assertEqual(result["status"], "blocked", self.messages(result))
        self.assertIn("is not configured", self.messages(result))

    def test_automation_disabled_blocks_even_a_well_formed_scope(self) -> None:
        """The master switch outranks the scope; a scope alone must not authorize."""

        policy = self.policy(allow_automated_send=False, automated_send_scopes=[self.SCOPE])

        result = validate_bundle(self.scoped_bundle(name="switched-off"), policy)

        self.assertEqual(result["status"], "blocked", self.messages(result))
        self.assertIn("does not allow automated send", self.messages(result))

    def test_send_without_a_source_is_refused(self) -> None:
        """Absence of authority is not a default to fall back on."""

        bundle = self.bundle(
            name="no-source",
            mode="send",
            authorization={"source": "none", "scope": None},
        )

        result = validate_bundle(bundle, self.scoped_policy())

        self.assertEqual(result["status"], "blocked", self.messages(result))
        self.assertIn("requires trusted authorization", self.messages(result))

    def test_an_invented_source_never_reaches_the_validator(self) -> None:
        """The loader rejects it first, so the validator's own branch is depth, not the gate.

        Worth pinning: if the loader ever loosened, this test fails rather than
        the validator quietly becoming the only thing standing between an
        invented `source` string and a send.
        """

        with self.assertRaisesRegex(BundleError, "unsupported value"):
            validate_bundle(
                self.bundle(
                    name="invented",
                    mode="send",
                    authorization={"source": "hand_wave", "scope": None},
                ),
                self.scoped_policy(),
            )


class CommandLineTests(ValidateMessageTests):
    """The entry point an operator actually runs, exercised the way they run it.

    `validate_bundle` returning `blocked` is only half the guarantee — the exit
    code is what a wrapper script branches on, and it had no test at all.
    """

    SCRIPT: ClassVar[Path] = (
        ROOT / "plugins" / "writing" / "skills" / "email" / "scripts" / "validate_message.py"
    )

    def invoke(self, bundle: Path, policy_path: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(self.SCRIPT),
                "--bundle",
                str(bundle),
                "--policy",
                str(policy_path),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def run_cli(self, bundle: Path, policy: dict[str, object]) -> tuple[int, dict | None]:
        policy_path = self.root / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        output = self.root / "out" / "result.json"
        completed = self.invoke(bundle, policy_path, output)
        written = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else None
        return completed.returncode, written

    def test_a_valid_draft_exits_zero_and_writes_its_result(self) -> None:
        code, result = self.run_cli(self.bundle(name="draft"), self.policy())

        self.assertEqual(code, 0)
        self.assertIsNotNone(result)
        self.assertNotEqual(result["status"], "blocked")

    def test_a_blocked_bundle_exits_two_and_still_writes_its_findings(self) -> None:
        """Exit 2 is the signal; the findings file is how the operator learns why."""

        bundle = self.bundle(
            name="blocked",
            mode="send",
            to=["stranger@elsewhere.test"],
            authorization={"source": "direct_user", "scope": None},
        )

        code, result = self.run_cli(bundle, self.policy())

        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["findings"])

    def test_an_unreadable_policy_exits_two_without_writing_a_result(self) -> None:
        """A validation that could not run must not leave a file that reads as a pass."""

        policy_path = self.root / "policy.json"
        policy_path.write_text("{ not json", encoding="utf-8")
        output = self.root / "out" / "result.json"

        completed = self.invoke(self.bundle(name="unreadable"), policy_path, output)

        self.assertEqual(completed.returncode, 2)
        self.assertIn("email validation failed", completed.stderr)
        self.assertFalse(output.exists(), "a failed run left a result file behind")


if __name__ == "__main__":
    unittest.main()
