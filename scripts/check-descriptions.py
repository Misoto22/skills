#!/usr/bin/env python3
"""Hold every published description to the rules CONTRIBUTING states for it.

The description is the only field that decides whether a skill ever fires, and
it is the one field nothing checked. The rules here are the ones already written
down — one line, concrete about when to use it, ending with what it is not for —
plus a ceiling and an overlap bound that only matter as the catalogue grows.

  python3 scripts/check-descriptions.py            Fail on a violation
  python3 scripts/check-descriptions.py --report   Print the lengths and overlaps too

Overlap is the one rule that cannot be checked a skill at a time. Two
descriptions sharing a long run of words are two skills competing for the same
prompt, and the loser misfires in a way no test of either skill alone can see.
"""

from __future__ import annotations

import argparse
import re
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"

# The platform truncates well past this; the ceiling is here so a description
# grows by being rewritten rather than by being appended to.
MAX_CHARACTERS = 1024
MIN_CHARACTERS = 120
# The longest run two descriptions share today is 6 words, between synastry and
# synastry-reading — a two-stage pair is the case that presses hardest on this.
# Seven leaves room to describe neighbouring subjects without room to describe
# the same one twice. Read `--report` before raising it: the headroom is a word.
MAX_SHARED_RUN = 7

WORD = re.compile(r"[\w']+")
NEGATIVE_SCOPE = re.compile(r"(?i)\bnot for\b|\bnot intended for\b|\bdo not use\b")
PLACEHOLDER = re.compile(r"(?i)\bplaceholder\b|\bTODO\b|\bFIXME\b")


def descriptions() -> dict[str, tuple[Path, str]]:
    """Return {skill name: (SKILL.md, description)} for every published skill."""

    found: dict[str, tuple[Path, str]] = {}
    for skill_file in sorted(PLUGINS_ROOT.glob("*/skills/*/SKILL.md")):
        found[skill_file.parent.name] = (skill_file, _description(skill_file))
    return found


def _description(skill_file: Path) -> str:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines[:20]):
        if line.startswith("description:"):
            value = line[len("description:") :].strip()
            # A folded scalar leaves the value on the following lines, which the
            # frontmatter parser does not read. Report it as the empty string.
            following = lines[index + 1] if index + 1 < len(lines) else ""
            return "" if value in {"", ">", "|", ">-", "|-"} or following.startswith("  ") else value
    return ""


def check(found: dict[str, tuple[Path, str]]) -> list[str]:
    errors: list[str] = []
    for skill_file, description in found.values():
        where = skill_file.relative_to(ROOT)
        if not description:
            errors.append(f"{where}: description must be one nonempty line")
            continue
        if PLACEHOLDER.search(description):
            errors.append(
                f"{where}: description is still the scaffold placeholder. It is the only field"
                " that decides whether the skill ever fires, so it has to be written before"
                " the skill is published."
            )
        if len(description) > MAX_CHARACTERS:
            errors.append(f"{where}: description is {len(description)} characters, over {MAX_CHARACTERS}")
        if len(description) < MIN_CHARACTERS:
            errors.append(
                f"{where}: description is {len(description)} characters, under {MIN_CHARACTERS}."
                " Name the phrasings and artefacts that should trigger it."
            )
        if not NEGATIVE_SCOPE.search(description):
            errors.append(
                f"{where}: description never says what the skill is not for. Without a boundary"
                " it competes for every neighbouring prompt."
            )

    for (_, (first_file, first_text)), (second, (_, second_text)) in combinations(found.items(), 2):
        run, shared = _longest_shared_run(first_text, second_text)
        if run > MAX_SHARED_RUN:
            errors.append(
                f"{first_file.relative_to(ROOT)}: shares {run} consecutive words with {second}"
                f" — {shared!r}. Two skills describing the same prompt is how one of them misfires."
            )
    return errors


def _longest_shared_run(first: str, second: str) -> tuple[int, str]:
    """Return the longest run of words the two descriptions share, and the run itself."""

    left = WORD.findall(first.lower())
    right = WORD.findall(second.lower())
    best_length = 0
    best_start = 0
    # Standard longest-common-substring table, one row at a time over the words.
    previous = [0] * (len(right) + 1)
    for i in range(1, len(left) + 1):
        current = [0] * (len(right) + 1)
        for j in range(1, len(right) + 1):
            if left[i - 1] == right[j - 1]:
                current[j] = previous[j - 1] + 1
                if current[j] > best_length:
                    best_length = current[j]
                    best_start = i - current[j]
        previous = current
    return best_length, " ".join(left[best_start : best_start + best_length])


def report(found: dict[str, tuple[Path, str]]) -> None:
    # Widened to the longest name rather than to a constant: a fixed column is a
    # number that goes stale on the next skill, and the row that overflows it is
    # the one whose length nobody can then read off.
    width = max(len("skill"), *(len(name) for name in found))
    print(f"{'skill':<{width}}{'chars':>8}  ends with a boundary")
    for name, (_, description) in sorted(found.items()):
        boundary = "yes" if NEGATIVE_SCOPE.search(description) else "NO"
        print(f"{name:<{width}}{len(description):>8}  {boundary}")

    print(f"\nlongest shared run of words (ceiling {MAX_SHARED_RUN}):")
    overlaps = sorted(
        (
            (_longest_shared_run(first_text, second_text)[0], first, second)
            for (first, (_, first_text)), (second, (_, second_text)) in combinations(found.items(), 2)
        ),
        reverse=True,
    )
    for run, first, second in overlaps[:10]:
        print(f"  {run:>2}  {first} / {second}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="print lengths and overlaps as well")
    args = parser.parse_args()

    found = descriptions()
    if not found:
        print("error: no published skills found", file=sys.stderr)
        return 1

    errors = check(found)
    if args.report:
        report(found)
        print()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{len(found)} descriptions pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
