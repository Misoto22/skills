"""Which environments each account has starred, and copying one account's stars to the rest.

The environment picker's Starred list is not in the presets file. The app keeps it in
Local Storage, one key per account and no org:
``LSS-persisted.code-projects-order.<accountUuid>``, a Latin-1 JSON envelope
``{"value": ["preset::<presetId>", ...], "tabId": "", "timestamp": <ms>}`` listing the
starred environments in the order the picker shows them. Copying stars is copying that
key's bytes from the source account to every other account, and deleting a receiving
account's key when the source has none — the same value the app would have written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sidebar import ORIGIN

PREFIX = ORIGIN + b"LSS-persisted.code-projects-order."
PRESET_PREFIX = "preset::"


@dataclass(frozen=True)
class StarChange:
    """How many environments one account has starred before and after the copy; None for no key."""

    account: str
    before: int | None
    after: int | None


def key(account: str) -> bytes:
    """The Local Storage key holding ``account``'s starred environments."""
    return PREFIX + account.encode()


def starred(raw: bytes | None) -> list[str] | None:
    """The starred preset ids in a stored value; None when there is no key, [] when it is unreadable."""
    if raw is None:
        return None
    try:
        value = json.loads(raw[1:].decode("latin-1")).get("value")
    except (ValueError, AttributeError):
        return []
    if not isinstance(value, list):
        return []
    return [item.removeprefix(PRESET_PREFIX) for item in value if isinstance(item, str)]


def _count(raw: bytes | None) -> int | None:
    ids = starred(raw)
    return None if ids is None else len(ids)


def plan_stars(
    values: dict[str, bytes | None], source: str
) -> tuple[list[tuple[bytes, bytes | None]], list[StarChange]]:
    """The writes that give every account ``source``'s stars, and what each one changes.

    ``values`` maps every account to its stored value, or None where it has no key.
    """
    wanted = values.get(source)
    operations: list[tuple[bytes, bytes | None]] = []
    changes: list[StarChange] = []
    for account in sorted(values):
        if account == source or values[account] == wanted:
            continue
        operations.append((key(account), wanted))
        changes.append(StarChange(account, _count(values[account]), _count(wanted)))
    return operations, changes
