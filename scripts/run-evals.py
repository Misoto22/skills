#!/usr/bin/env python3
"""Keep the evaluation cases complete, consistent, and ready to run.

Triggering is decided by a model, so nothing here scores a skill: that needs an
agent and a key, and a check that cannot run in CI is a check nobody runs. What
this does enforce is the part that rots silently — every published skill having
cases at all, each one naming what should happen instead when it must not fire,
and every stated hand-off pointing at a skill that exists.

  python3 scripts/run-evals.py --check           Fail on a missing or malformed suite
  python3 scripts/run-evals.py --report          Print every case
  python3 scripts/run-evals.py --report email    Print one skill's cases, ready to paste

A `non_trigger` is the half that matters. A skill that fires on everything looks
excellent in its own trigger cases, and the cost lands on whichever skill it
took the prompt from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = ROOT / "plugins"
EVALS_ROOT = ROOT / "evals"

MINIMUM_TRIGGERS = 3
MINIMUM_NON_TRIGGERS = 2


def published_skills() -> list[str]:
    return sorted(path.parent.name for path in PLUGINS_ROOT.glob("*/skills/*/SKILL.md"))


def load(skill: str, errors: list[str]) -> dict | None:
    path = EVALS_ROOT / skill / "evals.json"
    if not path.is_file():
        errors.append(
            f"{path.relative_to(ROOT)}: missing. Every published skill needs trigger and"
            " non-trigger cases; the description is otherwise unfalsifiable."
        )
        return None
    try:
        suite = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"{path.relative_to(ROOT)}: cannot read JSON: {error}")
        return None
    if not isinstance(suite, dict):
        errors.append(f"{path.relative_to(ROOT)}: root must be an object")
        return None
    return suite


def check(skills: list[str]) -> list[str]:
    errors: list[str] = []
    known = set(skills)
    for skill in skills:
        suite = load(skill, errors)
        if suite is None:
            continue
        where = (EVALS_ROOT / skill / "evals.json").relative_to(ROOT)
        if suite.get("skill") != skill:
            errors.append(f"{where}: 'skill' must be {skill!r}")

        seen: set[str] = set()
        for section, minimum in (
            ("triggers", MINIMUM_TRIGGERS),
            ("non_triggers", MINIMUM_NON_TRIGGERS),
            ("behaviors", 0),
        ):
            cases = suite.get(section)
            if not isinstance(cases, list):
                errors.append(f"{where}: {section} must be a list")
                continue
            if len(cases) < minimum:
                errors.append(f"{where}: {section} has {len(cases)} cases, needs at least {minimum}")
            for index, case in enumerate(cases):
                errors.extend(_check_case(where, section, index, case, seen, known, skill))

    for path in sorted(EVALS_ROOT.glob("*/evals.json")):
        if path.parent.name not in known:
            errors.append(
                f"{path.relative_to(ROOT)}: no published skill named {path.parent.name!r}."
                " Retired cases belong with the retired skill."
            )
    return errors


def _check_case(
    where: Path,
    section: str,
    index: int,
    case: object,
    seen: set[str],
    known: set[str],
    skill: str,
) -> list[str]:
    errors: list[str] = []
    label = f"{where}: {section}[{index}]"
    if not isinstance(case, dict):
        return [f"{label} must be an object"]

    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id.strip():
        errors.append(f"{label} needs a nonempty id")
    elif case_id in seen:
        errors.append(f"{label} repeats the id {case_id!r}")
    else:
        seen.add(case_id)

    prompt = case.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append(f"{label} needs a nonempty prompt")

    if section == "behaviors":
        expectations = case.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            errors.append(f"{label} needs at least one expectation")
    else:
        expected = case.get("expected")
        if not isinstance(expected, str) or not expected.strip():
            errors.append(f"{label} needs an 'expected' saying what should happen")

    routes_to = case.get("routes_to")
    if routes_to is not None:
        if section != "non_triggers":
            errors.append(f"{label}: routes_to belongs on a non_trigger")
        elif routes_to == skill:
            errors.append(f"{label}: routes_to names its own skill")
        elif routes_to not in known:
            errors.append(f"{label}: routes_to names {routes_to!r}, which is not published")
    return errors


def report(skills: list[str]) -> None:
    for skill in skills:
        suite = load(skill, [])
        if suite is None:
            continue
        print(f"\n{'=' * 72}\n{skill}\n{'=' * 72}")
        for section in ("triggers", "non_triggers", "behaviors"):
            cases = suite.get(section) or []
            if not cases:
                continue
            print(f"\n-- {section} ({len(cases)}) --")
            for case in cases:
                print(f"\n[{case.get('id')}]")
                print(f"  prompt:   {case.get('prompt')}")
                if section == "behaviors":
                    for expectation in case.get("expectations", []):
                        print(f"  expect:   {expectation}")
                else:
                    print(f"  expected: {case.get('expected')}")
                if case.get("routes_to"):
                    print(f"  routes to: {case['routes_to']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on a missing or malformed suite")
    parser.add_argument(
        "--report",
        nargs="?",
        const="*",
        metavar="SKILL",
        help="print every case, or one skill's",
    )
    args = parser.parse_args()
    if not args.check and not args.report:
        parser.error("pass --check or --report")

    skills = published_skills()
    if not skills:
        print("error: no published skills found", file=sys.stderr)
        return 1

    if args.report:
        selected = skills if args.report == "*" else [args.report]
        unknown = [skill for skill in selected if skill not in skills]
        if unknown:
            print(f"error: no published skill named {unknown[0]!r}", file=sys.stderr)
            return 1
        report(selected)
        if not args.check:
            return 0

    errors = check(skills)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    counts = {skill: load(skill, []) or {} for skill in skills}
    total = sum(len(suite.get(section) or []) for suite in counts.values() for section in SECTIONS)
    print(f"{total} cases across {len(skills)} skills")
    return 0


SECTIONS = ("triggers", "non_triggers", "behaviors")


if __name__ == "__main__":
    raise SystemExit(main())
