#!/usr/bin/env python3
"""Verify a retrieved Sent message against its validated email bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .email_bundle import BundleError, artifact_hashes, load_bundle
    from .email_policy import normalize_address
except ImportError:
    from email_bundle import BundleError, artifact_hashes, load_bundle
    from email_policy import normalize_address


_READBACK_KEYS = {
    "schema_version",
    "message_id",
    "thread_id",
    "from",
    "to",
    "cc",
    "bcc",
    "subject",
    "text_body",
    "html_body",
    "attachments",
}
_ATTACHMENT_KEYS = {"name", "size", "sha256"}


def verify_readback(
    bundle_dir: Path,
    validation_path: Path,
    readback_path: Path,
) -> dict[str, object]:
    """Compare a retrieved message with the exact bundle approved for sending."""

    bundle = load_bundle(bundle_dir)
    validation = _load_object(validation_path, "validation report")
    readback = _load_object(readback_path, "readback report")
    mismatches: list[dict[str, object]] = []

    if validation.get("schema_version") != 1:
        mismatches.append(_mismatch("validation.schema_version", 1, validation.get("schema_version")))
    if validation.get("status") != "send_ready":
        mismatches.append(_mismatch("validation.status", "send_ready", validation.get("status")))

    expected_hashes = validation.get("artifact_sha256")
    observed_hashes = artifact_hashes(bundle_dir, bundle)
    if expected_hashes != observed_hashes:
        mismatches.append(_mismatch("artifact_sha256", expected_hashes, observed_hashes))

    unknown = sorted(set(readback) - _READBACK_KEYS)
    missing = sorted(_READBACK_KEYS - set(readback))
    if unknown or missing or readback.get("schema_version") != 1:
        mismatches.append(
            _mismatch(
                "readback.schema",
                {"schema_version": 1, "fields": sorted(_READBACK_KEYS)},
                {
                    "schema_version": readback.get("schema_version"),
                    "unknown": unknown,
                    "missing": missing,
                },
            )
        )

    message_id = readback.get("message_id")
    if not isinstance(message_id, str) or not message_id.strip():
        mismatches.append(_mismatch("message_id", "nonempty string", message_id))
        result_message_id = ""
    else:
        result_message_id = message_id.strip()

    normalized = _mapping(validation.get("normalized"))
    _compare(
        mismatches,
        "from",
        normalized.get("sender"),
        _normalized_single_address(readback.get("from")),
    )
    expected_recipients = _mapping(normalized.get("recipients"))
    for header in ("to", "cc", "bcc"):
        _compare(
            mismatches,
            header,
            _normalized_expected_addresses(expected_recipients.get(header)),
            _normalized_addresses(readback.get(header)),
        )

    _compare(mismatches, "subject", normalized.get("subject"), readback.get("subject"))
    _compare(
        mismatches,
        "text_body",
        _normalize_text(str(bundle["_text_body"])),
        _normalize_text_value(readback.get("text_body")),
    )
    _compare(mismatches, "html_body", bundle["_html_body"], readback.get("html_body"))

    requested_thread_id = _mapping(bundle.get("reply")).get("thread_id")
    if requested_thread_id is not None:
        _compare(
            mismatches,
            "thread_id",
            requested_thread_id,
            readback.get("thread_id"),
        )

    _compare(
        mismatches,
        "attachments",
        _expected_attachments(bundle.get("attachments")),
        _observed_attachments(readback.get("attachments")),
    )

    return _result(mismatches, result_message_id)


def _load_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain an object")
    return value


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def _normalize_text_value(value: object) -> object:
    return _normalize_text(value) if isinstance(value, str) else value


def _normalized_single_address(value: object) -> object:
    return normalize_address(value) if isinstance(value, str) else value


def _normalized_expected_addresses(value: object) -> object:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return value
    return sorted(value)


def _normalized_addresses(value: object) -> object:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return value
    addresses = [normalize_address(item) for item in value]
    if any(address is None for address in addresses):
        return value
    return sorted(addresses)


def _expected_attachments(value: object) -> object:
    if not isinstance(value, list):
        return value
    attachments: list[dict[str, object]] = []
    for item in value:
        attachment = _mapping(item)
        attachments.append(
            {
                "name": attachment.get("name"),
                "size": attachment.get("size"),
                "sha256": str(attachment.get("sha256", "")).lower(),
            }
        )
    return _sort_attachments(attachments)


def _observed_attachments(value: object) -> object:
    if not isinstance(value, list):
        return value
    attachments: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != _ATTACHMENT_KEYS:
            return value
        attachments.append(
            {
                "name": item.get("name"),
                "size": item.get("size"),
                "sha256": str(item.get("sha256", "")).lower(),
            }
        )
    return _sort_attachments(attachments)


def _sort_attachments(value: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        value,
        key=lambda item: (
            str(item.get("name")),
            str(item.get("sha256")),
            str(item.get("size")),
        ),
    )


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _compare(
    mismatches: list[dict[str, object]],
    field: str,
    expected: object,
    observed: object,
) -> None:
    if expected != observed:
        mismatches.append(_mismatch(field, expected, observed))


def _mismatch(field: str, expected: object, observed: object) -> dict[str, object]:
    return {"field": field, "expected": expected, "observed": observed}


def _result(
    mismatches: list[dict[str, object]],
    message_id: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "blocked" if mismatches else "sent_and_verified",
        "message_id": message_id,
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a retrieved Sent message.")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--readback", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = verify_readback(args.bundle, args.validation, args.readback)
    except (BundleError, ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"email readback verification failed: {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
