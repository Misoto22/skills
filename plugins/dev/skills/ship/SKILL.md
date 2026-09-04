---
name: ship
description: Ship the current changes as a merged pull request — branch off, run the project's tests, commit, open the PR, wait for CI, merge, and clean up the worktree. Use when asked to ship it, land it, get this merged, open a PR and merge it, push this up and merge, 发出去, 合掉, 开个 PR 合了, 把这些改动提上去, 推上去合并. Not for tagging a release, publishing a package, deploying, or writing a commit message without pushing it.
license: MIT
metadata:
  version: "0.15.2"
argument-hint: "[branch-name] [--dry-run] [--no-test] [--draft] [--base=<branch>] [--bump=<version|major|minor|patch>] [--merge-strategy=<squash|merge|rebase>]"
---

Ship the current changes as a merged PR.

Read [shared/git.md](shared/git.md) first.

Step 0 inspects the repo and prints an **execution plan** that marks each downstream step as `RUN` or `SKIP`. Follow that plan exactly — do not run a `SKIP` step, do not invent new ones. If any step exhausts its retry budget, stop and ask the user.

## Step classification

| Step                | Runs when                                                            |
|---------------------|----------------------------------------------------------------------|
| 0. Preflight        | Always.                                                              |
| 1. Branch off base  | Current branch == base branch AND something is shippable — an uncommitted change, or a commit `origin/<base>` does not have. |
| 2. Test & lint      | A test or lint command is detected AND `--no-test` was not passed.   |
| 3. Commit           | `git status --porcelain` is non-empty. Its first sub-step moves the version, but only when 0h found a bumper AND `--bump` was passed. |
| 4. PR               | The branch carries at least one commit the base does not, or an open PR already exists. |
| 5. CI               | The PR reports at least one check, or the repository declares a workflow that would. |
| 6. Merge            | Always (unless `--draft` — stop after step 4).                       |
| 7. Worktree cleanup | A `git worktree` holds the branch just shipped. It is removed only when this run is not standing in it. |

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
git rev-parse --show-toplevel   # where this run stands — step 7 needs it before any cd
```

Record that path. It is the only chance to: `git rev-parse --show-toplevel` answers for the primary checkout the moment you leave a worktree, and step 7 decides what it may remove by comparing against it.

### 0c. Base branch resolution

Per [shared/git.md](shared/git.md), which also carries the force-push rule and what "merged" means after a rebase. Read it before step 6.

With the base resolved, ask whether it carries work of its own:

```bash
git rev-list --count origin/<base>..<base>
```

**Early exit.** On the base branch, with a clean tree, no open pull request, and that count at zero, there is nothing to ship: report, stop, and run no step 1–7. Non-zero is the case that looks identical and is not — someone committed to the base by hand, and those commits are exactly what this skill exists to land. Step 1 branches off and carries them.

### 0d. Open PR for the current branch

Only meaningful when the current branch is not the base branch:

```bash
gh pr list --head "$(git branch --show-current)" --state open --json number,url,headRefName
```

### 0e. Test command detection

[references/detection.md](references/detection.md) § Test command. Record what matched.
Step 2a needs three answers told apart: a command that ran, a command that was found and
could not run here, and no command declared anywhere — including the project's CI.

### 0f. Lint command detection

[references/detection.md](references/detection.md) § Lint command. Nothing detected means
step 2b SKIPs; a linter the project does not configure is not this skill's to impose.

### 0g. CI presence

Step 5 reads this, so record it rather than glancing at it:

```bash
ls .github/workflows/ 2>/dev/null
grep -lE 'pull_request|push:' .github/workflows/*.y*ml 2>/dev/null
```

Either trigger reports on the pull request — a `push` workflow fires when step 4 pushes the branch. What matters is whether this repository has a workflow that *will* produce a check, because step 5 has to tell "no CI here" apart from "CI has not registered yet".

### 0h. Version bump detection

[references/detection.md](references/detection.md) § Version bumper. Record the bumper and
whether `--bump` was passed.

**Finding a bumper is not a reason to run it.** Whether a change is a release is a
judgment, and the number is not derivable from a diff — a bug fix and a breaking change
produce the same `git status`. So `--bump` RUNs step 3a; without it step 3a SKIPs **and
the run reports that under `Attention`**. A silent skip is how a version sits still
through twenty-five merges while every install stays pinned to the first one.

### 0i. Print the execution plan

Before any write:

```
Ship plan for <branch> → <base>:
  [done]       0. Preflight
  [<RUN|SKIP>] 1. Branch off <base>     <reason>
  [<RUN|SKIP>] 2. Test & lint           <reason — e.g. "detected: cargo test, cargo clippy" / "--no-test passed">
  [<RUN|SKIP>] 3. Commit                <reason — e.g. "5 files modified; --bump=minor → 0.15.2" / "5 files modified; bumper found, no --bump" / "working tree clean">
  [<RUN|SKIP>] 4. PR                    <reason — "create new" or "reuse #42">
  [<RUN|SKIP>] 5. CI                    <reason — "2 workflows declared" / "no workflow declares a check">
  [<RUN|SKIP>] 6. Merge                 <reason — "squash-merge" or "--draft: stop after step 4">
  [<RUN|SKIP>] 7. Worktree cleanup      <reason — "worktree <path> holds this branch" / "this run stands in it — kept">
```

After printing: stop if `--dry-run` was passed, otherwise proceed immediately. Without that flag the plan is a transparency tool, not a gate.

---

## 1. Branch off base

Only when on the base branch **and** there is something to ship — an uncommitted change, a commit `origin/<base>` does not have, or both.

- If the user passed a positional `[branch-name]`, use it.
- Otherwise name it per [shared/git.md](shared/git.md) § Branch names, taking the subject from the commit drafted in step 3.
- `git checkout -b <name>`.

If already on a feature branch → SKIP.

### 1a. When the base carried commits of its own

Only when step 0c counted commits on `<base>` that `origin/<base>` does not have. The branch just created was cut from that same HEAD, so it already holds every one of them — which is what makes the next line safe:

```bash
git branch -f <base> origin/<base>
```

Nothing can be lost. The commits the base ref is moving away from are the commits the new branch points at, this second, by construction; `git reflog` holds the old position besides. Leaving it undone is what costs: after the pull request lands, the local base holds those commits *and* the squashed or rebased copy of them that came back through the merge, so step 7 finds a base that will not fast-forward and stops.

Say in the report that the base was reset, and to which commit. This is the one ref this skill rewrites without being asked, and a run that does it silently is indistinguishable from one that lost three commits.

## 2. Test & lint

### 2a. Tests

Run the detected command. On failure: max 2 fix attempts; then stop and ask. Never fabricate a test run if no command was detected.

A suite that was already red is a different report from one this change broke, and "unrelated" is a claim, not a guess. Before attributing a failure elsewhere, get a baseline — cheapest first:

- The failing test's file is not in the diff, and neither is the module it exercises → say that, and say the baseline was inferred from the diff rather than measured.
- Measure it, when the suite runs without an install step. A throwaway checkout touches nothing in the working tree:
  ```bash
  git worktree add --detach <tmp> origin/<base>
  # run the test command in <tmp>
  git worktree remove <tmp>
  ```
  Where a fresh checkout would need its dependencies installed again, `git stash push --include-untracked`, run, then `git stash pop`.
- Neither is practical → report the baseline as unknown. That is honest; "unrelated to this change" without a baseline is not.

One baseline run for the whole suite, not one per failing test.

### 2b. Lint

Run what 0f detected, before step 3 stages anything — a formatter's output belongs in the commit, not in a follow-up.

- Formatting differences: apply them, and include them in the same commit.
- Rule violations inside the change: fix them, same budget as 2a — two attempts, then stop and ask.
- Violations in code this change never touched: report them and leave them. A ship is not a cleanup, and a diff that fixes the repository's backlog is a diff nobody can review.

`--no-test` skips 2b as well as 2a.

## 3. Commit

### 3a. Version bump

Runs only when 0h found a bumper **and** `--bump` was passed. It comes before the secrets
gate so the rewritten files are gated and staged into the same commit as the change — a
bump landing in a second commit, or a second PR, is how a branch ends up with a version
that describes neither the tree before it nor the tree after.

1. Resolve the version. `major` / `minor` / `patch` are relative to what the manifest
   declares right now, so read it first; an explicit version is used as passed. Never
   invent one.
2. Run the project's bumper. **Never edit version strings by hand** — a repository that
   ships a bumper declares its version in more places than a grep will show you, and
   keeping those in step is the whole reason the tool exists.
3. Check its report against `git status`, and close a changelog's `## Unreleased` section
   under the new version if the bumper did not already do it.

A bumper that exits non-zero stops the run. Do not hand-edit what it refused to write.

### 3b. Secrets gate — before staging anything

This is the last step before the change becomes public, and a secret pushed to a
remote is compromised even after a force-push removes it. Run over the change about
to be staged, not over the whole repository — and over its **content**, because a
file name is not where a credential is visible:

```bash
git diff --name-only HEAD                   # tracked, staged and unstaged together
git ls-files --others --exclude-standard    # untracked candidates — no diff exists for these
git diff -U0 HEAD                           # the added lines themselves
grep -nIE '<pattern>' <each untracked file> # untracked content, since git diff cannot show it
```

Both halves are needed. `git diff` never mentions an untracked file, and step 3c
stages untracked files by name — so a brand-new `config.local.json` holding a live
token reaches the commit having been read by nothing. Ignored files are excluded on
purpose: they cannot be committed without `git add -f`, which step 3c never uses.

Stop and ask — never stage — when a path or a diff line matches:

- a file named `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `id_rsa*`, `credentials*`, `*.keychain`
- a line adding a value that looks like a live credential: `sk-`, `ghp_`, `github_pat_`, `AKIA`, `xox[baprs]-`, `-----BEGIN .* PRIVATE KEY-----`, or a `password`/`secret`/`token` assignment whose value is neither empty, a placeholder, nor an environment lookup

A match is not automatically a leak — fixtures and documentation legitimately
contain shaped examples. Show the file, the line, and ask. Do not decide alone.

### 3c. Staging

- **Stage explicit paths only — never `git add -A`.**
- Classify each untracked file:
  - **Include** — clearly part of the change (new source / config matching the diff's topic).
  - **Skip** — runtime artefact (`*.log`, `.DS_Store`, `*-cache.json`, session/telemetry dirs). If a class of these recurs, add a `.gitignore` entry in the same commit.
  - **Ask the user** — collect every ambiguous file into one prompt and ask `include / skip` per item in a single round-trip. Never ask file-by-file.
- Conventional commit subject (`feat:` / `fix:` / `chore:` / `docs:` / `refactor:` / `test:` / `style:` / `perf:` / `build:` / `ci:` / `revert:`), ≤72 chars.
- Trailer: `Co-Authored-By: Claude <noreply@anthropic.com>`. **Do not hard-code a model version** — the trailer must stay model-agnostic.
- Commit directly; no user approval needed.

### 3d. When the commit is rejected

A pre-commit hook that refuses is the project talking. Read what it printed, fix what it names, commit again — two attempts, then stop and ask.

Never `--no-verify`. A hook bypassed here runs again in CI a minute later, on a pull request that is already public, and the only thing the bypass bought was a longer path to the same failure. If the hook itself is broken, say so and stop; that is a repository problem, not a shipping decision.

## 4. PR

**Reuse path** — preflight found an open PR on this branch:

1. Confirm the remote branch still exists: `git ls-remote --exit-code origin <branch>`. If it's gone (PR was closed-and-deleted out from under us), stop and ask.
2. `git fetch origin <branch>`. If the remote has commits we don't (force-push by someone else), stop and ask.
3. `git push` any new local commits.
4. Skip to step 5.

**Create path** — first, confirm there is anything to open one for:

```bash
git rev-list --count <base>..HEAD
```

Zero commits and no open pull request is not an error, it is an early exit: the run's
only changes were files step 3 classified as skip. Report it, push nothing, and if
step 1 created the branch a moment ago, offer `git checkout <base> && git branch -d <name>`
rather than leaving an empty branch behind. `gh pr create` against zero commits fails
anyway; reaching it means the plan printed in step 0 was wrong about what would be committed.

1. `git push -u origin <branch>`. If push is rejected (branch protection, signed-commits requirement, etc.), stop and surface the rejection — do not retry blindly.
2. `gh pr create --base <base>` (the resolved base from step 0c).
   - **Title** — from the commit subject.
   - **Body** — short summary of what & why, plus a `## Test plan` checklist.
   - The "Warning: N uncommitted changes" message from `gh` is expected when runtime files were intentionally left unstaged in step 3 — log it, ignore it.
3. If `--draft` was passed: add `--draft`, **stop here**, report the URL.

## 5. CI

"No checks reported" has two meanings and they are minutes apart in consequence. A pull
request opened seconds ago reports none because GitHub has not registered the workflow
run yet, and `mergeStateStatus` is `CLEAN` in that window exactly as it is in a repository
with no CI at all. Merging on that reading ships without the checks the project wrote.

Step 0g already settled which one this is:

- **A workflow declares a trigger** → re-poll `gh pr checks` every 10s for up to 60s before
  concluding there are none. If nothing registers in that window, proceed, and say so in
  the report: `CI skipped — <N> workflows declared, no check registered within 60s`. That
  line is the difference between a check that was green and a check that never ran.
- **No workflow declares one** → skip step 5 immediately.

Once at least one check exists, poll `gh pr checks` every 30s, timeout 10 min.

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

`--merge-strategy` wins if passed — but check it against what the repository allows before
merging, not after. `squash`, `merge`, and `rebase` map to `--squash`, `--merge`, and
`--rebase`; each is refused by `gh pr merge` when the corresponding repository setting is
off. On a mismatch, stop and name the strategies the repository does allow. Never
substitute one silently: `--merge` where the author asked for `--rebase` writes a history
they explicitly did not want.

Without the flag, choose rather than defaulting:

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

Only about the worktree holding the branch just shipped. Another tool's worktree, or one
for an unrelated branch, is not this run's business — the cleanup skill owns those.

### 7a. The home worktree

Per [shared/git.md](shared/git.md) § The home worktree, this run never removes the one it
is standing in. Identify it by comparing the toplevel recorded in step 0b against
`git worktree list`, which has to be that recorded value: after a `cd` to the primary
checkout, `git rev-parse --show-toplevel` no longer answers the question.

Report it and move on to 7c:

```
Worktree kept: <path> — this session is running in it.
Remove it from the primary checkout once the session ends, or run the cleanup skill there.
```

### 7b. A worktree for the shipped branch that this run is not in

1. Confirm it is clean: `git -C <path> status --porcelain`. Anything at all, untracked included, means stop and ask.
2. From the primary repo, never from inside it: `git worktree remove <path>` (retry with `--force` on "Directory not empty" only when step 1 found it clean; if residue remains, `rm -rf <path>`).
3. `git worktree prune`.
4. Delete the local branch only if it still exists: `git branch -D <merged-branch> 2>/dev/null` is fine — `--delete-branch` in step 6 plus `git fetch --prune` may have already removed it.

### 7c. Bring the primary checkout's base up to date

Advance the ref without commandeering someone's checkout — the primary may hold work in progress, and a `git checkout` in it is a change nobody asked for:

```bash
git -C <primary> fetch origin <base>:<base>
```

That advances the local base directly, refuses anything that is not a fast-forward, and touches no file. It is refused when `<base>` is the branch checked out there; in that case, and only when that tree is clean, `git -C <primary> pull --ff-only`. If the base has diverged, or the tree is dirty, report it and stop — do not force, do not stash someone else's work.

### 7d. Report

Remaining worktrees, and where `<base>` now points in the primary checkout.

---

## Flags

Each names the step that owns it. The rule lives in that step.

- `--dry-run` — print the execution plan and stop. Nothing is written, pushed, or merged.
- `--no-test` — skip all of step 2, tests and lint alike.
- `--draft` — open the PR as a draft and stop after step 4.
- `--base=<branch>` — override the base step 0c would resolve.
- `--merge-strategy=squash|merge|rebase` — force one of step 6's three, subject to what the repository allows.
- `--bump=<version|major|minor|patch>` — run the bumper 0h detected, in step 3a.
- `[branch-name]` (positional) — branch name when step 1 triggers.

## Reporting

**Normal run** — print one block:

```
Shipped:       <PR URL>
Merged commit: <sha on base>
Branch:        <feature-branch> → <base>
Steps run:     <comma-separated step numbers>
Steps skipped: <step number — reason; …>
Attention:     <base reset to <sha>; CI never registered; worktree kept — …; version not bumped — <bumper> found, no --bump passed; or none>
```

`Attention` carries what the run did that nobody asked for, and what it decided not to do:
the base ref moved in step 1a, a CI window that expired without a check, a worktree kept
because this session is standing in it, a version bumper found and not run. Empty is a
valid value; a silent one is not.

**Early exit (nothing to ship)**:

```
Nothing to ship.
Branch: <branch> (== <base>), tree clean, no open PR, nothing unpushed on <base>.
```

**Draft stop (`--draft`)**:

```
Draft PR opened: <PR URL>
Branch:          <feature-branch> → <base>
Steps run:       0, 1?, 2?, 3?, 4
```
