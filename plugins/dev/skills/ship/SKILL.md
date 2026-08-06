---
name: ship
description: Ship the current changes as a merged pull request — branch off, run the project's tests, commit, open the PR, wait for CI, merge, and clean up the worktree. Runs a preflight first that marks each step RUN or SKIP, so a clean tree on the base branch exits without doing anything. Use when asked to ship it, ship this, land it, get this merged, open a PR and merge it, push this up and merge, 发出去, 合掉, 开个 PR 合了, 把这些改动提上去, 推上去合并. Not for tagging a release, publishing a package, deploying, or writing a commit message without pushing it.
license: MIT
metadata:
  version: "0.6.0"
argument-hint: "[branch-name] [--dry-run] [--no-test] [--draft] [--base=<branch>] [--merge-strategy=<squash|merge|rebase>]"
---

Ship the current changes as a merged PR.

Read [shared/git.md](shared/git.md) first.

Step 0 inspects the repo and prints an **execution plan** that marks each downstream step as `RUN` or `SKIP`. Follow that plan exactly — do not run a `SKIP` step, do not invent new ones. If any step exhausts its retry budget, stop and ask the user.

## Common paths

- **On base branch with changes** → branch off → (test) → commit → PR → CI → merge → (worktree cleanup).
- **On feature branch with open PR** → (test) → (commit) → push → CI → merge.
- **Clean tree, on base, no open PR** → early-exit at step 0; nothing to ship.

---

## Step classification

| Step                | Runs when                                                            |
|---------------------|----------------------------------------------------------------------|
| 0. Preflight        | Always.                                                              |
| 1. Branch off base  | Current branch == base branch AND there are changes to ship.         |
| 2. Test             | A test command is detected AND `--no-test` was not passed.           |
| 3. Commit           | `git status --porcelain` is non-empty.                               |
| 4. PR               | Always — create new or reuse existing open PR.                       |
| 5. CI               | The PR reports at least one check.                                   |
| 6. Merge            | Always (unless `--draft` — stop after step 4).                       |
| 7. Worktree cleanup | Work was done in a `git worktree`.                                   |

> **Early exit overrides everything.** If preflight finds a clean tree AND no open PR for the current branch AND we're on the base branch → there is nothing to ship; report and stop. Steps 1–7 do not run.

---

## 0. Preflight

### 0a. Environment prerequisites (fail fast)

Any failure here stops the run with a clear message — do not proceed.

```bash
command -v gh         # gh CLI installed?
gh auth status        # gh authenticated?
git remote -v         # at least one remote configured?
```

### 0b. Repo state

```bash
git status --porcelain
git branch --show-current
git worktree list
```

### 0c. Base branch resolution

Per [shared/git.md](shared/git.md), which also carries the force-push rule and what "merged" means after a rebase. Read it before step 6.

### 0d. Open PR for the current branch

Only meaningful when the current branch is not the base branch:

```bash
gh pr list --head "$(git branch --show-current)" --state open --json number,url,headRefName
```

### 0e. Test command detection — first match wins

