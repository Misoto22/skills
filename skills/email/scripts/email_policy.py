#!/usr/bin/env python3
"""Load and validate organization-neutral policy for the email skill."""

from __future__ import annotations

import copy
import json
import re
from email.utils import parseaddr
from pathlib import Path
from typing import Literal, Mapping


POLICY_ENVIRONMENT_VARIABLE = "EMAIL_SKILL_POLICY"
PROJECT_POLICY_PATH = Path(".agents/email-policy.json")

_TOP_LEVEL_KEYS = {
    "schema_version",
    "identity",
    "composition",
    "recipients",
    "authorization",
}
_IDENTITY_KEYS = {"sender_name", "sender_address", "internal_domains"}
_COMPOSITION_KEYS = {
    "greeting_style",
    "target_words",
    "max_words",
    "signature_file",
    "humanizer",
}
_RECIPIENT_KEYS = {
    "allowed_external_domains",
    "required_cc_rules",
    "reply_all",
}
_AUTHORIZATION_KEYS = {
    "default_mode",
    "allow_automated_send",
    "automated_send_scopes",
}
_REQUIRED_CC_KEYS = {"address", "recipient_domains", "sensitivity"}
_AUTOMATION_SCOPE_KEYS = {
    "name",
    "recipient_domains",
    "max_recipients",
    "allow_attachments",
    "allowed_sensitivity",
}
_DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)
_ADDRESS_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z"
)


class PolicyError(ValueError):
    """Raised when policy discovery or validation fails."""


def safe_default_policy() -> dict[str, object]:
    """Return organization-neutral defaults that permit drafting only."""

    return {
        "schema_version": 1,
        "identity": {
            "sender_name": "",
            "sender_address": "",
            "internal_domains": [],
        },
        "composition": {
            "greeting_style": "first-name",
            "target_words": None,
            "max_words": None,
            "signature_file": None,
            "humanizer": "optional",
        },
        "recipients": {
            "allowed_external_domains": [],
            "required_cc_rules": [],
            "reply_all": "review",
        },
        "authorization": {
            "default_mode": "draft",
            "allow_automated_send": False,
            "automated_send_scopes": [],
        },
    }


def discover_policy(
    explicit_path: Path | None,
    cwd: Path,
    environ: Mapping[str, str],
) -> Path | None:
    """Resolve policy by explicit path, environment path, then project path."""

    if explicit_path is not None:
        return _require_policy_path(explicit_path, cwd, "explicit policy")

    environment_path = environ.get(POLICY_ENVIRONMENT_VARIABLE)
    if environment_path:
        return _require_policy_path(
            Path(environment_path),
            cwd,
            POLICY_ENVIRONMENT_VARIABLE,
        )

    project_path = cwd / PROJECT_POLICY_PATH
    return project_path if project_path.is_file() else None


def load_policy(path: Path | None) -> dict[str, object]:
    """Load a JSON policy, merge safe defaults, and validate every field."""

    if path is None:
        return safe_default_policy()

    resolved_path = path.expanduser().resolve()
    if not resolved_path.is_file():
        raise PolicyError(f"policy does not exist: {resolved_path}")

    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PolicyError(f"cannot read policy {resolved_path}: {error}") from error

    if not isinstance(raw, dict):
        raise PolicyError("policy must be a JSON object")

    _reject_unknown(raw, _TOP_LEVEL_KEYS, "policy")
    policy = copy.deepcopy(safe_default_policy())
    for section in ("identity", "composition", "recipients", "authorization"):
        supplied = raw.get(section, {})
        if not isinstance(supplied, dict):
            raise PolicyError(f"{section} must be an object")
        policy[section].update(supplied)
    if "schema_version" in raw:
        policy["schema_version"] = raw["schema_version"]

    _validate_policy(policy, resolved_path)
    return policy


def classify_address(
    address: str,
    policy: Mapping[str, object],
) -> Literal["internal", "external", "invalid"]:
    """Classify an address from its parsed domain, never its display name."""

    normalized = normalize_address(address)
    if normalized is None:
        return "invalid"
    domain = normalized.rsplit("@", 1)[1]
    identity = policy.get("identity", {})
    internal_domains = identity.get("internal_domains", []) if isinstance(identity, Mapping) else []
    return "internal" if domain in internal_domains else "external"


