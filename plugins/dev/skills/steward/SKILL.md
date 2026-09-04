---
name: steward
description: Sweep every repository your agent sessions have touched, found from the agent's own session records and any roots you name, and run the dev loop's housekeeping across all of them at once — fast-forward each base branch, remove what already merged, keep conversation titles in scheme, and report which branches are ready to merge, which pull requests are blocked, and which worktrees a live session still occupies. Built to run unattended on a schedule, so a question a pass would have stopped to ask lands in the report instead. Use when asked to 巡一遍所有项目, 大内总管, 看看哪些分支该合并了, 定时清理本地环境, 扫一下所有 worktree, sweep all my repos, check on every project, what needs merging across my projects, run the housekeeping, keep my local environment clean. Not for syncing or cleaning the one repository you are standing in, for shipping or merging a branch, or for renaming a single conversation.
license: MIT
context: fork
metadata:
  version: "0.14.0"
argument-hint: "[--roots=<dir,…>] [--since=<days>] [--only=<sync|cleanup|retitle|report>] [--dry-run] [--unattended]"
---

# Steward

Sweep every repository a session has been working in, run the loop's housekeeping in each, and hand back one report of what is waiting on a person.

Read [shared/git.md](shared/git.md) first — base resolution, the force-push rule, what "merged" means after a rebase, and § The home worktree.

This skill owns three things the skills it delegates to cannot see: **which repositories exist** (each of them works in one), **which worktrees a session still occupies** (git cannot tell), and **the report across all of them**. Everything else it hands off:

| Pass | Delegated to | What the steward adds |
|---|---|---|
| fast-forward the base | `/dev:sync` | runs it in every repository |
| merged branches, worktrees, residue | `/dev:cleanup` | the occupancy list — worktrees it must keep |
| conversation titles | `/dev:retitle` | unattended runs propose and never write |
| landing a branch | nobody | reported as ready, with the command; `/dev:ship` is the person's to run |

It never merges, rebases, resolves a conflict, deletes anything cleanup would keep, or renames a title without the two-column table.

## It runs forked

`context: fork` in the frontmatter, because a sweep is a long private session whose transcript the caller never needs. Fifteen repositories produce fifteen fetches, a branch ledger per repository, and every sub-skill's own output; measured on one machine, one sweep covered 15 repositories, 121 worktrees and 44 open pull requests, and none of that intermediate traffic is what the person asked for. Forked, it lands in the fork and the caller gets the report.

Two consequences the rest of this skill is written around:

- **The report is not a summary of evidence printed above it.** It is the only thing that comes back, so every claim it makes has to be checkable from the report itself or from a file it names.
- **A question asked inside the fork reaches nobody.** Attended runs relay through the report the same way unattended ones do; the difference between the two modes is what the passes are allowed to *do*, not who they can interrupt.

## 0. Mode

Decide before anything runs, and say which in the report's first line.

- **Attended** — a person is at the keyboard. Sub-skills keep their own stop-and-ask behaviour, and the steward relays each question as it comes, one repository at a time.
- **Unattended** — `--unattended`, or the prompt arrived from a scheduler rather than a person: a scheduled-task run, a cron-fired session, a `claude -p` invocation. Nobody can answer, so **no pass may block on a question**. Every question a sub-skill would have asked is written into the report under *Needs you*, and the pass moves on. Retitle proposes and does not write. Cleanup removes only what its own rules remove without asking.

`--dry-run` is stricter than either: inventory and report only. No fetch, no fast-forward, no deletion, no rename — and the report says its branch states are as of the last fetch, whenever that was.

`--only=<pass>` runs one pass. `report` runs the inventory and the branch ledger with no writes at all, which is `--dry-run` under another name.

Identify this run's home worktree before it moves anywhere, per `shared/git.md` § The home worktree. It is kept whatever any pass below concludes about its branch.

## 1. Inventory