| Marker                               | Command                                                                 |
|--------------------------------------|-------------------------------------------------------------------------|
| `scripts/test`, `justfile`, `Makefile` target `test` | run that target                                          |
| `package.json` `scripts.test`        | `<pm> test` — pm via lockfile (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock` → bun, else npm) |
| `Cargo.toml`                         | `cargo test`                                                            |
| `pyproject.toml`                     | `uv run pytest` if `uv.lock`; else `pytest`; else `python -m unittest`  |
| `go.mod`                             | `go test ./...`                                                         |
| `*.csproj` / `*.sln`                 | `dotnet test`                                                           |
| `Gemfile`                            | `bundle exec rake test` if `Rakefile`, else `rspec`                     |
| none of the above                    | no test command → SKIP step 2                                           |

### 0f. CI presence (informational)

```bash
ls .github/workflows/ 2>/dev/null
```

### 0g. Print the execution plan

Before any write:

```
Ship plan for <branch> → <base>:
  [done]       0. Preflight
  [<RUN|SKIP>] 1. Branch off <base>     <reason>
  [<RUN|SKIP>] 2. Test                  <reason — e.g. "detected: cargo test" / "--no-test passed">
  [<RUN|SKIP>] 3. Commit                <reason — e.g. "5 files modified" / "working tree clean">
  [<RUN|SKIP>] 4. PR                    <reason — "create new" or "reuse #42">
  [<RUN|SKIP>] 5. CI                    <decided after PR opens>
  [<RUN|SKIP>] 6. Merge                 <reason — "squash-merge" or "--draft: stop after step 4">
  [<RUN|SKIP>] 7. Worktree cleanup      <reason>
```

After printing: stop if `--dry-run` was passed, otherwise proceed immediately. Without that flag the plan is a transparency tool, not a gate.

---

## 1. Branch off base

Only when on the base branch **and** there are changes.

- If the user passed a positional `[branch-name]`, use it.
- Otherwise derive `{type}/{slug}`:
  - **type** — pick by this order:
    1. `docs` if every changed file is `*.md` or text.
    2. `chore` if every changed file is config / deps / lockfile (`*.json`, `*.yml`, `*.toml`, lockfiles).
    3. `fix` if the commit subject (drafted in step 3) starts with "fix"/"bug"/"resolve".
    4. else `feat`.
  - **slug** — 3–5 words, kebab-case. Build from:
    1. The commit subject's content words (drop conjunctions, articles, the leading verb), OR
    2. The longest common directory prefix of the changed files.
    3. If both are unhelpful, fall back to `chore/sync-<dominant-dir-name>`.
  - Avoid reading large diffs to invent a slug — the commit subject is enough.
- `git checkout -b <name>`.

If already on a feature branch → SKIP.

## 2. Test

Run the detected command. On failure: max 2 fix attempts; then stop and ask. Never fabricate a test run if no command was detected.

## 3. Commit

### 3a. Secrets gate — before staging anything

This is the last step before the change becomes public, and a secret pushed to a
remote is compromised even after a force-push removes it. Run over the diff about
to be staged, not over the whole repository:

```bash
git diff --cached --name-only; git diff --name-only
```

Stop and ask — never stage — when a path or a diff line matches:

- a file named `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `id_rsa*`, `credentials*`, `*.keychain`
- a line adding a value that looks like a live credential: `sk-`, `ghp_`, `github_pat_`, `AKIA`, `xox[baprs]-`, `-----BEGIN .* PRIVATE KEY-----`, or a `password`/`secret`/`token` assignment whose value is neither empty, a placeholder, nor an environment lookup

A match is not automatically a leak — fixtures and documentation legitimately
contain shaped examples. Show the file, the line, and ask. Do not decide alone.

### 3b. Staging

- **Stage explicit paths only — never `git add -A`.**
- Classify each untracked file:
  - **Include** — clearly part of the change (new source / config matching the diff's topic).
  - **Skip** — runtime artefact (`*.log`, `.DS_Store`, `*-cache.json`, session/telemetry dirs). If a class of these recurs, add a `.gitignore` entry in the same commit.
  - **Ask the user** — collect every ambiguous file into one prompt and ask `include / skip` per item in a single round-trip. Never ask file-by-file.
- Conventional commit subject (`feat:` / `fix:` / `chore:` / `docs:` / `refactor:` / `test:` / `style:` / `perf:` / `build:` / `ci:` / `revert:`), ≤72 chars.
- Trailer: `Co-Authored-By: Claude <noreply@anthropic.com>`. **Do not hard-code a model version** — the trailer must stay model-agnostic.
- Commit directly; no user approval needed.

## 4. PR

**Reuse path** — preflight found an open PR on this branch:

1. Confirm the remote branch still exists: `git ls-remote --exit-code origin <branch>`. If it's gone (PR was closed-and-deleted out from under us), stop and ask.
2. `git fetch origin <branch>`. If the remote has commits we don't (force-push by someone else), stop and ask.
3. `git push` any new local commits.
4. Skip to step 5.

**Create path**:

1. `git push -u origin <branch>`. If push is rejected (branch protection, signed-commits requirement, etc.), stop and surface the rejection — do not retry blindly.
2. `gh pr create --base <base>` (the resolved base from step 0c).
   - **Title** — from the commit subject.
   - **Body** — short summary of what & why, plus a `## Test plan` checklist.
   - The "Warning: N uncommitted changes" message from `gh` is expected when runtime files were intentionally left unstaged in step 3 — log it, ignore it.
3. If `--draft` was passed: add `--draft`, **stop here**, report the URL.

## 5. CI

Skip immediately if `gh pr checks` reports "no checks reported" **and** `mergeStateStatus == CLEAN`.

Otherwise poll `gh pr checks` every 30s, timeout 10 min.

When checks settle, branch on `gh pr view --json mergeStateStatus`:

| State       | Action                                                                                            |
|-------------|---------------------------------------------------------------------------------------------------|
| `CLEAN`     | Proceed to merge.                                                                                 |
| `HAS_HOOKS` | Treat as `CLEAN` (post-merge hooks only).                                                         |
| `UNKNOWN`   | GitHub still computing. Sleep 5s and re-poll (max 3 times before treating as failure).            |
| `UNSTABLE`  | Non-required check failed. Stop and ask the user before merging.                                  |
| `BEHIND`    | Try `gh pr update-branch <PR>` (gh ≥2.30). Fallback: `git fetch origin <base> && git rebase origin/<base> && git push --force-with-lease`. Re-poll. |
| `BLOCKED`   | Required review / status check missing. Stop and ask the user.                                    |
| `DIRTY`     | Merge conflict with base. Stop and ask — do **not** auto-resolve.                                 |
| `DRAFT`     | PR is a draft — should not happen unless `--draft`. Stop.                                         |
| other       | Stop and surface the state verbatim.                                                              |

If a required check fails: `gh run view --log-failed`, fix, commit, push, re-poll. Max 2 fix attempts; then stop and ask.

## 6. Merge

`--merge-strategy` wins if passed. Otherwise choose, rather than defaulting:

```bash
gh repo view --json squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed
git rev-list --count <base>..HEAD
```

- One commit on the branch → `--squash` and `--rebase` are the same result; take whichever the repository allows, `--squash` first.
- More than one commit → `--rebase` if allowed. Squashing here discards a history the author deliberately split, and "one logical change per commit" is a common house rule. Fall back to `--squash` only when rebase is disallowed, and say so in the report.
- Always `--delete-branch`.

Never `--admin`. A merge that needs it is one a human should look at.
- **Verify** afterwards with `gh pr view <PR> --json state -q .state`:
  - `MERGED` → done.
  - Anything else → sleep 3s and re-check once (GitHub can be eventually consistent).
  - Still not `MERGED` → stop and surface the state.

## 7. Worktree cleanup

Only if `git worktree list` showed more than the primary repo.

1. Confirm the worktree is clean. If dirty, stop and ask.
2. `cd` back to the primary repo path.
3. `git worktree remove <path>` (retry with `--force` on "Directory not empty"; if residue remains, `rm -rf <path>`).
4. Delete the local branch only if it still exists: `git branch -D <merged-branch> 2>/dev/null` is fine — `--delete-branch` in step 6 plus `git fetch --prune` may have already removed it.
5. In the primary repo: `git fetch origin <base> && git checkout <base> && git pull --ff-only`. If `pull --ff-only` fails because the primary's base branch has diverged, stop and ask — do not force.
6. Report remaining worktrees and the new HEAD on `<base>`.

---

## Flags

- `--dry-run` — print the execution plan and stop. Nothing is written, pushed, or merged.
- `--no-test` — skip step 2 even if a test command was detected. Useful for docs-only / config-only ships.
- `--draft` — open the PR as a draft and stop after step 4.
- `--base=<branch>` — override base branch resolution. Without this flag, base is detected per step 0c.
- `--merge-strategy=squash|merge|rebase` — force one. Without it, step 6 picks from what the repository allows and how many commits the branch carries.
- `[branch-name]` (positional) — branch name when step 1 triggers.

## Reporting

**Normal run** — print one block:

```
Shipped:       <PR URL>
Merged commit: <sha on base>
Branch:        <feature-branch> → <base>
Steps run:     <comma-separated step numbers>
Steps skipped: <step number — reason; …>
```

**Early exit (nothing to ship)**:

```
Nothing to ship.
Branch: <branch> (== <base>), tree clean, no open PR.
```

**Draft stop (`--draft`)**:

```
Draft PR opened: <PR URL>
Branch:          <feature-branch> → <base>
Steps run:       0, 1?, 2?, 3?, 4
```