def normalize_address(value: str) -> str | None:
    """Return a lowercase addr-spec for supported mailbox syntax."""

    if not isinstance(value, str) or "\n" in value or "\r" in value:
        return None
    _, address = parseaddr(value)
    if not address or _ADDRESS_PATTERN.fullmatch(address) is None:
        return None
    return address.lower()


def _require_policy_path(path: Path, cwd: Path, label: str) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    if not candidate.is_file():
        raise PolicyError(f"{label} does not exist: {candidate}")
    return candidate


def _reject_unknown(
    value: Mapping[str, object],
    allowed: set[str],
    location: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise PolicyError(f"{location} has unknown field(s): {', '.join(unknown)}")


def _validate_policy(policy: dict[str, object], path: Path) -> None:
    if policy["schema_version"] != 1:
        raise PolicyError("schema_version must be 1")

    identity = _require_mapping(policy["identity"], "identity")
    composition = _require_mapping(policy["composition"], "composition")
    recipients = _require_mapping(policy["recipients"], "recipients")
    authorization = _require_mapping(policy["authorization"], "authorization")

    _reject_unknown(identity, _IDENTITY_KEYS, "identity")
    _reject_unknown(composition, _COMPOSITION_KEYS, "composition")
    _reject_unknown(recipients, _RECIPIENT_KEYS, "recipients")
    _reject_unknown(authorization, _AUTHORIZATION_KEYS, "authorization")

    _require_string(identity["sender_name"], "identity.sender_name")
    sender_address = _require_string(
        identity["sender_address"],
        "identity.sender_address",
    )
    if sender_address and normalize_address(sender_address) is None:
        raise PolicyError("identity.sender_address must be a valid mailbox")
    if sender_address:
        identity["sender_address"] = normalize_address(sender_address)
    identity["internal_domains"] = _normalize_domains(
        identity["internal_domains"],
        "identity.internal_domains",
    )

    if composition["greeting_style"] not in {"first-name", "full-name", "none"}:
        raise PolicyError("composition.greeting_style has an unsupported value")
    if composition["humanizer"] not in {"optional", "disabled", "required"}:
        raise PolicyError("composition.humanizer has an unsupported value")
    target_words = _optional_positive_integer(
        composition["target_words"],
        "composition.target_words",
    )
    max_words = _optional_positive_integer(
        composition["max_words"],
        "composition.max_words",
    )
    if target_words is not None and max_words is not None and target_words > max_words:
        raise PolicyError("composition.target_words cannot exceed max_words")
    signature_file = composition["signature_file"]
    if signature_file is not None:
        signature_value = _require_string(
            signature_file,
            "composition.signature_file",
        )
        signature_path = Path(signature_value).expanduser()
        if not signature_path.is_absolute():
            signature_path = path.parent / signature_path
        signature_path = signature_path.resolve()
        if not signature_path.is_file():
            raise PolicyError(
                f"composition.signature_file does not exist: {signature_path}"
            )
        composition["_resolved_signature_file"] = str(signature_path)

    recipients["allowed_external_domains"] = _normalize_domains(
        recipients["allowed_external_domains"],
        "recipients.allowed_external_domains",
    )
    if recipients["reply_all"] not in {"review", "never"}:
        raise PolicyError("recipients.reply_all must be review or never")
    recipients["required_cc_rules"] = _validate_required_cc_rules(
        recipients["required_cc_rules"]
    )

    if authorization["default_mode"] != "draft":
        raise PolicyError("authorization.default_mode must be draft")
    if not isinstance(authorization["allow_automated_send"], bool):
        raise PolicyError("authorization.allow_automated_send must be boolean")
    authorization["automated_send_scopes"] = _validate_automation_scopes(
        authorization["automated_send_scopes"]
    )


def _validate_required_cc_rules(value: object) -> list[dict[str, object]]:
    rules = _require_list(value, "recipients.required_cc_rules")
    normalized: list[dict[str, object]] = []
    for index, rule_value in enumerate(rules):
        location = f"recipients.required_cc_rules[{index}]"
        rule = _require_mapping(rule_value, location)
        _reject_unknown(rule, _REQUIRED_CC_KEYS, location)
        if "address" not in rule or "recipient_domains" not in rule:
            raise PolicyError(f"{location} requires address and recipient_domains")
        address = normalize_address(_require_string(rule["address"], f"{location}.address"))
        if address is None:
            raise PolicyError(f"{location}.address must be a valid mailbox")
        domains = _normalize_domains(
            rule["recipient_domains"],
            f"{location}.recipient_domains",
        )
        if not domains:
            raise PolicyError(f"{location}.recipient_domains cannot be empty")
        sensitivity = rule.get("sensitivity", ["normal", "sensitive"])
        sensitivity_values = _enum_list(
            sensitivity,
            {"normal", "sensitive"},
            f"{location}.sensitivity",
        )
        normalized.append(
            {
                "address": address,
                "recipient_domains": domains,
                "sensitivity": sensitivity_values,
            }
        )
    return normalized


def _validate_automation_scopes(value: object) -> list[dict[str, object]]:
    scopes = _require_list(value, "authorization.automated_send_scopes")
    normalized: list[dict[str, object]] = []
    names: set[str] = set()
    for index, scope_value in enumerate(scopes):
        location = f"authorization.automated_send_scopes[{index}]"
        scope = _require_mapping(scope_value, location)
        _reject_unknown(scope, _AUTOMATION_SCOPE_KEYS, location)
        missing = _AUTOMATION_SCOPE_KEYS - set(scope)
        if missing:
            raise PolicyError(f"{location} missing field(s): {', '.join(sorted(missing))}")
        name = _require_string(scope["name"], f"{location}.name").strip()
        if not name or name in names:
            raise PolicyError(f"{location}.name must be nonempty and unique")
        names.add(name)
        domains = _normalize_domains(
            scope["recipient_domains"],
            f"{location}.recipient_domains",
        )
        if not domains:
            raise PolicyError(f"{location}.recipient_domains cannot be empty")
        max_recipients = scope["max_recipients"]
        if isinstance(max_recipients, bool) or not isinstance(max_recipients, int) or max_recipients < 1:
            raise PolicyError(f"{location}.max_recipients must be a positive integer")
        if not isinstance(scope["allow_attachments"], bool):
            raise PolicyError(f"{location}.allow_attachments must be boolean")
        sensitivity = _enum_list(
            scope["allowed_sensitivity"],
            {"normal", "sensitive"},
            f"{location}.allowed_sensitivity",
        )
        if not sensitivity:
            raise PolicyError(f"{location}.allowed_sensitivity cannot be empty")
        normalized.append(
            {
                "name": name,
                "recipient_domains": domains,
                "max_recipients": max_recipients,
                "allow_attachments": scope["allow_attachments"],
                "allowed_sensitivity": sensitivity,
            }
        )
    return normalized


def _normalize_domains(value: object, location: str) -> list[str]:
    domains = _require_list(value, location)
    normalized: list[str] = []
    for index, domain_value in enumerate(domains):
        domain = _require_string(domain_value, f"{location}[{index}]").strip().lower().rstrip(".")
        if _DOMAIN_PATTERN.fullmatch(domain) is None:
            raise PolicyError(f"{location}[{index}] is not a valid domain")
        if domain not in normalized:
            normalized.append(domain)
    return normalized


def _enum_list(value: object, allowed: set[str], location: str) -> list[str]:
    values = _require_list(value, location)
    normalized: list[str] = []
    for index, item in enumerate(values):
        item_value = _require_string(item, f"{location}[{index}]")
        if item_value not in allowed:
            raise PolicyError(f"{location}[{index}] has an unsupported value")
        if item_value not in normalized:
            normalized.append(item_value)
    return normalized


def _optional_positive_integer(value: object, location: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PolicyError(f"{location} must be a positive integer or null")
    return value


def _require_mapping(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PolicyError(f"{location} must be an object")
    return value


def _require_list(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise PolicyError(f"{location} must be an array")
    return value


def _require_string(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise PolicyError(f"{location} must be a string")
    return value