Which repositories are active is not a git question. A repository is active because a session was open in it, so the list comes from where sessions leave traces. `scripts/inventory.py` reads them and writes nothing:

```bash
python3 scripts/inventory.py --since 14 --roots <dir,…>
```

| Source | What it yields | Where |
|---|---|---|
| Claude Code transcripts | every session's working directory and when it was last written to | `projects/*/*.jsonl` under the config directory |
| Claude Code live sessions | sessions with a process attached right now | `claude agents --json`, when the CLI is on `PATH`; `--no-live` skips it |
| Codex thread catalogue | each thread's working directory and last update | `sqlite/codex*.db` under the Codex home, opened read-only |
| `--roots` | every child directory holding a `.git` | named by you — repositories nobody opened a session in |

Each trace resolves to its worktree, each worktree to the primary checkout it belongs to, and the primary's own `git worktree list` fills in the worktrees no session touched. The JSON carries, per repository, every worktree with its branch, dirty-file count, sessions, last activity and an `occupied` flag, and a `skipped` block:

- `temporary` — under the system temp directory. Scratch checkouts and agent sandboxes, not yours to sweep.
- `missing` — a working directory that no longer exists. The session outlived its checkout; reported, never an error.
- `not_git` — a session that ran somewhere that is not a repository.
- `unresolved` — a transcript with no working directory in its first lines.

Print the inventory before any pass runs. It is the scope of everything after it:

> **Inventory — <N> repositories, <M> worktrees, <K> sessions in the last <since> days**
>
> | Repository | Worktree | Branch | Sessions | Last activity | Dirty | Occupied |
> |---|---|---|---|---|---|---|
> | `<primary>` | `.` | `main` | 3 | 2h ago | clean | — |
> | | `.claude/worktrees/foo` | `feat/foo` | 1 · live | 10m ago | 2 files | **yes** |

A markdown table, for the reason cleanup gives: paths and branch names run long, and a table wraps inside its cell where a fixed-width block throws every column under the long row out of line. Print worktree paths relative to their primary, and the primary once.

### Occupied means hands off

A worktree is occupied when a session has a process attached to it right now, or when any session wrote to it within `--occupied-hours` (default 24). **An occupied worktree is never removed, and its branch is never deleted, by anything this run does** — merged or not, clean or not. A session resumed into a directory that is gone breaks every command that follows, and cleanup cannot see the session from git; this list is how it finds out. Pass it to cleanup as keeps, and list each one under *Kept* with the session that holds it.

`shared/git.md` § The home worktree is the one case of this a running session can settle with certainty rather than infer — its own. Occupancy is the general rule, and the home worktree is its one instance that needs no evidence.

The default window is a day rather than an hour because a transcript stops moving the moment its person walks away, and they come back after lunch.

## 2. Each repository, most recently active first

Run every command in a subshell rooted at the primary checkout, never by changing this session's own directory:

```bash
( cd <primary> && git fetch --prune && … )
```

`gh` reads the repository from the directory it runs in, which is why a subshell rather than `git -C`. One repository failing — a remote that is down, a token that expired, `gh` not authenticated for that host — is reported for that repository and the sweep continues. A sweep that stops at the third of twelve repositories has told the person about two.

### 2a. Sync

Run `/dev:sync` as written: fetch, prune, fast-forward the base without touching a feature branch or a dirty tree. Keep its `attention` lines — they go into *Needs you* verbatim.

### 2b. The branch ledger

This is the pass the person asked for: which branches are waiting, and on whom. For every local branch that is not the base:

```bash
gh pr list --head <branch> --state all --json number,state,isDraft,mergeable,reviewDecision,statusCheckRollup,url
git rev-list --left-right --count origin/<base>...<branch>    # behind, then ahead
git log -1 --format=%cr <branch>
```

Classify by the first row that matches:

