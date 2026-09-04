#!/usr/bin/env python3
"""PreToolUse hook: refuse the three git forms the dev skills only ever asked the model to avoid.

`ship` says "never `--no-verify`" and "never `--admin`", and `shared/git.md` says the
base branch is never force-pushed and a feature branch only with `--force-with-lease`.
A sentence can be missed on a long turn; a hook cannot. Moving the rule here is what
lets the prose read as instruction rather than as a list of prohibitions.

Reads the tool call as JSON on stdin, exits 2 with the reason on stderr when a command
carries one of the forms, and exits 0 silently otherwise — including on anything it
cannot parse, because a guard that blocks every command is worse than no guard.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

SEGMENT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
NO_VERIFY_COMMANDS = ("commit", "push", "merge", "rebase")

REFUSALS = {
    "force": (
        "Refused: bare force-push. Force-push a feature branch with --force-with-lease, "
        "never with --force or -f, and never the base branch at all."
    ),
    "no-verify": (
        "Refused: --no-verify. A hook that refuses is the project talking: fix what it "
        "names and run the command again, or stop and say the hook itself is broken."
    ),
    "admin": "Refused: gh pr merge --admin. A merge that needs it is one a human should look at.",
}


def _words(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def _is_force(word: str) -> bool:
    """`--force` or a short cluster carrying `f`; `--force-with-lease` is the sanctioned form."""
    if word == "--force":
        return True
    return word.startswith("-") and not word.startswith("--") and "f" in word[1:]


def _has_short(words: list[str], letter: str) -> bool:
    return any(w.startswith("-") and not w.startswith("--") and letter in w[1:] for w in words)


def offence(command: str) -> str | None:
    """The refusal a command earns, or None when it may run."""
    for segment in SEGMENT.split(command):
        words = _words(segment)
        if not words:
            continue
        if words[0] == "git":
            subcommand = next((w for w in words[1:] if not w.startswith("-")), "")
            rest = words[words.index(subcommand) + 1 :] if subcommand else []
            if subcommand == "push" and any(_is_force(w) for w in rest):
                return REFUSALS["force"]
            if subcommand in NO_VERIFY_COMMANDS and "--no-verify" in rest:
                return REFUSALS["no-verify"]
            if subcommand == "commit" and _has_short(rest, "n"):
                return REFUSALS["no-verify"]
        elif words[:3] == ["gh", "pr", "merge"] and "--admin" in words:
            return REFUSALS["admin"]
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    reason = offence(command)
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
