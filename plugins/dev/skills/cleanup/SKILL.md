---
name: cleanup
description: Remove what shipping left behind — local and remote branches whose pull request merged, worktrees for those branches, and ignored residue a move stranded, such as a __pycache__ that git mv could not see. Use when asked to clean up, tidy the repo, delete merged or stale branches, prune the remote branches, clear out old worktrees, 清理一下, 清掉合并过的分支, 删掉没用的分支, 清理远程分支, 收拾一下仓库. Not for discarding uncommitted work, resetting a branch, or removing untracked files you have not been shown.
license: MIT
metadata:
  version: "0.18.5" # x-release-please-version
argument-hint: "[--base=<branch>] [--branches] [--remote] [--worktrees] [--residue] [--no-remote] [--dry-run]"
---

# Cleanup

Remove what shipping left behind. Nothing else.

Read [shared/git.md](shared/git.md) first — in particular that a rebase or squash merge rewrites commits, so `git branch --merged` does not list a branch that landed. Every deletion here is verified against the forge, never against git alone.

**Default to `--dry-run` reasoning even without the flag: list everything, then delete.** With no scope flag, all four passes run. With any of `--branches`, `--remote`, `--worktrees`, `--residue`, only those. `--no-remote` drops the remote pass and keeps the rest — for a fork you cannot push to, or when you only want the local side tidied.

## 0. Inventory, before deleting anything

```bash
git fetch --prune
git branch -vv
git worktree list
git status --porcelain
git ls-remote --heads origin
```

`git fetch --prune` only deletes local `origin/*` tracking refs. It does not touch
a single branch on the remote, which is why the remote list is read separately —
a branch missing from `git branch -vv` may still be sitting on the forge.

Print one table. Nothing is removed until it is printed:

> **Cleanup `<repo>` → `<base>`**
>
> | Kind | Name | Finding | Action |
> |---|---|---|---|
> | branch | `<name>` | merged #12 · unmerged: N commits · no PR, contained in base | delete · keep: reason |
> | remote | `<name>` | merged #12 · open #22 · no PR | delete · keep: reason |
> | worktree | `<path>` | clean, branch merged · dirty: N files | remove · keep: reason |
> | residue | `<path>` | N ignored files, no tracked sibling | remove · keep: reason |

A markdown table, never a fixed-width block. Branch names run past forty characters and the finding is written in the reader's language, so any column width computed here is wrong in their terminal: one long row wraps, and every column under it is thrown out of alignment. A table wraps inside its own cell and the rest of the row stays where it belongs.

Strip a prefix every name shares — `claude/`, `feature/`, `dependabot/` — and say once that you stripped it. Repeated down twelve rows it costs a column and tells the reader nothing.

Stop here if `--dry-run`.

## 1. Branches

A local branch is deletable when **its pull request reports `MERGED`**:

```bash
gh pr list --head <branch> --state merged --json number,mergedAt
```

- Merged → `git branch -D <branch>`. `-d` refuses after a rebase merge, for the reason in `shared/git.md`; `-D` is correct here precisely because the SHAs were rewritten.
- No pull request, but every commit is already on the base → delete. Prove it rather than assuming it:
  ```bash
  git merge-base --is-ancestor <branch> <base>
  ```
  A branch merged by hand, or one whose pull request was deleted, lands here. Nothing is lost, so the missing pull request is not a reason to keep it — but report which test cleared it, because "no PR" and "deleted" together look alarming in a report.
- Marked `[gone]` by `git branch -vv`, no merged pull request, **and** commits not on the base → the remote branch was deleted without merging. **Keep it and say so.** That is either abandoned work or someone else's mistake, and it is not recoverable once the local copy is gone.
- No pull request, commits not on the base → unmerged local work. Keep, report.
- The base branch → never.
- A branch checked out in any worktree → not deletable *while* it is checked out. Two cases, and neither is "keep it forever":
  - Checked out in a worktree this pass is about to remove → step 2 removes the worktree, then this rule is re-applied to the branch. Do not decide it before step 2 runs.
  - Checked out in the primary repo, and merged, and its tree is clean → the checkout itself is the leftover. Say so and offer to `git checkout <base>` and delete it. Never switch someone's checkout without asking; a branch name is often the only record of what they were in the middle of.

## 2. Worktrees

Per `git worktree list`, skipping the primary checkout:

1. **The home worktree is never removed** — `shared/git.md` § The home worktree. Report it as kept, with that as the reason.
2. `git -C <path> status --porcelain` — anything at all, including untracked files, means keep. Say what is dirty.
3. Its branch must be deletable by the rule in step 1.
4. Remove from the primary checkout, never from inside the worktree:
   ```bash
   git worktree remove <path>
   ```
   On `Directory not empty`, retry with `--force` only if step 2 found the tree clean — the residue is ignored files, which is step 4's business.
