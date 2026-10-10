#!/usr/bin/env python3
"""Export, check, diff, apply, and review a plan for a GitHub account's star lists.

Run it through run.sh, which finds or installs Python and gh first:

  sh scripts/run.sh export --out plan.json   Write the live account as a plan
  sh scripts/run.sh check plan.json          Validate a plan against the account
  sh scripts/run.sh diff plan.json           Show what applying it would change
  sh scripts/run.sh apply plan.json --yes    Back up, apply, and verify
  sh scripts/run.sh review plan.json         Write an HTML page to review a plan

Restoring a backup is `apply <backup>.json --yes`: a backup is a plan.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if sys.version_info < (3, 9):  # noqa: UP036 - the guard has to run on the old interpreter it rejects
    sys.exit("star-lists needs Python 3.9 or newer; run it through scripts/run.sh")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lists_changes as changes
import lists_plan as plans
import lists_review as review
from github_api import GitHub, GitHubError

EXIT_OK, EXIT_FAILED, EXIT_NEEDS_CONFIRMATION = 0, 1, 2


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_plan(path: str) -> dict:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise plans.PlanError(f"cannot read {path}: {error}") from error
    return plans.load(document)


def _checked(github: GitHub, path: str, allow_unassigned: bool) -> tuple[dict, dict]:
    plan = _read_plan(path)
    snapshot = github.snapshot()
    errors = plans.validate(plan, snapshot, allow_unassigned=allow_unassigned)
    if errors:
        raise plans.PlanError("the plan cannot be applied:\n  " + "\n  ".join(errors))
    return plan, snapshot


def cmd_export(github: GitHub, args: argparse.Namespace) -> int:
    snapshot = github.snapshot()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = Path(args.out or f"star-lists-{snapshot['login']}-{stamp}.json")
    _write_json(out, plans.snapshot_to_plan(snapshot))
    unassigned = sum(
        1 for repo in snapshot["stars"] if not any(repo["name"] in i["items"] for i in snapshot["lists"])
    )
    print(
        f"Wrote {out}: {len(snapshot['stars'])} starred repositories, {len(snapshot['lists'])} lists, "
        f"{unassigned} repositories in no list."
    )
    return EXIT_OK


def cmd_check(github: GitHub, args: argparse.Namespace) -> int:
    plan, snapshot = _checked(github, args.plan, args.allow_unassigned)
    multi = sum(1 for keys in plan["assignments"].values() if len(keys) > 1)
    lists, repos = len(plan["lists"]), len(snapshot["stars"])
    print(f"OK: {lists} lists, {repos} repositories, {multi} in more than one list.")
    return EXIT_OK


def cmd_diff(github: GitHub, args: argparse.Namespace) -> int:
    plan, snapshot = _checked(github, args.plan, args.allow_unassigned)
    print(changes.render(changes.compute(plan, snapshot)))
    return EXIT_OK


def cmd_apply(github: GitHub, args: argparse.Namespace) -> int:
    plan, snapshot = _checked(github, args.plan, args.allow_unassigned)
    pending = changes.compute(plan, snapshot)
    print(changes.render(pending))
    if pending.empty():
        return EXIT_OK
    if not args.yes:
        print("\nNothing was written. Re-run with --yes to apply these changes.")
        return EXIT_NEEDS_CONFIRMATION
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = Path(args.backup_dir) / f"star-lists-{snapshot['login']}-{stamp}.json"
    _write_json(backup, plans.snapshot_to_plan(snapshot))
    print(f"\nBacked up the current state to {backup}. Undo with: sh scripts/run.sh apply {backup} --yes")
    changes.apply(github, plan, snapshot, pending)
    after = github.snapshot()
    refreshed = _resolve_created_ids(plan, after)
    remaining = changes.compute(refreshed, after)
    if not remaining.empty():
        print("Applied, but the account still differs from the plan:\n" + changes.render(remaining))
        return EXIT_FAILED
    print("Applied and verified: the account now matches the plan.")
    return EXIT_OK


def _resolve_created_ids(plan: dict, snapshot: dict) -> dict:
    """Give lists the apply created, or recreated from a backup, their new ids, matched by name."""
    live_ids = {item["id"] for item in snapshot["lists"]}
    by_name = {item["name"]: item["id"] for item in snapshot["lists"]}
    lists = [
        item if item.get("id") in live_ids else dict(item, id=by_name.get(item["name"]))
        for item in plan["lists"]
    ]
    return dict(plan, lists=lists)


def cmd_review(github: GitHub, args: argparse.Namespace) -> int:
    plan = _read_plan(args.plan)
    out = Path(args.out or Path(args.plan).with_suffix(".html"))
    out.write_text(review.render(plan), encoding="utf-8")
    print(f"Wrote {out}. Open it in a browser, adjust, then save the edited plan from the page.")
    return EXIT_OK


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="star-lists", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write the live account as a plan")
    export.add_argument("--out", help="file to write (default: star-lists-<login>-<timestamp>.json)")
    for name, help_text in (
        ("check", "validate a plan against the live account"),
        ("diff", "show what applying a plan would change"),
        ("apply", "back up, apply a plan, and verify the result"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("plan")
        command.add_argument(
            "--allow-unassigned", action="store_true", help="allow starred repositories in no list"
        )
    commands.choices["apply"].add_argument("--yes", action="store_true", help="make the writes")
    commands.choices["apply"].add_argument("--backup-dir", default="star-lists-backups")
    review_command = commands.add_parser("review", help="write an HTML page for reviewing a plan")
    review_command.add_argument("plan")
    review_command.add_argument("--out")
    return parser.parse_args(argv)


COMMANDS = {
    "export": cmd_export,
    "check": cmd_check,
    "diff": cmd_diff,
    "apply": cmd_apply,
    "review": cmd_review,
}


def main(argv: list[str] | None = None, github: GitHub | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return COMMANDS[args.command](github or GitHub(), args)
    except (plans.PlanError, GitHubError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
