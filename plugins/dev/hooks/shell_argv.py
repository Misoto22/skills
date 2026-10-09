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


def unwrap_env(words: list[str]) -> tuple[dict[str, str], list[str]]:
    """The variables a command line sets for its command, and the command's own words.

    ``KEY=value git``, ``command git``, ``exec tee`` and ``env KEY=value sed`` would
    otherwise hide the executable from the checks after this, and the assignments are
    returned because some of them change what the command does. Kept deliberately small:
    recognising an arbitrary word as a wrapper turns harmless prose or inspection
    commands into false refusals.
    """
    environment: dict[str, str] = {}
    words = list(words)
    while words:
        if ENV_ASSIGNMENT.fullmatch(words[0]):
            key, _, value = words.pop(0).partition("=")
            environment[key] = value
        elif words[0] in WRAPPER_COMMANDS or words[0] in ENV_COMMANDS:
            words.pop(0)
        else:
            break
    return environment, words


def unwrap(words: list[str]) -> list[str]:
    """The command's own words, past every leading assignment and wrapper."""
    return unwrap_env(words)[1]
