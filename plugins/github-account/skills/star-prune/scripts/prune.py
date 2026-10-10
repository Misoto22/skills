#!/usr/bin/env python3
"""Find archived, deprecated and dormant stars; unstar the confirmed ones; restore them.

Run it through run.sh, which finds or installs Python and gh first:

  sh scripts/run.sh scan --out prune.json       Flag stars and propose an action for each
  sh scripts/run.sh apply prune.json --yes      Back up, unstar every "unstar", and verify
  sh scripts/run.sh restore <backup>.json --yes Re-star and put each repository back in its lists
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if sys.version_info < (3, 9):  # noqa: UP036 - the guard has to run on the old interpreter it rejects
    sys.exit("star-prune needs Python 3.9 or newer; run it through scripts/run.sh")

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "shared"))

import prune_rules as rules  # noqa: E402 - the skill directories go on sys.path first
from github_api import GitHub, GitHubError  # noqa: E402 - the skill directories go on sys.path first

BACKUP_FORMAT = "github-star-prune-backup/v1"
EXIT_OK, EXIT_FAILED, EXIT_NEEDS_CONFIRMATION = 0, 1, 2


class PruneError(ValueError):
    """A candidates or backup file that cannot be used as given."""


def _count(number: int, singular: str, plural: str) -> str:
    return f"{number} {singular if number == 1 else plural}"


def _now() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017 - datetime.UTC needs Python 3.11


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _read(path: str, expected_format: str, login: str) -> dict:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PruneError(f"cannot read {path}: {error}") from error
    if not isinstance(document, dict) or document.get("format") != expected_format:
        raise PruneError(f"{path} is not a {expected_format} file")
    if document.get("account") != login:
        raise PruneError(f"{path} is for {document.get('account')!r} but gh is signed in as {login!r}")
    return document


def cmd_scan(github: GitHub, args: argparse.Namespace) -> int:
    snapshot = github.snapshot()
    candidates = rules.classify(snapshot, _now(), args.dormant_years, args.old_star_years)
    out = Path(args.out or f"star-prune-{snapshot['login']}-{_stamp()}.json")
    _write_json(
        out,
        {
            "format": rules.FORMAT,
            "account": snapshot["login"],
            "thresholds": {"dormant_years": args.dormant_years, "old_star_years": args.old_star_years},
            "candidates": candidates,
        },
    )
    print(f"Wrote {out}: {len(candidates)} of {len(snapshot['stars'])} starred repositories flagged.")
    for reason in rules.REASONS:
        flagged = [c["name"] for c in candidates if c["reasons"][0] == reason]
        if flagged:
            more = " ..." if len(flagged) > 5 else ""
            print(f"  {reason:<10} {len(flagged):>3}  {', '.join(flagged[:5])}{more}")
    proposed = sum(1 for c in candidates if c["action"] == "unstar")
    print(f"Proposed: unstar {proposed}, keep {len(candidates) - proposed}.")
    return EXIT_OK


def _targets(document: dict, snapshot: dict) -> list[dict]:
    starred = {star["name"] for star in snapshot["stars"]}
    for candidate in document.get("candidates", []):
        if candidate.get("action") not in rules.ACTIONS:
            raise PruneError(f"{candidate.get('name')}: action must be one of {', '.join(rules.ACTIONS)}")
    return [c for c in document["candidates"] if c["action"] == "unstar" and c["name"] in starred]


def cmd_apply(github: GitHub, args: argparse.Namespace) -> int:
    snapshot = github.snapshot()
    targets = _targets(_read(args.candidates, rules.FORMAT, snapshot["login"]), snapshot)
    if not targets:
        print("Nothing to unstar: no candidate marked unstar is still starred.")
        return EXIT_OK
    print(f"{_count(len(targets), 'repository', 'repositories')} to unstar:")
    for target in targets:
        print(f"  unstar  {target['name']} ({', '.join(target['reasons'])})")
    if not args.yes:
        print("\nNothing was written. Re-run with --yes to unstar these repositories.")
        return EXIT_NEEDS_CONFIRMATION
    lists = {item["name"]: item["id"] for item in snapshot["lists"]}
    member_of = {
        star["name"]: [item for item in snapshot["lists"] if star["name"] in item["items"]]
        for star in snapshot["stars"]
    }
    backup = Path(args.backup_dir) / f"star-prune-{snapshot['login']}-{_stamp()}.json"
    repos = [
        {
            "id": t["id"],
            "name": t["name"],
            "lists": [{"id": lists[i["name"]], "name": i["name"]} for i in member_of[t["name"]]],
        }
        for t in targets
    ]
    _write_json(backup, {"format": BACKUP_FORMAT, "account": snapshot["login"], "repos": repos})
    print(f"\nBacked up {_count(len(repos), 'star', 'stars')} and their lists to {backup}.")
    print(f"Undo with: sh scripts/run.sh restore {backup} --yes")
    for target in targets:
        github.remove_star(target["id"])
    still = {star["name"] for star in github.snapshot()["stars"]}.intersection(t["name"] for t in targets)
    if still:
        print(f"Unstarred, but these are still starred: {', '.join(sorted(still))}")
        return EXIT_FAILED
    print(f"Unstarred and verified: {_count(len(targets), 'repository', 'repositories')}.")
    return EXIT_OK


def cmd_restore(github: GitHub, args: argparse.Namespace) -> int:
    snapshot = github.snapshot()
    backup = _read(args.backup, BACKUP_FORMAT, snapshot["login"])
    live_lists = {item["id"] for item in snapshot["lists"]}
    starred = {star["name"] for star in snapshot["stars"]}
    repos = backup.get("repos", [])
    missing = [repo for repo in repos if repo["name"] not in starred]
    to_star = _count(len(missing), "repository", "repositories")
    print(f"{to_star} to re-star; {len(repos)} to put back into their lists.")
    for repo in repos:
        gone = [entry["name"] for entry in repo["lists"] if entry["id"] not in live_lists]
        if gone:
            print(f"  {repo['name']}: list no longer exists, skipped: {', '.join(gone)}")
    if not args.yes:
        print("\nNothing was written. Re-run with --yes to restore.")
        return EXIT_NEEDS_CONFIRMATION
    for repo in missing:
        github.add_star(repo["id"])
    for repo in repos:
        github.set_item_lists(
            repo["id"], [entry["id"] for entry in repo["lists"] if entry["id"] in live_lists]
        )
    after = github.snapshot()
    not_back = sorted({repo["name"] for repo in repos} - {star["name"] for star in after["stars"]})
    if not_back:
        print(f"Restored, but these are still not starred: {', '.join(not_back)}")
        return EXIT_FAILED
    restored = _count(len(repos), "repository", "repositories")
    print(f"Restored and verified: {restored} starred and back in their lists.")
    return EXIT_OK


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="star-prune", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="flag stars and propose an action for each")
    scan.add_argument("--out", help="file to write (default: star-prune-<login>-<timestamp>.json)")
    scan.add_argument("--dormant-years", type=float, default=rules.DEFAULT_DORMANT_YEARS)
    scan.add_argument("--old-star-years", type=float, default=rules.DEFAULT_OLD_STAR_YEARS)
    apply = commands.add_parser("apply", help="back up, unstar the candidates marked unstar, and verify")
    apply.add_argument("candidates")
    apply.add_argument("--yes", action="store_true", help="make the writes")
    apply.add_argument("--backup-dir", default="star-prune-backups")
    restore = commands.add_parser(
        "restore", help="re-star a backup and put each repository back in its lists"
    )
    restore.add_argument("backup")
    restore.add_argument("--yes", action="store_true", help="make the writes")
    return parser.parse_args(argv)


COMMANDS = {"scan": cmd_scan, "apply": cmd_apply, "restore": cmd_restore}


def main(argv: list[str] | None = None, github: GitHub | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return COMMANDS[args.command](github or GitHub(), args)
    except (PruneError, GitHubError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
