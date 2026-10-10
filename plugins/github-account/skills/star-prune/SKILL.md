---
name: star-prune
description: Find the starred GitHub repositories that are archived, disabled, deprecated or dormant, explain why each was flagged, and unstar the ones the user confirms, backing up every removed star and its lists so a restore can re-star them. Use when asked to clean up dead or stale GitHub stars, remove archived or deprecated repos from my stars, prune or declutter starred repositories, find stars that are no longer maintained, or undo a star cleanup. Not for sorting stars into lists or renaming lists, starring new repositories, deleting or archiving repositories you own, or GitHub notifications.
license: MIT
metadata:
  version: "0.20.0" # x-release-please-version
argument-hint: "[scan | apply | restore <backup.json>] [--dormant-years N]"
---

# Star Prune

Find the stars that no longer earn their place, show why, and unstar only what the user confirms.

The path never changes: `scan` writes a candidates file with a proposed action per repository, the user adjusts it, `apply --yes` backs up and unstars, and `restore` undoes it. Sorting the stars that remain is `star-lists`' job.

## Language

Everything this skill generates is English: the candidates file, backups, and anything written to disk. Talk to the user in their language. The candidates file carries reasons and evidence, not repository descriptions, so a non-English description never lands in a generated file.

## 1. Dependencies and sign-in

Run every command through `scripts/run.sh` from this skill's directory. It needs only a POSIX shell, `tar`, and `curl` or `wget`.

```bash
sh scripts/run.sh doctor
```

Act on every `missing` line:

- **Python or gh missing.** Ask before installing, then run `sh scripts/run.sh doctor --install`. It downloads gh and uv from their GitHub releases, verifies each SHA-256, and installs them into `~/.local/share/github-account/bin` (override with `GITHUB_ACCOUNT_TOOLS_DIR`) without `sudo`.
- **Not signed in.** Run `gh auth login --hostname github.com --web --scopes user,repo`; the user enters the one-time code in their browser. Never ask for a password or token in chat.
- **Scope missing.** `apply` and `restore` need `repo` (or `public_repo`) to star and unstar, and `user` so a restore can put repositories back into their lists. Run the `gh auth refresh` command the line prints.

## 2. Scan

```bash
sh scripts/run.sh scan --out prune.json
```

Each flagged repository gets reasons, strongest first:

| Reason | Meaning | Proposed action |
|---|---|---|
| `disabled` | GitHub disabled the repository | `unstar` |
| `archived` | the owner archived it; it is read-only | `unstar` |
| `deprecated` | its description or topics say deprecated, unmaintained, no longer maintained, superseded by, or moved to; `evidence` quotes which | `unstar` |
| `dormant` | not archived, but no push in more than `--dormant-years` (default 2) | `keep` |
| `old-star` | starred more than `--old-star-years` (default 4) ago and in no list | `keep` |

Repositories the account owns are never flagged. A dormant repository is often finished rather than dead, which is why dormancy alone proposes `keep`.

## 3. Review with the user

Show the candidates grouped by first reason, with counts. List every `unstar` candidate by name with its reason and evidence; summarize `keep` candidates by count and offer the names. Then let the user change any `action` between `unstar` and `keep` in `prune.json`. Accept answers like "unstar the archived ones, keep the rest" and edit the file accordingly.

A user who wants a repository out of sight but not unstarred wants an Archive list: hand that to `star-lists` rather than unstarring.

## 4. Apply

```bash
sh scripts/run.sh apply prune.json          # prints what would be unstarred, writes nothing
sh scripts/run.sh apply prune.json --yes    # after the user says yes to that list
```

Run it without `--yes` first and show its list. A yes to an earlier list does not cover a changed file. With `--yes` it writes `star-prune-backups/star-prune-<login>-<timestamp>.json` holding each repository's id, name and lists, unstars them, reads the stars back, and exits non-zero if any are still starred. Report the backup path it printed.

## Restoring

```bash
sh scripts/run.sh restore star-prune-backups/<file>.json        # shows what it would do
sh scripts/run.sh restore star-prune-backups/<file>.json --yes
```

It re-stars every repository in the backup and puts each back into the lists it was in. A list deleted since then is reported and skipped.

Tell the user before a restore: GitHub cannot bring back the original star date, so restored stars sort as newly starred.

## Limits

- A renamed repository is not flagged; GitHub follows renames transparently, so only a description that says "moved to" reveals a move.
- The scan reads the live account each time, so a candidates file from an earlier scan still works; repositories already unstarred are skipped.
