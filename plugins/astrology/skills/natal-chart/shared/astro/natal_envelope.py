"""The natal artifact's identity and checksum, shared by the two skills that use it.

The calculator writes this envelope and the reading skill verifies it. Neither may
import the other — an installer copies a skill directory and nothing beside it — so
the one thing they must agree on byte for byte lives here instead. Duplicating a
canonical-JSON hash in two places is how two skills quietly stop agreeing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

SCHEMA = "astrology.natal-chart"
SCHEMA_VERSION = 1


class NatalEnvelopeError(ValueError):
    """A natal artifact is not what it claims to be."""


def canonical_checksum(content: Mapping[str, Any]) -> str:
    """Hash the envelope's canonical form, with any existing checksum removed."""

    payload = {key: value for key, value in content.items() if key != "checksum"}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def add_checksum(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached envelope carrying its canonical SHA-256."""

    result = {key: value for key, value in envelope.items() if key != "checksum"}
    result["checksum"] = canonical_checksum(result)
    return result


def validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate schema identity, version, and canonical content checksum."""

    result = dict(envelope)
    if result.get("schema") != SCHEMA:
        raise NatalEnvelopeError(f"unsupported artifact schema {result.get('schema')!r}")
    if result.get("schema_version") != SCHEMA_VERSION:
        raise NatalEnvelopeError(
            f"unsupported {SCHEMA} version {result.get('schema_version')!r}; expected {SCHEMA_VERSION}"
        )
    supplied = result.get("checksum")
    if not isinstance(supplied, str) or supplied != canonical_checksum(result):
        raise NatalEnvelopeError("artifact checksum does not match its canonical content")
    return result