5. `git worktree prune`.
6. Re-apply step 1 to each branch just released. It was held back as "checked out", not as unmerged, and nothing else will come back for it.

A worktree outside this repository's own directory — another tool's session directory, say — is clean and merged like any other, but a live session may still be standing in it. List it and ask rather than removing it unprompted.

## 3. Remote branches

Runs by default. Skip only on `--no-remote`, or when a scope flag other than `--remote` was passed.

The forge is asked twice, because merged and open are not opposites — `shared/git.md` § Deleting a remote branch closes its open pull request.

```bash
gh pr list --head <branch> --state merged --json number
gh pr list --head <branch> --state open   --json number
```

- Merged, and no open pull request → delete.
- Any open pull request → keep, and name the pull request. This is the one case where a merged branch is still in use.
- No pull request at all → keep. A remote branch nobody opened a pull request for is someone else's work in progress, and it is not yours to guess about.
- The base branch, and any branch the remote protects → never.

Delete them in one push rather than one per branch — a stale-branch backlog is usually a dozen, and each push is a round trip:

```bash
git push origin --delete <branch> <branch> …
```

If the push is rejected for permissions, stop and report it: a fork, or a repository where you have read access only. Do not retry per branch — the rejection is the same every time.

Local and remote are decided independently. A branch can be deletable on the remote while its local copy is held back by a worktree, and reporting them as one line hides that.

## 4. Residue

Directories holding nothing but ignored files, left behind by a move — `shared/git.md` § Ignored files survive a move, and git will not tell you.

Search this checkout only. Every other worktree — each path `git worktree list` names besides this one, and anything under `.claude/worktrees/` — is a separate checkout with its own live `__pycache__`, and descending into it reads that working state as residue here:

```bash
top=$(git rev-parse --show-toplevel)
prune=(-path "$top/.git" -o -path "$top/.claude/worktrees")
while IFS= read -r tree; do
  [ "$tree" = "$top" ] || prune+=(-o -path "$tree")
done < <(git worktree list --porcelain | sed -n 's/^worktree //p')
find "$top" \( "${prune[@]}" \) -prune -o -type d \( -name __pycache__ -o -empty \) -print
```

For each candidate, the test is whether its **parent directory** still holds anything tracked — never the candidate itself. Git tracks no `__pycache__` and no empty directory, so asking about the candidate classes every one of them as residue, the live ones included:

```bash
git ls-files -- "$(dirname <dir>)" | head -1        # any output → the parent is live
git ls-files --others --exclude-standard -- <dir>   # any output → untracked work inside
```

- Parent holds a tracked file → live working state, whatever it looks like: a `__pycache__` beside its tracked `.py`, `node_modules` beside `package.json`. Keep.
- Parent holds nothing tracked, and every file inside the candidate is ignored → residue: the move took the source and left this behind. Remove.
- Anything untracked but not ignored inside it → someone's work, not residue. Keep, and list it.

Removing one can leave its parent empty or holding only ignored files; run the search again until it finds nothing new.

Never remove `.git`, `.venv`, `node_modules`, or anything named in `.gitignore` that sits beside tracked files. Deleting a build cache costs a rebuild; deleting `.venv` costs an afternoon. If a directory is large and expensive to recreate, list it and ask instead.

## 5. Verify

```bash
git branch -vv
git worktree list
git status --porcelain
git ls-remote --heads origin
```

The working tree must be exactly as clean as it was in step 0. If cleanup made it dirty, something tracked was removed — restore it with `git restore` and stop.

## Reporting

Two tables, in the same shape as step 0's — what went, then what stayed.

> **Cleaned `<repo>`.**
>
> | Pass | Removed |
> |---|---|
> | branches | `a`, `b` · none |
> | remote | `a`, `b` · none |
> | worktrees | `<path>` · none |
> | residue | `<path>` (N files) · none |
>
> | Kept | Why |
> |---|---|
> | `<name>` | `<reason>` |

The kept table is the important half. Every row in it is something that looked removable and was not, and each needs its reason stated — an unmerged branch, a remote branch with an open pull request, a dirty worktree, the worktree this session is running in, an ignored directory with tracked siblings. It is a table rather than a run-on line because those reasons are sentences, and a dozen of them separated by semicolons is unreadable.

Anything held back only because a human has to decide — a merged branch checked out in the primary repo, a worktree belonging to another tool's session — is reported as a question, not filed under `kept` and forgotten.
