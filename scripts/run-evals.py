#!/usr/bin/env python3
"""Keep the evaluation cases complete and consistent, and score them against a model.

Two halves, deliberately separated by what they cost. `--check` is structural and
free: every published skill has cases at all, each one names what should happen
instead when it must not fire, and every stated hand-off points at a skill that
exists. It runs on every push.

`--run` is the half that actually falsifies a description. It asks a model which
skill a prompt should route to, given every published description and nothing
else, and compares the answer to what the suite says. It needs a key and costs
money, so it runs weekly and on demand rather than in the pull-request gate — a
description that quietly starts stealing another skill's prompts is otherwise
invisible until a user reports it.

  python3 scripts/run-evals.py --check           Fail on a missing or malformed suite
  python3 scripts/run-evals.py --report          Print every case
  python3 scripts/run-evals.py --report email    Print one skill's cases, ready to paste
  python3 scripts/run-evals.py --run             Score every case against a model
  python3 scripts/run-evals.py --run email       Score one skill's cases

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


# The routing question, asked with nothing but the descriptions to answer it
# from. That is the point: a description is the only thing a client sees before
# deciding, so scoring against anything richer would grade a different artefact.
ROUTER_SYSTEM = """You are the router in an agent harness. You are given every skill \
available to the agent, each with the description its author wrote, and one user prompt.

Decide which single skill should fire for that prompt, or that none should.

A skill fires when the prompt is the work its description claims. It does not fire \
because the topic is adjacent, because the description mentions a word the prompt \
also uses, or because it is the closest of several poor matches. Answering "none" \
is correct far more often than it feels — most prompts are ordinary work no skill \
was written for.

Judge only from the descriptions below. Do not use anything you know about these \
skills from elsewhere.

<skills>
{catalogue}
</skills>"""

ROUTING_SCHEMA = {
    "type": "object",
    "properties": {
        "skill": {
            "type": "string",
            "description": "The name of the one skill that should fire, or 'none'.",
        },
        "reason": {
            "type": "string",
            "description": "One sentence naming the part of the description that decided it.",
        },
    },
    "required": ["skill", "reason"],
    "additionalProperties": False,
}
# Classification, so the cheapest depth that holds. Thinking stays on: disabling
# it is what leaks `<thinking>` tags into the answer, and effort is the lever
# that actually costs less.
ROUTER_MODEL = "claude-opus-5"
ROUTER_EFFORT = "low"
# Adaptive thinking and the response share this ceiling, so it is not the ~256 a
# bare classification would need.
ROUTER_MAX_TOKENS = 2048


def descriptions() -> dict[str, str]:
    """Read each published skill's description — the only field routing sees."""

    found: dict[str, str] = {}
    for path in sorted(PLUGINS_ROOT.glob("*/skills/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("description:"):
                found[path.parent.name] = line.split(":", 1)[1].strip()
                break
    return found


def route(client: object, catalogue: str, prompt: str) -> tuple[str, str]:
    """Ask which skill fires, and return its name plus the stated reason."""

    response = client.messages.create(  # type: ignore[attr-defined]
        model=ROUTER_MODEL,
        max_tokens=ROUTER_MAX_TOKENS,
        # One breakpoint on the catalogue: it is byte-identical across every
        # case in the run, and the prompt that follows it is the only variable.
        system=[
            {
                "type": "text",
                "text": ROUTER_SYSTEM.format(catalogue=catalogue),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={"effort": ROUTER_EFFORT, "format": {"type": "json_schema", "schema": ROUTING_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    # A declined request returns 200 with an empty or partial content list, so
    # this has to be read before the content is indexed.
    if response.stop_reason == "refusal":
        return "refused", "the request was declined by the model's safety classifiers"
    answer = next((block.text for block in response.content if block.type == "text"), "")
    parsed = json.loads(answer)
    return parsed["skill"], parsed["reason"]


def run(skills: list[str]) -> list[str]:
    """Score every case, and return one line per case that routed wrongly."""

    try:
        import anthropic
    except ImportError:
        raise SystemExit(
            "error: --run needs the Anthropic SDK. Install the pinned version:\n"
            '  python3 -m pip install "$(python3 scripts/ci-pins.py spec anthropic)"'
        ) from None

    catalogue = "\n".join(f"<skill name={name!r}>{text}</skill>" for name, text in descriptions().items())
    client = anthropic.Anthropic()
    known = set(descriptions())
    failures: list[str] = []
    scored = 0

    for skill in skills:
        suite = load(skill, [])
        if suite is None:
            continue
        for section in ("triggers", "non_triggers"):
            for case in suite.get(section) or []:
                answer, reason = route(client, catalogue, case["prompt"])
                scored += 1
                verdict = _judge(skill, section, case, answer, known)
                if verdict is None:
                    print(f"  pass  {skill}/{case['id']}")
                    continue
                failures.append(f"{skill}/{case['id']}: {verdict}; routed to {answer!r} — {reason}")
                print(f"  FAIL  {skill}/{case['id']} → {answer}")

    print(f"\n{scored} cases scored, {len(failures)} failed")
    return failures


def _judge(skill: str, section: str, case: dict, answer: str, known: set[str]) -> str | None:
    """Return why the routing was wrong, or None when it was right.

    A non-trigger is satisfied by anything that is not this skill — including
    `none`, which is the honest answer for most of them. Only a case that names
    `routes_to` asserts where the prompt should have gone instead.
    """

    if section == "triggers":
        return None if answer == skill else f"expected {skill!r}"
    if answer == skill:
        return f"fired on a non-trigger; expected {case.get('routes_to') or 'no skill'}"
    routes_to = case.get("routes_to")
    if routes_to and answer != routes_to:
        return f"expected the hand-off to {routes_to!r}"
    if answer not in known and answer not in {"none", "refused"}:
        return f"named {answer!r}, which is not a published skill"
    return None


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
    parser.add_argument(
        "--run",
        nargs="?",
        const="*",
        metavar="SKILL",
        help="score every case against a model; needs ANTHROPIC_API_KEY",
    )
    args = parser.parse_args()
    if not args.check and not args.report and not args.run:
        parser.error("pass --check, --report, or --run")

    skills = published_skills()
    if not skills:
        print("error: no published skills found", file=sys.stderr)
        return 1

    for requested in (args.report, args.run):
        if requested and requested != "*" and requested not in skills:
            print(f"error: no published skill named {requested!r}", file=sys.stderr)
            return 1

    if args.report:
        report(skills if args.report == "*" else [args.report])
        if not args.check and not args.run:
            return 0

    if args.run:
        # Structural first: scoring a malformed suite bills a model to discover
        # what a free check already knew.
        errors = check(skills)
        if errors:
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            return 1
        failures = run(skills if args.run == "*" else [args.run])
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 1 if failures else 0

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
