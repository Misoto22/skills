#!/usr/bin/env python3
"""Load, normalize, and hash transport-neutral email message bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


_MANIFEST_KEYS = {
    "schema_version",
    "mode",
    "sender",
    "recipients",
    "subject_file",
    "text_body_file",
    "html_body_file",
    "authorization",
    "protected_facts",
    "sensitivity",
    "reply",
    "transport",
    "attachments",
}
_SENDER_KEYS = {"name", "address"}
_RECIPIENT_KEYS = {"to", "cc", "bcc"}
_AUTHORIZATION_KEYS = {"source", "scope"}
_REPLY_KEYS = {"message_id", "thread_id", "candidate_recipients"}
_TRANSPORT_KEYS = {"supports_readback", "supports_attachment_readback"}
_ATTACHMENT_KEYS = {"path", "name", "size", "sha256"}


class BundleError(ValueError):
    """Raised when a message bundle is malformed or unsafe to read."""


def load_bundle(directory: Path) -> dict[str, object]:
    """Load a strict message bundle and attach its validated artifact paths."""

    root = directory.expanduser().resolve()
    if not root.is_dir():
        raise BundleError(f"bundle directory does not exist: {root}")
    manifest_path = root / "message.json"
    if not manifest_path.is_file():
        raise BundleError(f"bundle is missing message.json: {root}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BundleError(f"cannot read message.json: {error}") from error
    if not isinstance(manifest, dict):
        raise BundleError("message.json must contain an object")

    _reject_unknown(manifest, _MANIFEST_KEYS, "message.json")
    missing = _MANIFEST_KEYS - set(manifest)
    if missing:
        raise BundleError(f"message.json missing field(s): {', '.join(sorted(missing))}")
    if manifest["schema_version"] != 1:
        raise BundleError("message.json schema_version must be 1")
    if manifest["mode"] not in {"draft", "send"}:
        raise BundleError("message.json mode must be draft or send")

    sender = _require_mapping(manifest["sender"], "sender")
    _require_exact_keys(sender, _SENDER_KEYS, "sender")
    _require_string(sender["name"], "sender.name")
    _require_string(sender["address"], "sender.address")

    recipients = _require_mapping(manifest["recipients"], "recipients")
    _require_exact_keys(recipients, _RECIPIENT_KEYS, "recipients")
    for header in ("to", "cc", "bcc"):
        _string_list(recipients[header], f"recipients.{header}")

    authorization = _require_mapping(manifest["authorization"], "authorization")
    _require_exact_keys(authorization, _AUTHORIZATION_KEYS, "authorization")
    if authorization["source"] not in {
        "none",
        "direct_user",
        "policy",
        "untrusted_content",
    }:
        raise BundleError("authorization.source has an unsupported value")
    if authorization["scope"] is not None:
        _require_string(authorization["scope"], "authorization.scope")

    protected_facts = _string_list(manifest["protected_facts"], "protected_facts")
    if any(not fact for fact in protected_facts):
        raise BundleError("protected_facts cannot contain empty strings")
    if manifest["sensitivity"] not in {"normal", "sensitive"}:
        raise BundleError("sensitivity must be normal or sensitive")

    reply = _require_mapping(manifest["reply"], "reply")
    _require_exact_keys(reply, _REPLY_KEYS, "reply")
    for field in ("message_id", "thread_id"):
        if reply[field] is not None:
            _require_string(reply[field], f"reply.{field}")
    _string_list(reply["candidate_recipients"], "reply.candidate_recipients")

    transport = _require_mapping(manifest["transport"], "transport")
    _require_exact_keys(transport, _TRANSPORT_KEYS, "transport")
    for field in _TRANSPORT_KEYS:
        if not isinstance(transport[field], bool):
            raise BundleError(f"transport.{field} must be boolean")

    artifact_paths: dict[str, Path] = {"message.json": manifest_path}
    for field in ("subject_file", "text_body_file", "html_body_file"):
        relative = _require_string(manifest[field], field)
        artifact_paths[relative] = _contained_file(root, relative, field)

    attachments = _require_list(manifest["attachments"], "attachments")
    attachment_paths: dict[str, Path] = {}
    for index, value in enumerate(attachments):
        location = f"attachments[{index}]"
        attachment = _require_mapping(value, location)
        _require_exact_keys(attachment, _ATTACHMENT_KEYS, location)
        relative = _require_string(attachment["path"], f"{location}.path")
        _require_string(attachment["name"], f"{location}.name")
        if (
            isinstance(attachment["size"], bool)
            or not isinstance(attachment["size"], int)
            or attachment["size"] < 0
        ):
            raise BundleError(f"{location}.size must be a nonnegative integer")
        _require_string(attachment["sha256"], f"{location}.sha256")
        path = _contained_file(root, relative, f"{location}.path")
        attachment_paths[relative] = path
        artifact_paths[relative] = path

    loaded = dict(manifest)
    loaded["_directory"] = root
    loaded["_artifact_paths"] = artifact_paths
    loaded["_attachment_paths"] = attachment_paths
    loaded["_subject"] = _read_text(artifact_paths[manifest["subject_file"]], "subject")
    loaded["_text_body"] = _read_text(artifact_paths[manifest["text_body_file"]], "text body")
    loaded["_html_body"] = _read_text(artifact_paths[manifest["html_body_file"]], "HTML body")
    return loaded


def artifact_hashes(
    directory: Path,
    bundle: dict[str, object],
) -> dict[str, str]:
    """Hash the manifest and every artifact referenced by a loaded bundle."""

    root = directory.expanduser().resolve()
    if bundle.get("_directory") != root:
        raise BundleError("loaded bundle does not belong to the supplied directory")
    paths = bundle.get("_artifact_paths")
    if not isinstance(paths, dict):
        raise BundleError("bundle has not been loaded by load_bundle")
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(paths.items())
    }


def _contained_file(root: Path, relative: str, location: str) -> Path:
    supplied = Path(relative)
    if supplied.is_absolute() or ".." in supplied.parts:
        raise BundleError(f"{location} must be contained by the bundle")
    resolved = (root / supplied).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise BundleError(f"{location} must be contained by the bundle") from error
    if not resolved.is_file():
        raise BundleError(f"{location} does not exist: {relative}")
    return resolved


def _read_text(path: Path, label: str) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise BundleError(f"cannot read {label}: {error}") from error
    if "\x00" in value:
        raise BundleError(f"{label} contains a NUL byte")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _reject_unknown(value: dict[str, object], allowed: set[str], location: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise BundleError(f"{location} has unknown field(s): {', '.join(unknown)}")


def _require_exact_keys(value: dict[str, object], keys: set[str], location: str) -> None:
    _reject_unknown(value, keys, location)
    missing = keys - set(value)
    if missing:
        raise BundleError(f"{location} missing field(s): {', '.join(sorted(missing))}")


def _require_mapping(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BundleError(f"{location} must be an object")
    return value


def _require_list(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise BundleError(f"{location} must be an array")
    return value


def _string_list(value: object, location: str) -> list[str]:
    values = _require_list(value, location)
    for index, item in enumerate(values):
        _require_string(item, f"{location}[{index}]")
    return values


def _require_string(value: object, location: str) -> str:
    if not isinstance(value, str):
        raise BundleError(f"{location} must be a string")
    return value
