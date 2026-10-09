"""How the dev hooks reach a command's own words inside a line of shell source.

guard-git and orchestrate both see a tool call as shell text, and both need the same two
steps before they can judge it: split the line where one command ends and the next
begins, then strip the wrappers that run a command rather than describe it. One copy, so
a wrapper taught to one hook is taught to both.

Imported by the hooks beside it, which put their own directory on `sys.path`; it is not a
hook and is registered nowhere.
"""

from __future__ import annotations

import re

# `&&`, `||`, `;`, `|` and a newline each start a new command.
SEGMENT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
ENV_COMMANDS = ("env", "/usr/bin/env", "/bin/env")
WRAPPER_COMMANDS = ("command", "exec")
ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def unwrap(words: list[str]) -> list[str]:
    """Remove shell wrappers that run, rather than merely describe, their command.

    ``command git``, ``exec tee`` and ``env KEY=value sed`` would otherwise hide the
    executable from the checks after this. Kept deliberately small: recognising an
    arbitrary word as a wrapper turns harmless prose or inspection commands into false
    refusals.
    """
    words = list(words)
    while words:
        if words[0] in WRAPPER_COMMANDS:
            words.pop(0)
            continue
        if words[0] not in ENV_COMMANDS:
            break
        words.pop(0)
        while words and ENV_ASSIGNMENT.fullmatch(words[0]):
            words.pop(0)
    return words
