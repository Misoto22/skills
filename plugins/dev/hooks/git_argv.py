"""How the dev hooks read a git command line: global options, subcommand, and what follows.

`git -C /repo push --force` and `git -c k=v commit --no-verify` put options between `git`
and its subcommand, so taking the first non-dash word reads them as `git /repo` and
`git k=v` and lets both through. Both hooks that judge git commands read them here.

Imported by the hooks beside it, which put their own directory on `sys.path`; it is not a
hook and is registered nowhere.
"""

from __future__ import annotations

import os

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


def is_force(word: str) -> bool:
    """`--force` or a short cluster carrying `f`; `--force-with-lease` is the sanctioned form."""
    if word == "--force":
        return True
    return word.startswith("-") and not word.startswith("--") and "f" in word[1:]


def is_forced_push(rest: list[str]) -> bool:
    """A force flag, or a `+refspec`, which forces that one ref with no flag at all."""
    return any(is_force(word) or word.startswith("+") for word in rest)
