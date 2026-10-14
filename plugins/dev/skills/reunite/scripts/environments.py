"""Plan giving every account the same environments, without ever bringing a deleted one back.

The desktop app keeps its environments — named working directories offered when a
session starts — in ``ccd-session-presets.json`` as ``{"byAccount": {<account>:
{"presets": [...], "builtIns": {...}, "seededFromDraft": bool}}}``, and edits only the
signed-in account's entry. A preset is a name and a machine path; nothing in it
belongs to an account, so every account can hold the same list.

The list every account receives is the union of all of them, one copy per ``id``: the
copy used most recently wins, then the one created last. What the user deleted is only
knowable against what was there before, so every write records a baseline of the ids
each account held. A run that finds an account no longer holding an id it held then
reads that as a deletion: the id is removed from every account and recorded with the
time it was observed, and no later run copies it back — unless a copy created after
that moment turns up, which is the user making it again.

An account that held presets at the last run and holds none now is frozen: neither read
as deleting all of them nor refilled. The app empties an account when it recovers from a
corrupt file or resets one, and reading that as the user deleting everything would wipe
every account; refilling it would undo a user who really did. It is left as it is until
it holds something again.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

BY_ACCOUNT = "byAccount"
PRESETS = "presets"
KEPT_FIELDS = ("builtIns", "seededFromDraft")
# The app refuses a catalog longer than this, or larger than this many bytes as compact JSON.
MAX_PRESETS = 200
MAX_ENTRY_BYTES = 524_288


class EnvironmentsError(Exception):
    """The environments file is not in the shape this script knows how to align."""


@dataclass
class EnvBaseline:
    """What the previous write left: the ids each account held, and the deletions seen so far."""

    held: dict[str, list[str]] = field(default_factory=dict)
    deleted: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class AccountChange:
    """What aligning changes in one account's entry."""

    account: str
    added: int
    updated: int
    removed: int
    created: bool


@dataclass(frozen=True)
class EnvPlan:
    """The whole new document, what it changes per account, and the baseline to record after."""

    document: dict
    union: list[str]
    changes: list[AccountChange]
    frozen: list[str]
    newly_deleted: set[str]
    baseline: EnvBaseline
    changed: bool


def entries_of(document: object) -> dict[str, dict]:
    """Each account's entry, or EnvironmentsError when any is not shaped as the app writes it."""
    by_account = document.get(BY_ACCOUNT) if isinstance(document, dict) else None
    if not isinstance(by_account, dict):
        raise EnvironmentsError(f"no {BY_ACCOUNT} object")
    for account, entry in by_account.items():
        presets = entry.get(PRESETS) if isinstance(entry, dict) else None
        if not isinstance(presets, list) or not all(
            isinstance(p, dict) and isinstance(p.get("id"), str) and p["id"] for p in presets
        ):
            raise EnvironmentsError(f"account {account} has no list of presets with ids")
    return by_account


def _ids(entry: dict | None) -> list[str]:
    return [p["id"] for p in entry[PRESETS]] if entry else []


def _rank(preset: dict) -> tuple[int, int]:
    used, created = preset.get("lastUsedAt"), preset.get("createdAt")
    return (used if isinstance(used, int) else 0, created if isinstance(created, int) else 0)


def _settle_deletions(entries, held, frozen, prior: dict[str, int], now: int) -> tuple[dict[str, int], set]:
    """Deletions recorded so far plus the ones seen now, less any preset made again since."""
    newly = set()
    for account, ids in held.items():
        if account in entries and account not in frozen:
            newly |= set(ids) - set(_ids(entries[account])) - set(prior)
    deleted = {**prior, **dict.fromkeys(newly, now)}
    for entry in entries.values():
        for preset in entry[PRESETS]:
            when = deleted.get(preset["id"])
            if when is not None and _rank(preset)[1] > when:
                del deleted[preset["id"]]
    return deleted, newly


def _union(entries: dict[str, dict], deleted: dict[str, int]) -> tuple[list[dict], str | None]:
    """One winning copy per live id, in the lead account's order, and which account leads."""
    winners: dict[str, tuple[tuple[int, int], dict]] = {}
    lead, best = None, (-1, -1)
    for account in sorted(entries):
        for preset in entries[account][PRESETS]:
            rank = _rank(preset)
            if rank > best:
                lead, best = account, rank
            if preset["id"] in deleted:
                continue
            if preset["id"] not in winners or rank > winners[preset["id"]][0]:
                winners[preset["id"]] = (rank, preset)
    order = [*_ids(entries.get(lead)), *(i for a in sorted(entries) for i in _ids(entries[a]))]
    union = [copy.deepcopy(winners[i][1]) for i in dict.fromkeys(order) if i in winners]
    if len(union) > MAX_PRESETS:
        raise EnvironmentsError(f"{len(union)} presets, more than the {MAX_PRESETS} the app accepts")
    return union, lead


def _aligned(before: dict | None, union: list[dict], lead_entry: dict | None) -> dict:
    entry = copy.deepcopy(before) if before is not None else {}
    entry[PRESETS] = union
    for name in KEPT_FIELDS:
        if name not in entry and lead_entry is not None and name in lead_entry:
            entry[name] = copy.deepcopy(lead_entry[name])
    if len(json.dumps(entry, separators=(",", ":")).encode()) > MAX_ENTRY_BYTES:
        raise EnvironmentsError(
            f"the aligned catalog is larger than the {MAX_ENTRY_BYTES} bytes the app accepts"
        )
    return entry


def _change(account: str, before: dict | None, after: dict) -> AccountChange:
    old = {p["id"]: p for p in (before or {}).get(PRESETS, [])}
    new = {p["id"]: p for p in after[PRESETS]}
    updated = sum(1 for i in new.keys() & old.keys() if new[i] != old[i])
    return AccountChange(
        account, len(new.keys() - old.keys()), updated, len(old.keys() - new.keys()), before is None
    )


def plan_environments(document: dict, targets: list[str], baseline: EnvBaseline | None, now: int) -> EnvPlan:
    """Align every target account's presets onto the union, honouring recorded deletions.

    ``now`` is the time in milliseconds a deletion seen in this run is recorded at.
    """
    entries = entries_of(document)
    held = baseline.held if baseline else {}
    frozen = sorted(a for a, ids in held.items() if ids and not _ids(entries.get(a)))
    deleted, newly = _settle_deletions(entries, held, set(frozen), baseline.deleted if baseline else {}, now)
    union, lead = _union(entries, deleted)
    updated = copy.deepcopy(document)
    accounts = updated[BY_ACCOUNT]
    changes: list[AccountChange] = []
    for account in sorted(set(targets) - set(frozen)):
        before = entries.get(account)
        if before is None and not union:
            continue
        after = _aligned(before, union, entries.get(lead) if lead else None)
        if after != before:
            accounts[account] = after
            changes.append(_change(account, before, after))
    record = {a: _ids(e) for a, e in accounts.items()}
    record.update({a: held[a] for a in frozen})
    union_ids = [p["id"] for p in union]
    return EnvPlan(updated, union_ids, changes, frozen, newly, EnvBaseline(record, deleted), bool(changes))
