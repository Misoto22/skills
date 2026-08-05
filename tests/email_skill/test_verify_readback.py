from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "plugins" / "writing" / "skills" / "email" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from email_policy import safe_default_policy  # noqa: E402
from render_email import render_html  # noqa: E402
from validate_message import validate_bundle  # noqa: E402
from verify_readback import verify_readback  # noqa: E402


class VerifyReadbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.bundle = self._bundle()
        validation = validate_bundle(self.bundle, self._policy())
        self.assertEqual(validation["status"], "send_ready")
        self.validation = self._write_json("validation.json", validation)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _policy(self) -> dict[str, object]:
        policy = copy.deepcopy(safe_default_policy())
        policy["identity"] = {
            "sender_name": "Example Sender",
            "sender_address": "sender@example.test",
            "internal_domains": ["example.test"],
        }
        return policy

    def _bundle(self, *, attachment: bool = False) -> Path:
        directory = self.root / ("attachment-message" if attachment else "message")
        directory.mkdir()
        body = "Dear Owner,\n\nThe update is ready.\n"
        (directory / "subject.txt").write_text("Project update\n", encoding="utf-8")
        (directory / "body.txt").write_text(body, encoding="utf-8")
        (directory / "body.html").write_text(render_html(body), encoding="utf-8")

        attachments: list[dict[str, object]] = []
        if attachment:
            payload = b"quarterly data\n"
            (directory / "report.txt").write_bytes(payload)
            attachments.append(
                {
                    "path": "report.txt",
                    "name": "report.txt",
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )

        manifest = {
            "schema_version": 1,
            "mode": "send",
            "sender": {"name": "Example Sender", "address": "sender@example.test"},
            "recipients": {
                "to": ["Owner <owner@example.test>"],
                "cc": ["reviewer@example.test"],
                "bcc": [],
            },
            "subject_file": "subject.txt",
            "text_body_file": "body.txt",
            "html_body_file": "body.html",
            "authorization": {"source": "direct_user", "scope": None},
            "protected_facts": [],
            "sensitivity": "normal",
            "reply": {
                "message_id": "source-message-id",
                "thread_id": "thread-123",
                "candidate_recipients": [],
            },
            "transport": {
                "supports_readback": True,
                "supports_attachment_readback": True,
            },
            "attachments": attachments,
        }
        (directory / "message.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        return directory

    def _readback(self, **overrides: object) -> Path:
        data: dict[str, object] = {
            "schema_version": 1,
            "message_id": "sent-message-id",
            "thread_id": "thread-123",
            "from": "Example Sender <SENDER@example.test>",
            "to": ["owner@EXAMPLE.test"],
            "cc": ["Reviewer <reviewer@example.test>"],
            "bcc": [],
            "subject": "Project update",
            "text_body": "Dear Owner,\r\n\r\nThe update is ready.\r\n",
            "html_body": render_html("Dear Owner,\n\nThe update is ready.\n"),
            "attachments": [],
        }
        data.update(overrides)
        return self._write_json("readback.json", data)

    def _write_json(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _mismatch_fields(result: dict[str, object]) -> set[str]:
        return {item["field"] for item in result["mismatches"]}

    def test_exact_normalized_readback_is_verified(self) -> None:
        result = verify_readback(self.bundle, self.validation, self._readback())

        self.assertEqual(result["status"], "sent_and_verified")
        self.assertEqual(result["message_id"], "sent-message-id")
        self.assertEqual(result["mismatches"], [])

    def test_message_id_without_matching_body_fails(self) -> None:
        result = verify_readback(
            self.bundle,
            self.validation,
            self._readback(text_body="wrong"),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("text_body", self._mismatch_fields(result))

    def test_changed_recipient_fails(self) -> None:
        result = verify_readback(
            self.bundle,
            self.validation,
            self._readback(to=["other@example.test"]),
        )

        self.assertIn("to", self._mismatch_fields(result))

    def test_missing_message_id_fails(self) -> None:
        result = verify_readback(
            self.bundle,
            self.validation,
            self._readback(message_id=""),
        )

        self.assertIn("message_id", self._mismatch_fields(result))

    def test_requested_thread_id_must_match(self) -> None:
        result = verify_readback(
            self.bundle,
            self.validation,
            self._readback(thread_id="other-thread"),
        )

        self.assertIn("thread_id", self._mismatch_fields(result))

    def test_missing_attachment_bytes_cannot_verify_expected_attachment(self) -> None:
        attachment_bundle = self._bundle(attachment=True)
        validation = validate_bundle(attachment_bundle, self._policy())
        validation_path = self._write_json("attachment-validation.json", validation)

        result = verify_readback(
            attachment_bundle,
            validation_path,
            self._readback(attachments=[]),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("attachments", self._mismatch_fields(result))

    def test_matching_attachment_metadata_is_verified(self) -> None:
        attachment_bundle = self._bundle(attachment=True)
        validation = validate_bundle(attachment_bundle, self._policy())
        validation_path = self._write_json("attachment-validation.json", validation)
        payload = b"quarterly data\n"

        result = verify_readback(
            attachment_bundle,
            validation_path,
            self._readback(
                attachments=[
                    {
                        "name": "report.txt",
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ]
            ),
        )

        self.assertEqual(result["status"], "sent_and_verified")

    def test_mutated_bundle_after_validation_fails_before_comparison(self) -> None:
        (self.bundle / "body.txt").write_text("changed\n", encoding="utf-8")

        result = verify_readback(self.bundle, self.validation, self._readback())

        self.assertIn("artifact_sha256", self._mismatch_fields(result))

    def test_prior_validation_must_be_send_ready(self) -> None:
        validation = json.loads(self.validation.read_text(encoding="utf-8"))
        validation["status"] = "draft_ready"
        self._write_json("validation.json", validation)

        result = verify_readback(self.bundle, self.validation, self._readback())

        self.assertIn("validation.status", self._mismatch_fields(result))

    def test_unknown_readback_field_is_rejected(self) -> None:
        result = verify_readback(
            self.bundle,
            self.validation,
            self._readback(provider_claim="delivered"),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("readback.schema", self._mismatch_fields(result))


if __name__ == "__main__":
    unittest.main()
