---
name: cleanup
description: Remove what shipping left behind — local branches whose pull request merged, worktrees for those branches, and ignored residue a move stranded, such as a __pycache__ that git mv could not see. Every deletion is verified against the forge first, and anything unmerged or unexplained is reported rather than removed. Use when asked to clean up, tidy the repo, delete merged branches, remove stale branches, clear out old worktrees, 清理一下, 清掉合并过的分支, 删掉没用的分支, 收拾一下仓库. Not for discarding uncommitted work, resetting a branch, or removing untracked files you have not been shown.
license: MIT
metadata:
  version: "0.8.3"
argument-hint: "[--base=<branch>] [--branches] [--worktrees] [--residue] [--dry-run]"
---

# Cleanup

Remove what shipping left behind. Nothing else.

Read [shared/git.md](shared/git.md) first — in particular that a rebase or squash merge rewrites commits, so `git branch --merged` does not list a branch that landed. Every deletion here is verified against the forge, never against git alone.

**Default to `--dry-run` reasoning even without the flag: list everything, then delete.** With no scope flag, all three passes run. With any of `--branches`, `--worktrees`, `--residue`, only those.

## 0. Inventory, before deleting anything

```bash
git fetch --prune
git branch -vv
git worktree list
git status --porcelain
```

Print one table. Nothing is removed until it is printed:

```
Cleanup <repo> → <base>
  branch <name>       <merged #12 | unmerged: N commits | no PR> → <delete | keep: reason>
  worktree <path>     <clean, branch merged | dirty> → <remove | keep: reason>
  residue <path>      <N ignored files, no tracked sibling> → <remove | keep: reason>
```

Stop here if `--dry-run`.

## 1. Branches

A local branch is deletable when **its pull request reports `MERGED`**:

```bash
gh pr list --head <branch> --state merged --json number,mergedAt
```

- Merged → `git branch -D <branch>`. `-d` refuses after a rebase merge, for the reason in `shared/git.md`; `-D` is correct here precisely because the SHAs were rewritten.
- Marked `[gone]` by `git branch -vv` but no merged pull request → the remote branch was deleted without merging. **Keep it and say so.** That is either abandoned work or someone else's mistake, and it is not recoverable once the local copy is gone.
- No pull request, commits not on the base → unmerged local work. Keep, report.
- The base branch, and the branch currently checked out anywhere → never.

## 2. Worktrees

Per `git worktree list`, skipping the primary checkout:

1. `git -C <path> status --porcelain` — anything at all, including untracked files, means keep. Say what is dirty.
2. Its branch must be deletable by the rule in step 1.
3. Remove from the primary checkout, never from inside the worktree:
   ```bash
   git worktree remove <path>
   ```
   On `Directory not empty`, retry with `--force` only if step 1 found the tree clean — the residue is ignored files, which is step 3's business.
4. `git worktree prune`.

If the current working directory is inside the worktree being removed, change out of it first. A shell whose directory has been deleted breaks every command after it.

## 3. Residue

Directories holding nothing but ignored files, left behind because `git mv` moves only what git tracks. `git status` stays clean, which is why these survive for months.

```bash
find . -type d -name __pycache__ -not -path './.git/*'
find . -type d -empty -not -path './.git/*'
```

For each candidate, the test is whether **anything tracked still lives under it**:

```bash
git ls-files --error-unmatch <dir> >/dev/null 2>&1
```

- No tracked files, and every file inside is ignored → residue. Remove.
- Any tracked file under it → not residue, whatever it looks like. Keep.
- Ignored files beside tracked ones — a live `__pycache__` next to its `.py`, `node_modules` next to `package.json` — are working state, not residue. Keep.

Never remove `.git`, `.venv`, `node_modules`, or anything named in `.gitignore` that sits beside tracked files. Deleting a build cache costs a rebuild; deleting `.venv` costs an afternoon. If a directory is large and expensive to recreate, list it and ask instead.

## 4. Verify

```bash
git branch -vv
git worktree list
git status --porcelain
```

The working tree must be exactly as clean as it was in step 0. If cleanup made it dirty, something tracked was removed — restore it with `git restore` and stop.

## Reporting

```
Cleaned <repo>.
  branches   <deleted: a, b | none>
  worktrees  <removed: path | none>
  residue    <removed: path (N files) | none>
  kept       <name — reason; …>
```

`kept` is the important half. Every line in it is something that looked removable and was not, and each needs its reason stated — an unmerged branch, a dirty worktree, an ignored directory with tracked siblings.
