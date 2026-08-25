---
name: sync
description: Bring the local repository in line with its remote — fetch, prune, fast-forward the base branch, and report what diverged. It never rebases a feature branch, never resolves a conflict, and never discards a local commit. Use when asked to sync, pull latest, update from main, get up to date, catch up with remote, 同步一下, 拉一下最新的, 更新到最新, 跟 main 对齐, 更新一下代码. Not for shipping changes, deleting merged branches, or resolving a merge conflict.
license: MIT
metadata:
  version: "0.10.0"
argument-hint: "[--base=<branch>] [--all]"
---

# Sync

Bring the local repository in line with its remote, and say plainly what did not line up.

Read [shared/git.md](shared/git.md) first. Base resolution, force-push rules, and what "merged" means after a rebase all live there.

This skill only fast-forwards. Where a branch has diverged it reports and stops — choosing between rebase, merge, and reset is the user's call, and guessing it destroys work.

## 1. Fetch

```bash
git fetch --all --prune --tags
```

`--prune` deletes remote-tracking refs whose upstream is gone. It touches no local branch and no file.

It does not prune tags, and `--prune-tags` is deliberately not passed: that flag deletes every local tag the remote does not carry, including one made by hand five minutes ago, and a tag is sometimes the only thing keeping a commit reachable. A stale tag costs nothing. The alternative discards work, which is the one thing this skill never does.

`git fetch` writes what it did to **stderr**, not stdout — capture it. The `fetched` line in the final report counts those lines, and a run that discards the output has nothing left to count. Lines opening `- [deleted]` are the pruned refs; `* [new tag]` are the tags.

## 2. Report before writing

One command per line of the report. None of them writes:

```bash
git status --porcelain                          # working tree
git branch --show-current                       # current branch
git rev-list --left-right --count @{u}...HEAD   # behind, then ahead — in that order
git rev-list --count <base>..origin/<base>      # how far the base is behind
git branch -vv                                  # upstream gone — the lines ending ': gone]'
git worktree list                               # worktrees, and which one holds the base
```

`--left-right` prints the left side first, and the left side is `@{u}` — the remote. So the first number is **behind** and the second is **ahead**, the reverse of the order the report reads them out in. Getting it backwards turns unpushed work into a report saying there is none.

`@{u}` exits non-zero when the branch has no upstream. That is an answer, not a failure — report `no upstream` and carry on.

Print this before changing anything:

```
Sync <repo> → <base>
  working tree   <clean | N files modified, M untracked>
  current branch <branch>  <ahead N, behind M | up to date | no upstream>
  base <base>    <behind N | up to date>
  gone upstream  <branches whose remote was pruned, or none>
  worktrees      <N, or none>
```

Every line comes from a command above it. A field no command could fill is reported as unknown — never estimated, never quietly dropped.

## 3. Fast-forward the base branch

Only when it is behind and carries no local commits of its own.

- **Already on the base branch** — `git merge --ff-only origin/<base>`. This is the one path that writes to the working tree, so a dirty tree can refuse it: when the incoming commits touch a file you have modified, git stops with `Your local changes to the following files would be overwritten by merge`. It checks before it writes, so the refusal leaves the tree exactly as step 2 found it. Report the base as skipped, name the files that blocked it, and stop. Stashing on someone's behalf is how uncommitted work goes missing.
- **On a feature branch** — update the base without leaving it:
  ```bash
  git fetch origin <base>:<base>
  ```
  That advances the local ref directly, fails loudly if it would not be a fast-forward, and never touches the working tree, so uncommitted work is not at risk.
- **The base is checked out in another worktree** — the command above is refused. Name the worktree holding it and skip. That is not an error.

If the fast-forward fails, the local base has commits the remote does not. Report the count and stop. Do not reset, rebase, or merge.

## 4. Report the feature branch, do not touch it

For the current branch when it is not the base:

| State | Report |
|---|---|
| No upstream | `no upstream — push with -u to create one` |
| Ahead only | `ahead N — unpushed work` |
| Behind only | `behind N — rebase onto <base> when ready` |
| Diverged | `diverged: N ahead, M behind — rebase or merge, your call` |
| Upstream gone | `upstream gone — the pull request was probably merged and the branch deleted; /dev:cleanup removes it` |

Never rebase automatically. A rebase rewrites commits, and one run without being asked is indistinguishable from losing work.

## 5. With `--all`

Enumerate first. One command classifies every local branch:

```bash
git for-each-ref --format='%(refname:short) %(upstream:short) %(upstream:track)' refs/heads/
```

`%(upstream:track)` is the whole decision:

| Track | Meaning | Action |
|---|---|---|
| `[behind N]` | strictly behind | fast-forward |
| `[ahead N]`, `[ahead N, behind M]` | carries local commits | skip — step 4's rules apply |
| `[gone]` | upstream pruned | skip, report; `/dev:cleanup` decides its fate |
| empty, with an upstream | up to date | nothing to do |
| empty, with no upstream | never pushed | skip, report |

Fast-forward each candidate without checking it out:

```bash
git fetch origin <branch>:<branch>
```

Skip the checked-out branch and any branch held by another worktree — that ref is pinned by a working tree and the command is refused, which is the same rule step 3 already applies to the base. Report each branch as fast-forwarded or skipped with its reason.

## Reporting

```
Synced <repo>.
  fetched        <N refs, M pruned, T new tags>
  base <base>    <fast-forwarded A..B | already up to date | skipped: reason>
  branch <name>  <state from step 4>
  attention      <lines needing a decision, or none>
```

All three counts on the `fetched` line come from the stderr captured in step 1. If it was not captured, say so rather than printing a number nobody measured.

Everything under `attention` is something this skill deliberately refused to decide. State the options; do not pick one.
