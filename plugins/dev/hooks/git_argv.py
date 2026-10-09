"""How the dev hooks read a git command line: global options, subcommand, and what follows.

`git -C /repo push --force` and `git -c k=v commit --no-verify` put options between `git`
and its subcommand, so taking the first non-dash word reads them as `git /repo` and
`git k=v` and lets both through. Both hooks that judge git commands read them here.

Imported by the hooks beside it, which put their own directory on `sys.path`; it is not a
hook and is registered nowhere.
"""

from __future__ import annotations

import os
import re

# Global options that take their value as the next word. Every other leading `-…` word is
# a flag, or carries its value after `=`.
OPTIONS_WITH_VALUE = (
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--config-env",
    "--super-prefix",
    "--attr-source",
)
# Pointing this at another directory for one command skips the repository's hooks.
HOOKS_PATH_KEY = "core.hookspath"
# `GIT_CONFIG_PARAMETERS` holds space-separated, single-quoted entries: `'key'='value'`,
# `'key=value'` or a bare `'key'`. git reads a key only where a quoted entry begins.
PARAMETERS_HOOKS_PATH = re.compile(r"(?:^|\s)'core\.hookspath(?:'|=)", re.IGNORECASE)
CONFIG_KEY_VARIABLE = re.compile(r"GIT_CONFIG_KEY_\d+")


def split(args: list[str]) -> tuple[list[tuple[str, str | None]], str, list[str]]:
    """(global options, subcommand, its arguments) for the words after `git`.

    Each option comes back with its separate value, or None when it has none. The
    subcommand is empty when there is none, as in `git --version`.
    """
    options: list[tuple[str, str | None]] = []
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        takes_value = option in OPTIONS_WITH_VALUE
        options.append((option, args[index + 1] if takes_value and index + 1 < len(args) else None))
        index += 2 if takes_value else 1
    if index >= len(args):
        return options, "", []
    return options, args[index], args[index + 1 :]


def directory(options: list[tuple[str, str | None]]) -> str:
    """Where `-C` moves git before it reads a relative path; empty for where it started."""
    return os.path.join("", *(value for option, value in options if option == "-C" and value))


def config_keys(options: list[tuple[str, str | None]]) -> list[str]:
    """The config keys `-c` and `--config-env` set for this one command, lowercased.

    Section and key names are case-insensitive to git, so `core.hooksPath` and
    `CORE.HOOKSPATH` are the same setting.
    """
    keys = []
    for option, value in options:
        if option in ("-c", "--config-env") and value is not None:
            setting = value
        elif option.startswith("--config-env="):
            setting = option.removeprefix("--config-env=")
        else:
            continue
        keys.append(setting.split("=", 1)[0].lower())
    return keys


def overrides_hooks(options: list[tuple[str, str | None]]) -> bool:
    """Whether the command redirects `core.hooksPath`, which skips hooks like --no-verify."""
    return HOOKS_PATH_KEY in config_keys(options)


def env_overrides_hooks(environment: dict[str, str]) -> bool:
    """Whether variables set for the command redirect `core.hooksPath`, as `-c` would.

    A `GIT_CONFIG_KEY_<n>` naming it counts whatever `GIT_CONFIG_COUNT` says here, since
    the count can already be exported in the shell.
    """
    if PARAMETERS_HOOKS_PATH.search(environment.get("GIT_CONFIG_PARAMETERS", "")):
        return True
    return any(
        CONFIG_KEY_VARIABLE.fullmatch(name) and value.lower() == HOOKS_PATH_KEY
        for name, value in environment.items()
    )


def is_force(word: str) -> bool:
    """`--force` or a short cluster carrying `f`; `--force-with-lease` is the sanctioned form."""
    if word == "--force":
        return True
    return word.startswith("-") and not word.startswith("--") and "f" in word[1:]


def is_forced_push(rest: list[str]) -> bool:
    """A force flag, or a `+refspec`, which forces that one ref with no flag at all."""
    return any(is_force(word) or word.startswith("+") for word in rest)
