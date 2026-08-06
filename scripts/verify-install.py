#!/usr/bin/env python3
"""Assert an installed skill tree is complete and self-contained.

Run this against whatever a real installer produced — a Claude Code plugin
cache, a Codex plugin root, an ~/.agents/skills copy, an unpacked .skill — so
the guarantee is tested on the artifact the agent actually reads, not on the
repository it came from.

  python3 scripts/verify-install.py <dir>...

Each argument is either a skill directory (contains SKILL.md) or a directory to
search for them. Every skill found must satisfy the same contract.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TEXT_SUFFIXES = {".md", ".json", ".py", ".txt", ".yaml", ".yml", ".sh"}
REQUIRED_SHARED = ("shared/tone.md", "shared/format.md")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
NAME_LINE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)

# The two constructions that install cleanly and then dangle at read time.
NON_PORTABLE_TEXT = (
    ("${CLAUDE_", "host-specific variable no other agent expands"),
    ("../", "path that climbs out of the installed skill"),
)


def verify(roots: list[Path]) -> list[str]:
    errors: list[str] = []
    skills = _discover(roots, errors)
    for skill in skills:
        _verify_skill(skill, errors)
    return errors


def _discover(roots: list[Path], errors: list[str]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            errors.append(f"{root}: not a directory")
            continue
        if (resolved / "SKILL.md").is_file():
            found.add(resolved)
            continue
        nested = {path.parent for path in resolved.rglob("SKILL.md")}
        if not nested:
            errors.append(f"{root}: contains no SKILL.md")
        found |= nested
    return sorted(found)


def _verify_skill(skill: Path, errors: list[str]) -> None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")

    match = NAME_LINE.search(text.split("---", 2)[1] if text.startswith("---") else "")
    if not match:
        errors.append(f"{skill}: SKILL.md has no frontmatter name")
    elif match.group(1) != skill.name:
        errors.append(f"{skill}: frontmatter name {match.group(1)!r} != directory name")

    for relative in REQUIRED_SHARED:
        if not (skill / relative).is_file():
            errors.append(f"{skill}: missing {relative} — the install dropped shared material")

    for target in MARKDOWN_LINK.findall(text):
        if target.startswith(("https://", "http://", "#", "mailto:")):
            continue
        relative = target.split("#", 1)[0]
        if not relative:
            continue
        if not (skill / relative).is_file():
            errors.append(f"{skill}: SKILL.md references {target}, which is not installed")

    for path in sorted(skill.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for fragment, reason in NON_PORTABLE_TEXT:
            if fragment in content:
                errors.append(f"{path}: contains {fragment!r} — a {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help="skill name that must be present (repeatable)",
    )
    args = parser.parse_args()

    errors = verify(args.roots)
    installed = {skill.name for skill in _discover(args.roots, [])}
    for name in args.expect:
        if name not in installed:
            errors.append(f"expected skill {name!r} was not installed; found {sorted(installed)}")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"installed skills verified: {', '.join(sorted(installed))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