| Finding | Report as | Under |
|---|---|---|
| open PR, checks passing, `mergeable` is `MERGEABLE`, not a draft, no review blocking | **ready to merge** — `/dev:ship` from its worktree, or `gh pr merge <n>` | Merge |
| open PR, a check failing | blocked: CI — name the check | Merge |
| open PR, `mergeable` is `CONFLICTING` | blocked: conflicts with `<base>` — rebase or merge, the person's call | Merge |
| open PR, `reviewDecision` is `REVIEW_REQUIRED` or `CHANGES_REQUESTED` | waiting on review | Merge |
| open PR, draft | draft — still being written | Merge |
| no PR, ahead of the base | unshipped: N commits, last touched <when> | Needs you |
| no PR, ahead, last commit older than `--stale` (default 30 days) | stale — not deleted; ship it, or say it is abandoned | Needs you |
| PR merged | cleanup's business — step 2c | — |
| PR closed without merging, branch still local | closed unmerged — kept, reported | Kept |

`mergeable` reads `UNKNOWN` while GitHub is still computing it, which is its state for a minute after any push. Re-read once after a few seconds; if it is still unknown, report it as unknown. Unknown is not ready.

A ready branch is reported with the command, never run. Whether a green pull request should land today is the author's decision — a review they were waiting for, a deploy window, a change they meant to fold in — and a sweep that merges on green has taken a decision it cannot see.

### 2c. Cleanup

Run `/dev:cleanup` as written, with two additions:

1. Every occupied worktree from step 1, and every branch checked out in one, is a keep. Say so in cleanup's kept table, with the session.
2. Unattended, every place cleanup would "list it and ask" — a worktree outside the repository's own directory, a merged branch checked out in the primary, a large ignored directory — is written to *Needs you* and left alone.

The home worktree rule still applies to this run's own worktree, in whichever repository it belongs to.

## 3. Sessions and titles

Two things, and the second is the one that needs a person.

**The session scan** comes from step 1's JSON and costs nothing more: per repository, how many sessions in the window, which worktrees they stand in, and which worktrees have *no* session inside the window — those are the ones cleanup can take once their branch merges, and the ones to name when a worktree count is climbing.

**Titles** are `/dev:retitle`'s. Attended, run it as written: the two-column proposal table, confirmation, then the write. Unattended, run it up to the table and stop — it shows the table before writing for a reason, and a scheduler is not a confirmation. Put the table in the report, or the count and where the table was written when it runs long. The hook that keeps new sessions named needs no installation check. Installed as the `dev` plugin, `hooks/hooks.json` registers it on every `UserPromptSubmit`, and disabling the plugin unregisters it. What is worth reporting is the opposite case: a machine that installed it by hand before the plugin carried it now runs two copies, and the second one is a `UserPromptSubmit` entry in the agent's settings pointing at a copied script. Report that as a duplicate to remove; report nothing when the plugin is the only registrar.

Where the skill was copied on its own — `npx skills add`, skills.sh, any client that installs a skill directory rather than a plugin — no plugin exists to register it, and retitle's `references/hook-install.md` is the manual route.

## 4. The report

One report, in the language the person writes in, after every repository has run. Because the run is forked, it does not sit on top of evidence the caller can scroll to — it is the whole delivery, and a claim it makes that nothing in it supports is a claim nobody can check.

> **Steward sweep — <date> · <attended | unattended> · <N> repositories, <M> worktrees, <K> sessions in <since> days · previous sweep <when, or none>**
>
> | Repository | Base | Synced | Cleaned | Merge | Needs you |
> |---|---|---|---|---|---|
> | `<name>` | `main` | ff 3 · up to date · skipped: dirty | 2 branches, 1 worktree · nothing | 1 ready · 1 blocked | 2 |
>
> **Merge**
>
> | Repository | Branch | PR | State | Do |
> |---|---|---|---|---|
> | `<name>` | `feat/x` | #12 | ready — checks green, approved | `gh pr merge 12`, or `/dev:ship` in `<worktree>` |
> | `<name>` | `feat/y` | #13 | blocked — `test (3.13)` failing | fix, push, re-run |
>
> **Needs you** — every question a pass would have asked
>
> | Repository | Item | Question |
> |---|---|---|
> | `<name>` | `feat/z` | 4 commits, no PR, last commit 45 days ago — ship it or drop it? |
>
> **Kept**
>
> | Repository | Item | Why |
> |---|---|---|
> | `<name>` | `.claude/worktrees/foo` | occupied — session `<id>` is live |
>
> **Titles** proposed N · renamed N · deferred N (30-day window) · hook installed
> **Skipped** temporary N · vanished N · not a repository N · unresolved N

