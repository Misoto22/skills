---
name: sync
description: Bring the local repository in line with its remote — fetch, prune, fast-forward the base branch, and report what diverged. It never rebases a feature branch, never resolves a conflict, and never discards a local commit. Use when asked to sync, pull latest, update from main, get up to date, catch up with remote, 同步一下, 拉一下最新的, 更新到最新, 跟 main 对齐, 更新一下代码. Not for shipping changes, deleting merged branches, or resolving a merge conflict.
license: MIT
metadata:
  version: "0.8.3"
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

## 2. Report before writing

Print this before changing anything, from `git status --porcelain`, `git branch --show-current`, and `git worktree list`:

```
Sync <repo> → <base>
  working tree   <clean | N files modified, M untracked>
  current branch <branch>  <ahead N, behind M | up to date | no upstream>
  base <base>    <behind N | up to date>
  gone upstream  <branches whose remote was pruned, or none>
  worktrees      <N, or none>
```

## 3. Fast-forward the base branch

Only when it is behind and carries no local commits of its own.

- **Already on the base branch** — `git merge --ff-only origin/<base>`.
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

Fast-forward every local branch that tracks a remote and is strictly behind, skipping the checked-out one and anything that has diverged. Report each as fast-forwarded or skipped with its reason.

## Reporting

```
Synced <repo>.
  fetched        <N refs, M pruned>
  base <base>    <fast-forwarded A..B | already up to date | skipped: reason>
  branch <name>  <state from step 4>
  attention      <lines needing a decision, or none>
```

Everything under `attention` is something this skill deliberately refused to decide. State the options; do not pick one.
