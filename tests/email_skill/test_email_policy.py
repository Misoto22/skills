from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins" / "writing" / "skills" / "email" / "scripts"))

from email_policy import (
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


class StylePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_policy(self, value: object) -> Path:
        path = self.root / "policy.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def policy_with_style(self, style: object) -> dict[str, object]:
        policy = safe_default_policy()
        policy["style"] = style
        return policy

    def valid_style(self, **overrides: object) -> dict[str, object]:
        style: dict[str, object] = {
            "font_family": "Helvetica, Arial, sans-serif",
            "font_size_px": 14,
            "line_height": 1.55,
            "text_color": "#222222",
            "paragraph_spacing_px": 16,
            "list_style": "semantic",
            "table": {
                "border_color": "#cccccc",
                "font_size_px": 13,
                "cell_padding_px": [6, 10],
            },
            "status_colors": {"ok": "#1a7f37", "warn": "#b36b00", "bad": "#c00000"},
        }
        style.update(overrides)
        return style

    def test_safe_defaults_carry_no_style(self) -> None:
        self.assertIsNone(safe_default_policy()["style"])

    def test_explicit_null_style_is_accepted(self) -> None:
        policy = load_policy(self.write_policy(self.policy_with_style(None)))

        self.assertIsNone(policy["style"])

    def test_valid_style_is_loaded(self) -> None:
        policy = load_policy(self.write_policy(self.policy_with_style(self.valid_style())))

        style = policy["style"]
        self.assertEqual(style["list_style"], "semantic")
        self.assertEqual(style["table"]["cell_padding_px"], [6, 10])

    def test_partial_style_is_completed_from_neutral_defaults(self) -> None:
        policy = load_policy(self.write_policy(self.policy_with_style({"list_style": "paragraph"})))

        style = policy["style"]
        self.assertEqual(style["list_style"], "paragraph")
        self.assertIn("font_family", style)
        self.assertIn("status_colors", style)

    def test_unknown_style_field_is_rejected(self) -> None:
        style = self.valid_style()
        style["background_image"] = "https://example.test/tracker.png"

        with self.assertRaisesRegex(PolicyError, "unknown field"):
            load_policy(self.write_policy(self.policy_with_style(style)))

    def test_unknown_table_field_is_rejected(self) -> None:
        style = self.valid_style()
        style["table"] = {"border_color": "#cccccc", "width": "100%"}

        with self.assertRaisesRegex(PolicyError, "unknown field"):
            load_policy(self.write_policy(self.policy_with_style(style)))

    def test_unsupported_list_style_is_rejected(self) -> None:
        with self.assertRaisesRegex(PolicyError, "list_style"):
            load_policy(self.write_policy(self.policy_with_style(self.valid_style(list_style="cards"))))

    def test_non_hex_colour_is_rejected(self) -> None:
        with self.assertRaisesRegex(PolicyError, "text_color"):
            load_policy(self.write_policy(self.policy_with_style(self.valid_style(text_color="red; xss:1"))))

    def test_status_colour_must_be_hex(self) -> None:
        style = self.valid_style()
        style["status_colors"] = {"ok": "#1a7f37", "warn": "#b36b00", "bad": "expression(1)"}

        with self.assertRaisesRegex(PolicyError, "status_colors.bad"):
            load_policy(self.write_policy(self.policy_with_style(style)))

    def test_font_family_rejects_css_control_characters(self) -> None:
        for hostile in ("Arial; background:url(x)", "Arial}", "Arial<script>"):
            with self.subTest(hostile=hostile), self.assertRaisesRegex(PolicyError, "font_family"):
                load_policy(self.write_policy(self.policy_with_style(self.valid_style(font_family=hostile))))

    def test_cell_padding_requires_two_non_negative_integers(self) -> None:
        style = self.valid_style()
        style["table"] = {
            "border_color": "#cccccc",
            "font_size_px": 13,
            "cell_padding_px": [6, -10],
        }

        with self.assertRaisesRegex(PolicyError, "cell_padding_px"):
            load_policy(self.write_policy(self.policy_with_style(style)))

    def test_font_size_must_be_positive_integer(self) -> None:
        with self.assertRaisesRegex(PolicyError, "font_size_px"):
            load_policy(self.write_policy(self.policy_with_style(self.valid_style(font_size_px=0))))

    def test_line_height_must_be_a_positive_number(self) -> None:
        with self.assertRaisesRegex(PolicyError, "line_height"):
            load_policy(self.write_policy(self.policy_with_style(self.valid_style(line_height="1.55; x"))))

    def test_style_must_be_object_or_null(self) -> None:
        with self.assertRaisesRegex(PolicyError, "style"):
            load_policy(self.write_policy(self.policy_with_style("house")))


class PolicyRejectionTests(unittest.TestCase):
    """The policy is the gate on an outward side effect, so its rejections are the product.

    A malformed policy that loads is worse than one that fails: it produces a
    sender identity, a domain allowlist, or a send authorization nobody wrote.
    These assert the file is rejected, and that the message names the field — an
    operator editing a policy at speed is the audience.
    """

    EXAMPLE = ROOT / "plugins" / "writing" / "skills" / "email" / "policy.example.json"
    # One value of the wrong type per JSON type. `load_policy` is a type gate
    # before it is anything else, and this is what the `_require_*` helpers
    # exist to catch.
    WRONG_TYPE: ClassVar[dict] = {str: 17, int: "seventeen", bool: "yes", list: {}, dict: []}

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.document = json.loads(self.EXAMPLE.read_text(encoding="utf-8"))
        # signature_file resolves against the policy file's own directory, so
        # the example's relative path has to exist beside the copy under test —
        # otherwise every case here fails on a missing signature instead of on
        # the rule it was written for.
        signature = self.root / self.document["composition"]["signature_file"]
        signature.parent.mkdir(parents=True, exist_ok=True)
        signature.write_text("-- \nExample Sender\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, value: object) -> Path:
        path = self.root / "policy.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def leaves(self, node: object, trail: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], object]]:
        """Every addressable position in the document."""

        if isinstance(node, dict):
            return [item for key, value in node.items() for item in self.leaves(value, (*trail, key))]
        return [(trail, node)] if trail else []

    def substitute(self, document: dict, trail: tuple[str, ...], value: object) -> dict:
        edited = json.loads(json.dumps(document))
        target = edited
        for key in trail[:-1]:
            target = target[key]
        target[trail[-1]] = value
        return edited

    def test_every_field_is_rejected_when_its_type_is_wrong(self) -> None:
        """A type gate nothing exercises is a type gate that quietly stopped working."""

        checked = 0
        for trail, value in self.leaves(self.document):
            wrong = self.WRONG_TYPE.get(type(value))
            if wrong is None:  # a null-valued optional; covered separately
                continue
            checked += 1
            with self.subTest(field=".".join(trail)):
                with self.assertRaises(PolicyError) as raised:
                    load_policy(self.write(self.substitute(self.document, trail, wrong)))
                # The operator is editing a file, so the message has to say which line.
                self.assertIn(trail[-1], str(raised.exception), f"{'.'.join(trail)}: {raised.exception}")
        self.assertGreater(checked, 8, "the example policy stopped covering the fields it used to")

    def test_a_populated_send_scope_is_held_to_every_field(self) -> None:
        """Automated send is the one authorization that acts without a human. Fence it."""

        def with_scope(**overrides: object) -> dict:
            scope = {
                "name": "ops-alerts",
                "recipient_domains": ["example.test"],
                "max_recipients": 3,
                "allow_attachments": False,
                "allowed_sensitivity": ["normal"],
            }
            scope.update(overrides)
            document = json.loads(json.dumps(self.document))
            document["authorization"]["allow_automated_send"] = True
            document["authorization"]["automated_send_scopes"] = [scope]
            return document

        # The happy path first, or a rejection below could be the scope shape
        # being wrong rather than the rule under test firing.
        loaded = load_policy(self.write(with_scope()))
        self.assertEqual(loaded["authorization"]["automated_send_scopes"][0]["name"], "ops-alerts")

        for overrides, expected in (
            ({"name": "  "}, "nonempty and unique"),
            ({"recipient_domains": []}, "cannot be empty"),
            ({"max_recipients": 0}, "positive integer"),
            ({"max_recipients": True}, "positive integer"),
            ({"allow_attachments": "no"}, "must be boolean"),
            ({"allowed_sensitivity": []}, "cannot be empty"),
            ({"allowed_sensitivity": ["urgent"]}, "unsupported value"),
        ):
            with self.subTest(**overrides), self.assertRaisesRegex(PolicyError, expected):
                load_policy(self.write(with_scope(**overrides)))

    def test_two_scopes_cannot_share_a_name(self) -> None:
        """Scopes are selected by name, so a duplicate silently shadows the stricter one."""

        scope = {
            "name": "ops-alerts",
            "recipient_domains": ["example.test"],
            "max_recipients": 3,
            "allow_attachments": False,
            "allowed_sensitivity": ["normal"],
        }
        document = json.loads(json.dumps(self.document))
        document["authorization"]["allow_automated_send"] = True
        document["authorization"]["automated_send_scopes"] = [scope, json.loads(json.dumps(scope))]

        with self.assertRaisesRegex(PolicyError, "nonempty and unique"):
            load_policy(self.write(document))

    def test_a_scope_missing_a_field_is_named_in_the_error(self) -> None:
        """A dropped field is the likeliest hand edit, and the laxest failure."""

        document = json.loads(json.dumps(self.document))
        document["authorization"]["allow_automated_send"] = True
        document["authorization"]["automated_send_scopes"] = [{"name": "ops-alerts"}]

        with self.assertRaisesRegex(PolicyError, "missing field"):
            load_policy(self.write(document))

    def test_an_unknown_field_is_rejected_rather_than_ignored(self) -> None:
        """A typo that loads is a setting the operator believes is in force."""

        for section, field in (("identity", "sender_adress"), ("authorization", "allow_automatic_send")):
            document = json.loads(json.dumps(self.document))
            document[section][field] = "value"
            with self.subTest(field=f"{section}.{field}"), self.assertRaises(PolicyError):
                load_policy(self.write(document))


if __name__ == "__main__":
    unittest.main()
