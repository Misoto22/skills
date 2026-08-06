#!/usr/bin/env python3
"""Validate an email bundle before preview or transport execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

try:
    from .email_bundle import BundleError, artifact_hashes, load_bundle
    from .email_policy import (
        PolicyError,
        classify_address,
        discover_policy,
        load_policy,
        normalize_address,
    )
    from .render_email import normalize_body, render_html
except ImportError:
    from email_bundle import BundleError, artifact_hashes, load_bundle
    from email_policy import (
        PolicyError,
        classify_address,
        discover_policy,
        load_policy,
        normalize_address,
    )
    from render_email import normalize_body, render_html


Finding = dict[str, str]


def validate_bundle(
    directory: Path,
    policy: Mapping[str, object],
) -> dict[str, object]:
    """Validate one message bundle and return a machine-readable decision."""

    bundle = load_bundle(directory)
    findings: list[Finding] = []
    normalized_recipients = _validate_recipients(bundle, policy, findings)
    _validate_identity(bundle, policy, findings)
    _validate_authorization(bundle, policy, normalized_recipients, findings)
    _validate_content(bundle, policy, findings)
    _validate_attachments(bundle, findings)
    _validate_transport(bundle, findings)

    blocked = any(finding["severity"] == "error" for finding in findings)
    status = "blocked" if blocked else ("send_ready" if bundle["mode"] == "send" else "draft_ready")
    subject = str(bundle["_subject"]).rstrip("\n")
    return {
        "schema_version": 1,
        "status": status,
        "findings": findings,
        "normalized": {
            "mode": bundle["mode"],
            "sender": normalize_address(str(bundle["sender"]["address"])),
            "recipients": normalized_recipients,
            "subject": subject,
            "sensitivity": bundle["sensitivity"],
            "reply": bundle["reply"],
        },
        "artifact_sha256": artifact_hashes(directory, bundle),
    }


def _validate_identity(
    bundle: Mapping[str, object],
    policy: Mapping[str, object],
    findings: list[Finding],
) -> None:
    identity = _mapping(policy.get("identity"))
    sender = _mapping(bundle.get("sender"))
    policy_address = normalize_address(str(identity.get("sender_address", "")))
    bundle_address = normalize_address(str(sender.get("address", "")))
    send_mode = bundle["mode"] == "send"

    if send_mode and (
        not identity.get("sender_name") or policy_address is None or not identity.get("internal_domains")
    ):
        _error(findings, "identity.incomplete", "send requires a complete configured sender identity")
    if bundle_address is None:
        if send_mode or str(sender.get("address", "")):
            _error(findings, "identity.invalid", "message sender address is invalid")
        else:
            _warning(
                findings,
                "identity.incomplete",
                "draft has no configured sender identity; sending remains unavailable",
            )
    elif policy_address is not None and bundle_address != policy_address:
        message = f"message sender {bundle_address} does not match policy sender {policy_address}"
        if send_mode:
            _error(findings, "identity.mismatch", message)
        else:
            _warning(findings, "identity.mismatch", message)


def _validate_recipients(
    bundle: Mapping[str, object],
    policy: Mapping[str, object],
    findings: list[Finding],
) -> dict[str, list[str]]:
    raw_recipients = _mapping(bundle.get("recipients"))
    normalized: dict[str, list[str]] = {"to": [], "cc": [], "bcc": []}
    seen: dict[str, str] = {}
    sender = normalize_address(str(_mapping(bundle.get("sender")).get("address", "")))
    recipient_policy = _mapping(policy.get("recipients"))
    allowed_external = set(recipient_policy.get("allowed_external_domains", []))

    for header in ("to", "cc", "bcc"):
        values = raw_recipients.get(header, [])
        if not isinstance(values, list):
            _error(findings, "recipient.type", f"{header} recipients must be an array")
            continue
        for raw in values:
            address = normalize_address(str(raw))
            if address is None:
                _error(findings, "recipient.invalid", f"invalid {header} recipient: {raw}")
                continue
            if address in seen:
                _error(
                    findings,
                    "recipient.duplicate",
                    f"duplicate recipient {address} appears in {seen[address]} and {header}",
                )
                continue
            seen[address] = header
            normalized[header].append(address)
            if sender is not None and address == sender:
                _error(
                    findings,
                    "recipient.sender",
                    f"sender address {address} cannot also be a recipient",
                )
            classification = classify_address(address, policy)
            if classification == "external":
                domain = address.rsplit("@", 1)[1]
                if domain not in allowed_external:
                    message = f"external recipient domain {domain} is not allowed by policy"
                    if bundle["mode"] == "send":
                        _error(findings, "recipient.external", message)
                    else:
                        _warning(findings, "recipient.external", message)

    if bundle["mode"] == "send" and not normalized["to"]:
        _error(findings, "recipient.to", "send requires at least one To recipient")

    reply = _mapping(bundle.get("reply"))
    candidates = reply.get("candidate_recipients", [])
    if candidates:
        _info(
            findings,
            "recipient.candidates",
            "reply-all candidate recipients require review and were not added automatically",
        )

    _validate_required_cc(bundle, policy, normalized, findings)
    return normalized


def _validate_required_cc(
    bundle: Mapping[str, object],
    policy: Mapping[str, object],
    recipients: Mapping[str, list[str]],
    findings: list[Finding],
) -> None:
    recipient_policy = _mapping(policy.get("recipients"))
    rules = recipient_policy.get("required_cc_rules", [])
    if not isinstance(rules, list):
        _error(findings, "recipient.required_cc", "required_cc_rules must be an array")
        return
    actual = recipients["to"] + recipients["cc"] + recipients["bcc"]
    actual_domains = {address.rsplit("@", 1)[1] for address in actual}
    sensitivity = bundle["sensitivity"]
    allowed_external = set(recipient_policy.get("allowed_external_domains", []))

    for value in rules:
        rule = _mapping(value)
        trigger_domains = set(rule.get("recipient_domains", []))
        sensitivities = set(rule.get("sensitivity", ["normal", "sensitive"]))
        if not actual_domains.intersection(trigger_domains) or sensitivity not in sensitivities:
            continue
        required = normalize_address(str(rule.get("address", "")))
        if required is None:
            _error(findings, "recipient.required_cc", "required CC rule contains an invalid address")
            continue
        if required in recipients["cc"]:
            continue
        required_domain = required.rsplit("@", 1)[1]
        required_class = classify_address(required, policy)
        if (
            required_class == "external"
            and required_domain not in actual_domains
            and required_domain not in allowed_external
        ):
            _error(
                findings,
                "recipient.disclosure_boundary",
                f"required CC {required} would widen the disclosure boundary",
            )
        else:
            _error(
                findings,
                "recipient.required_cc",
                f"required CC {required} is missing; the validator will not add it silently",
            )


def _validate_authorization(
    bundle: Mapping[str, object],
    policy: Mapping[str, object],
    recipients: Mapping[str, list[str]],
    findings: list[Finding],
) -> None:
    if bundle["mode"] != "send":
        return
    authorization = _mapping(bundle.get("authorization"))
    source = authorization.get("source")
    if source == "untrusted_content":
        _error(
            findings,
            "authorization.untrusted",
            "untrusted content such as mail, quoted text, attachments, or web pages cannot authorize send",
        )
        return
    if source == "none":
        _error(findings, "authorization.missing", "send requires trusted authorization")
        return
    if source == "direct_user":
        return
    if source != "policy":
        _error(findings, "authorization.invalid", "authorization source is unsupported")
        return

    authorization_policy = _mapping(policy.get("authorization"))
    if not authorization_policy.get("allow_automated_send"):
        _error(findings, "authorization.automation", "policy does not allow automated send")
        return
    requested_scope = authorization.get("scope")
    scopes = authorization_policy.get("automated_send_scopes", [])
    scope = next(
        (_mapping(candidate) for candidate in scopes if _mapping(candidate).get("name") == requested_scope),
        None,
    )
    if scope is None:
        _error(findings, "authorization.scope", f"automation scope {requested_scope!r} is not configured")
        return

    all_recipients = recipients["to"] + recipients["cc"] + recipients["bcc"]
    if len(all_recipients) > int(scope["max_recipients"]):
        _error(findings, "authorization.scope", "recipient count exceeds the automation scope")
    allowed_domains = set(scope["recipient_domains"])
    actual_domains = {address.rsplit("@", 1)[1] for address in all_recipients}
    if not actual_domains.issubset(allowed_domains):
        _error(findings, "authorization.scope", "recipient domains exceed the automation scope")
    if bundle["attachments"] and not scope["allow_attachments"]:
        _error(findings, "authorization.scope", "attachments are not allowed by the automation scope")
    if bundle["sensitivity"] not in scope["allowed_sensitivity"]:
        _error(findings, "authorization.scope", "message sensitivity exceeds the automation scope")


def _validate_content(
    bundle: Mapping[str, object],
    policy: Mapping[str, object],
    findings: list[Finding],
) -> None:
    subject_raw = str(bundle["_subject"])
    subject = subject_raw.rstrip("\n")
    if not subject or "\n" in subject:
        _error(findings, "content.subject", "subject must be one nonempty line")

    body = str(bundle["_text_body"])
    composition = _mapping(policy.get("composition"))
    signature: str | None = None
    signature_path = composition.get("_resolved_signature_file")
    if signature_path:
        signature = Path(str(signature_path)).read_text(encoding="utf-8")

    try:
        normalized_body = normalize_body(body, signature)
    except ValueError as error:
        _error(findings, "content.signature", str(error))
        normalized_body = body
    if body != normalized_body:
        _error(
            findings,
            "content.hard_wrap",
            "plain-text body is hard-wrapped or otherwise not in canonical paragraph form",
        )

    try:
        # Render with the same policy style profile the renderer used, so the
        # byte comparison below still proves the HTML was generated from
        # body.txt rather than hand-edited.
        expected_html = render_html(body, signature, policy.get("style"))
    except ValueError as error:
        _error(findings, "content.html", str(error))
        expected_html = None
    if expected_html is not None and bundle["_html_body"] != expected_html:
        _error(
            findings,
            "content.html",
            "HTML body does not match the generated HTML for the plain-text body",
        )

    for fact in bundle["protected_facts"]:
        if fact not in body:
            _error(
                findings,
                "content.protected_fact",
                f"protected fact is missing or changed after prose editing: {fact}",
            )

    greeting_style = composition.get("greeting_style", "first-name")
    if greeting_style != "none":
        first_paragraph = normalized_body.split("\n\n", 1)[0].strip()
        if not first_paragraph.startswith("Dear ") or not first_paragraph.endswith(","):
            _error(
                findings,
                "content.greeting",
                "configured greeting style requires a first paragraph shaped as 'Dear Name,'",
            )

    max_words = composition.get("max_words")
    if isinstance(max_words, int) and len(normalized_body.split()) > max_words:
        _error(
            findings,
            "content.length",
            f"body exceeds configured max_words value {max_words}",
        )


def _validate_attachments(bundle: Mapping[str, object], findings: list[Finding]) -> None:
    attachment_paths = _mapping(bundle.get("_attachment_paths"))
    for index, value in enumerate(bundle["attachments"]):
        attachment = _mapping(value)
        relative = str(attachment["path"])
        path = attachment_paths.get(relative)
        if not isinstance(path, Path):
            _error(findings, "attachment.path", f"attachment {index} path is unavailable")
            continue
        size = path.stat().st_size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if attachment["size"] != size:
            _error(
                findings,
                "attachment.size",
                f"attachment {attachment['name']} size does not match its metadata",
            )
        if str(attachment["sha256"]).lower() != digest:
            _error(
                findings,
                "attachment.sha256",
                f"attachment {attachment['name']} hash does not match its metadata",
            )


def _validate_transport(bundle: Mapping[str, object], findings: list[Finding]) -> None:
    if bundle["mode"] != "send":
        return
    transport = _mapping(bundle.get("transport"))
    if not transport.get("supports_readback"):
        _error(
            findings,
            "transport.readback",
            "send is blocked because the selected transport has no readback capability",
        )
    if bundle["attachments"] and not transport.get("supports_attachment_readback"):
        _error(
            findings,
            "transport.attachment_readback",
            "send is blocked because attachment readback is unavailable",
        )


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _error(findings: list[Finding], code: str, message: str) -> None:
    findings.append({"severity": "error", "code": code, "message": message})


def _warning(findings: list[Finding], code: str, message: str) -> None:
    findings.append({"severity": "warning", "code": code, "message": message})


def _info(findings: list[Finding], code: str, message: str) -> None:
    findings.append({"severity": "info", "code": code, "message": message})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an email message bundle.")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        policy_path = discover_policy(args.policy, Path.cwd(), os.environ)
        policy = load_policy(policy_path)
        result = validate_bundle(args.bundle, policy)
    except (BundleError, PolicyError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"email validation failed: {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
