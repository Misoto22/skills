"""Plan copying one account's sidebar layout onto every other account's scope.

The desktop app keeps its sidebar layout in one Local Storage value, ``dframe-store``:
a byte naming the text encoding, then JSON ``{"state": {...}, "version": N}``. Inside
``state``, ``codeSidebarByScope`` maps ``<accountUuid>/<orgUuid>`` to that scope's
sections — the built-in pinned, routines and sessions lists, and the user's manual
groups with their member conversations — and ``customGroupsByScope`` maps the same key
to the manual groups' names. Everything else in ``state`` is global or a cache, and is
carried over untouched.

A manual group lists its conversations as ``code:<sessionId>``. A copied group keeps
only the members the receiving account's index holds, so no account is handed a row
that opens to nothing.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass

STORE_KEY = b"_https://claude.ai\x00\x01dframe-store"
SECTIONS_BY_SCOPE = "codeSidebarByScope"
GROUPS_BY_SCOPE = "customGroupsByScope"
MANUAL = "manual"
MEMBER_PREFIX = "code:"
LATIN1, UTF16 = b"\x01", b"\x00"


class SidebarError(Exception):
    """The stored layout is not in the shape this script knows how to copy."""


@dataclass(frozen=True)
class ScopeChange:
    """What copying the layout does to one account's scope."""

    account: str
    scope: str
    created: bool
    sections_before: int
    manual_before: int
    sections_after: int
    manual_after: int
    dropped: int
    changed: bool


def decode(raw: bytes) -> dict:
    """Parse a stored ``dframe-store`` value into its JSON document."""
    prefix, body = raw[:1], raw[1:]
    try:
        if prefix == LATIN1:
            text = body.decode("latin-1")
        elif prefix == UTF16:
            text = body.decode("utf-16-le", "surrogatepass")
        else:
            raise SidebarError(f"unknown Local Storage encoding byte {prefix!r}")
        document = json.loads(text)
    except (UnicodeDecodeError, ValueError) as error:
        raise SidebarError(f"the stored sidebar layout is not readable JSON: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("state"), dict):
        raise SidebarError("the stored sidebar layout has no state object")
    return document


def encode(document: dict) -> bytes:
    """Serialize as the app does: Latin-1 when every character fits, else UTF-16LE."""
    text = json.dumps(document, separators=(",", ":"), ensure_ascii=False)
    try:
        return LATIN1 + text.encode("latin-1")
    except UnicodeEncodeError:
        return UTF16 + text.encode("utf-16-le", "surrogatepass")


def sections_of(entry: object) -> list[dict]:
    """The section list of one scope entry, or an empty list when there is none."""
    sections = entry.get("sections") if isinstance(entry, dict) else None
    return [s for s in sections if isinstance(s, dict)] if isinstance(sections, list) else []


def manual_count(entry: object) -> int:
    """How many manual groups a scope entry holds."""
    return sum(1 for section in sections_of(entry) if section.get("kind") == MANUAL)


def source_scope(state: dict, account: str, landing_scope: str) -> str:
    """The scope key holding the source account's layout.

    The account's landing org is where reunite puts its conversations, so its scope
    is preferred; an account with exactly one scope in the store uses that one.
    """
    scopes = state.get(SECTIONS_BY_SCOPE)
    if not isinstance(scopes, dict):
        raise SidebarError(f"the stored layout has no {SECTIONS_BY_SCOPE}")
    if isinstance(scopes.get(landing_scope), dict):
        return landing_scope
    own = [scope for scope in scopes if scope.startswith(f"{account}/")]
    if len(own) == 1:
        return own[0]
    found = ", ".join(own) or "none"
    raise SidebarError(f"cannot tell which sidebar scope is {account}'s layout (scopes found: {found})")


def prune(entry: dict, known: set[str]) -> tuple[dict, int]:
    """A copy of ``entry`` whose manual groups list only conversations in ``known``.

    A member not written as ``code:<sessionId>`` cannot be checked against the index,
    so it is kept as it is.
    """
    pruned = copy.deepcopy(entry)
    dropped = 0
    for section in sections_of(pruned):
        members = section.get("members")
        if section.get("kind") != MANUAL or not isinstance(members, list):
            continue
        kept = [
            m
            for m in members
            if not (isinstance(m, str) and m.startswith(MEMBER_PREFIX)) or m[len(MEMBER_PREFIX) :] in known
        ]
        dropped += len(members) - len(kept)
        section["members"] = kept
    return pruned, dropped


def plan_layout(
    document: dict, source: str, source_account: str, scopes: dict[str, str], held: dict[str, set[str]]
) -> tuple[dict, list[ScopeChange]]:
    """The document with ``source``'s layout copied to every other account's scope.

    ``scopes`` maps each account to the scope key it should receive; ``held`` maps it
    to the session ids its index holds. Only the two per-scope layout maps change.
    """
    updated = copy.deepcopy(document)
    state = updated["state"]
    sections = state[SECTIONS_BY_SCOPE]
    layout = sections[source]
    groups_map = state.get(GROUPS_BY_SCOPE)
    groups = groups_map.get(source) if isinstance(groups_map, dict) else None
    changes: list[ScopeChange] = []
    for account, scope in sorted(scopes.items()):
        if account == source_account or scope == source:
            continue
        before = sections.get(scope)
        entry, dropped = prune(layout, held.get(account, set()))
        changed = before != entry
        sections[scope] = entry
        if groups is not None:
            changed = changed or groups_map.get(scope) != groups
            groups_map[scope] = copy.deepcopy(groups)
        changes.append(
            ScopeChange(
                account,
                scope,
                before is None,
                len(sections_of(before)),
                manual_count(before),
                len(sections_of(entry)),
                manual_count(entry),
                dropped,
                changed,
            )
        )
    return updated, changes