Rules the report is held to:

- Every count comes from a read-back — `git branch -vv`, `git worktree list`, retitle's read-back query — never from the number of commands issued.
- An empty section is printed as `none`. A missing section reads as a pass that did not run, and those are two different facts.
- No sub-skill `attention` line is dropped. Merging them into a sentence is how the one that mattered disappears.
- Save it, before returning it. Write the report to `${XDG_STATE_HOME:-$HOME/.local/state}/steward/last-sweep.md`, with the timestamp beside it in `last-sweep`. Forked, this file is the only copy that outlives the run: it lets the next sweep say when the last one ran, and it survives a missed notification and a caller who cleared the conversation. Overwrite it; the history is in git and on the forge, not here.
- Name the file in the report itself. A reader who wants the per-repository detail the fork swallowed has to be told where it went.

## 5. Running on a schedule

The steward does not schedule itself. When asked to — "every morning", "run this daily", 定时跑 — install the sweep with whatever the harness offers, and tell the person which one it was and how to remove it:

| Harness | How | Lives as long as |
|---|---|---|
| Claude Code desktop app | its scheduled-task tool, prompt `/dev:steward --unattended`, cron in local time | the app is installed; a run missed while it was closed fires at next launch |
| Claude Code CLI, this session | `/loop 4h /dev:steward --unattended`, or the session's cron tool | this session — recurring jobs there expire after seven days |
| Any machine scheduler — cron, launchd, a systemd timer | `claude -p "/dev:steward --unattended" > <report path>` from any directory | the machine |
| Codex | its scheduler where it has one; otherwise the machine row | — |

Four rules for the schedule itself:

- **Pick a minute that is not `:00` or `:30`.** Every scheduled job on the planet asks for nine sharp; `23 9 * * 1-5` lands the same and does not queue behind them.
- **Pick a time the person is around.** The report exists to be acted on; a sweep at 3 a.m. is read at 9 a.m. with the numbers six hours stale.
- **One sweep at a time.** A scheduler that fires while the previous run is still going produces two runs racing to delete the same branch. Take a lock directory under the state directory at the start, and skip with a one-line report when it is already held.
- **Nothing in the run may need a terminal.** `gh auth status` first; an expired token is a reported failure for that host, not a prompt nobody sees.

Never register a schedule the person did not ask for, and never a second one: read the harness's list before adding.

## Flags

- `--roots=<dir,…>` — directories whose child repositories join the inventory whether or not a session touched them.
- `--since=<days>` — the activity window that makes a repository active. Default 14.
- `--occupied-hours=<hours>` — how recent a session's activity must be for its worktree to count as occupied. Default 24.
- `--stale=<days>` — how old an unshipped branch's last commit must be before it is reported stale. Default 30.
- `--only=<sync|cleanup|retitle|report>` — one pass. `report` writes nothing.
- `--dry-run` — inventory and report from what is already fetched. Nothing is written anywhere.
- `--unattended` — no pass may ask; every question goes into the report. Implied when the prompt came from a scheduler.

## Reporting failures

A pass that cannot run in one repository — `gh` unauthenticated for that host, a remote unreachable, a git command that timed out — is one row under *Needs you* naming the repository, the command, and what it printed. It is not a reason to stop the sweep, and it is not reported as "synced" or "clean". The per-repository table carries `failed: <reason>` in that column, so a reader can tell a repository that was swept from one that was skipped.
