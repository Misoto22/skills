---
name: star-lists
description: Organize a GitHub account's starred repositories into GitHub star Lists - design a clear set of lists, rename, create or delete lists, and put every starred repository into the right one or several, through a plan file that is validated, shown as a diff, backed up, applied and verified. Also files newly starred repositories into existing lists and restores a backup. Use when asked to organize, sort, clean up, categorize or tidy GitHub stars, star lists or the Lists dropdown, fix messy list names, put each starred repo in the right list, or file new stars. Not for starring or unstarring repositories, organizing repositories you own, GitHub Projects boards, or browser bookmarks.
license: MIT
metadata:
  version: "0.18.7" # x-release-please-version
argument-hint: "[organize | file new stars | review | restore <backup.json>]"
---

# Star Lists

Turn a GitHub account's starred repositories into a coherent set of star Lists, and keep them that way.

Every write goes through one path: export the account as a plan, edit the plan, `check`, `diff`, show the user, `apply --yes`. `apply` backs up the live state first and verifies the result afterwards. A backup is itself a plan, so restoring is applying it.

## Language

Everything this skill generates is English: list names, list descriptions, the plan file, the review page, and anything written to disk. This holds when the user writes in another language and when starred repositories have non-English descriptions. `check` rejects a plan whose list names or descriptions contain CJK text, so a slip fails before anything is written. Talk to the user in their language; generate artefacts in English.

## 1. Dependencies and sign-in

Run every command through `scripts/run.sh` from this skill's directory. It needs only a POSIX shell, `tar`, and `curl` or `wget`.

```bash
sh scripts/run.sh doctor
```

The report has one line per dependency: Python 3.9+, the GitHub CLI, the github.com sign-in, and the `user` token scope that writing lists requires. When anything is missing, read the line out and act on its fix:

- **Python or gh missing.** Ask before installing, then run `sh scripts/run.sh doctor --install`. It downloads gh and uv from their GitHub releases, verifies each archive's SHA-256 against the release checksums, and puts them in `~/.local/share/star-lists/bin` (override with `STAR_LISTS_TOOLS_DIR`). It never runs `sudo` and writes nowhere else; uv provides Python on first use. If neither `curl` nor `wget` exists, it prints the package-manager command for the machine; ask the user to run it.
- **Not signed in.** Run `gh auth login --hostname github.com --web --scopes user` from the tools directory or PATH. It prints a one-time code and a URL; the user enters the code in their browser. Never ask for a password or token in chat. `GH_TOKEN` in the environment also works.
- **Scope missing.** Run `gh auth refresh --hostname github.com --scopes user`, which goes through the same browser step.

Re-run `doctor` until it exits 0. Windows shells are refused; use WSL.

## 2. Export

```bash
sh scripts/run.sh export --out plan.json
```

`plan.json` holds the account's lists and every starred repository's current lists, plus each repository's description, language and topics under `repos`. The format is in [references/plan-format.md](references/plan-format.md). Read the whole file before proposing anything.

## 3. Design the lists

Build the taxonomy from what is actually starred, not from a generic template.

- **Aim for 8 to 25 lists.** GitHub allows at most 32 lists, 32 characters per name and 160 per description.
- **One naming pattern for every list.** For example `Area · Topic` (`AI · Agents`, `Study · Algorithms`), Title Case, no emoji. Sorting alphabetically should group related lists.
- **Keep the user's own structure where it holds.** Keep a list's `id` when its meaning survives, renaming it if the name is unclear or misspelled; only lists without an `id` get created. Delete a list (leave it out of the plan) only when it is empty, redundant, or the user agreed. Deleting a list never unstars anything.
- **Small is not wrong.** A list the user built around an interest stays, even with one repository, unless the user says otherwise.
- **Every starred repository gets at least one list.** Give a second list only for a real cross-cut, such as a CV template that belongs under both Career and Frontend. Never as a hedge.
- **Classify by what the repository is**, using its name, description, topics and language. When those say nothing (an empty description, a personal repository), put it in a catch-all list such as `Misc` rather than guessing.
- **Keys are stable identifiers.** Lowercase kebab-case, unique, used only inside the plan.

Write the new lists and assignments into the plan file. Keep `format` and `account` as exported.

## 4. Check, diff, confirm

```bash
sh scripts/run.sh check plan.json
sh scripts/run.sh diff plan.json
```

Fix every `check` error before continuing. Then show the user the diff summary: lists to create, update and delete, and how many repositories move. Include the full per-repository moves when there are fewer than about 40; otherwise show the list-level changes and offer the rest. The user can also review visually:

```bash
sh scripts/run.sh review plan.json   # writes plan.html next to the plan
```

The page lists every repository with every list as a toggle, so one repository can sit in several lists, and **Save edited plan** downloads `plan.reviewed.json`. Run `check` and `diff` on the saved file before applying it.

Wait for a clear yes to the diff. Approval of an earlier diff does not cover a changed plan.

## 5. Apply and verify

```bash
sh scripts/run.sh apply plan.json --yes
```

The command writes a backup to `star-lists-backups/star-lists-<login>-<timestamp>.json` and prints it. It then deletes lists, renames and updates lists (using temporary names when two lists swap names), creates lists, and moves repositories. Finally it reads the account back and compares it with the plan. Report what it printed, including the backup path. A non-zero exit after writing means the account and plan still differ: show the remaining diff and do not claim success.

GitHub throttles bursts of writes. The script backs off and retries when GitHub says so; a large reorganization can take a few minutes.

## Filing new stars

When asked to file stars added since the last organization, export, then assign only the repositories `check` reports as "starred but in no list", into existing lists. Change nothing else unless the user asks. Diff, confirm and apply as above.

## Restoring

Every backup is a complete plan:

```bash
sh scripts/run.sh diff star-lists-backups/<file>.json --allow-unassigned
sh scripts/run.sh apply star-lists-backups/<file>.json --yes --allow-unassigned
```

`--allow-unassigned` is there because the backup may predate repositories that were in no list at the time. A list deleted since the backup is recreated with a new id; GitHub cannot bring the old id back.

## Limits to tell the user

- GitHub exposes Lists only through GraphQL, and its stars documentation still calls Lists a preview. A GitHub change can break this skill; the error will name the failing call.
- Repositories starred or lists edited between `export` and `apply` are seen by `check`, which reads the live account each time. Re-export when it reports repositories the plan does not know.
