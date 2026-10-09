# Git

Read this before any command that writes to a branch, a remote, or the working tree.

## What language a git artifact is written in

Report to the user in the language they are writing in. Everything git keeps — commit subject and body, branch name, tag, pull request title and body — is written in **English**, whatever language the conversation is in.

The two have different readers. A report is read once, by the person who asked; a commit message is read years later by whoever runs `git log`, and by tooling that greps it. A history that switches language depending on who was at the keyboard is a history nobody can bisect.

The exception is a repository whose existing history is not in English. Match what is already there — `git log --oneline -20` settles it, and consistency with the project beats consistency with this rule.

## Resolving the base branch

Never assume `main`. Take the first that succeeds:

1. An explicit `--base=<branch>` flag.
2. `git symbolic-ref refs/remotes/origin/HEAD --short | sed 's@^origin/@@'` — works on any remote.
3. `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` — GitHub only.
4. `main`.

If step 2 fails with `ref refs/remotes/origin/HEAD is not a symbolic ref`, nobody has set it locally. `git remote set-head origin --auto` fixes it once, permanently.

## The base branch is never force-pushed

Not with `--force`, not with `--force-with-lease`, not to fix a mistake that is already public. A commit that reached the base branch is corrected by another commit.

Feature branches may be force-pushed with `--force-with-lease`, never bare `--force`: the lease is what stops you overwriting a colleague's push you have not fetched.

## After a rebase or squash merge, "merged" cannot be read from git

Both rewrite commits, so the branch that landed has different SHAs from the branch you still hold. `git branch --merged <base>` will not list it, and `git log <base>..<branch>` still shows commits. Neither means the work is unmerged.

Ask the forge, which knows what actually happened:

```bash
gh pr list --head <branch> --state merged --json number,mergedAt
```

A branch is safe to delete when its pull request reports `MERGED`, whatever git says. Deleting it then needs `git branch -D`; `-d` refuses, for exactly the reason above.

A branch with no pull request at all and commits not on the base is unmerged work. Stop and ask before touching it.

A branch with no pull request whose commits are *all* on the base is a different
case, and a common one once a branch has been merged by hand or its pull request
deleted. Nothing is lost by removing it, and git can prove that without the forge:

```bash
git merge-base --is-ancestor <branch> <base>
```

## Deleting a remote branch closes its open pull request

GitHub closes any pull request whose head branch is deleted, so `--state merged`
is not the only question to ask before deleting one. A branch can carry a merged
pull request and a newer open one at the same time:

```bash
gh pr list --head <branch> --state open --json number
```

`gh pr merge --delete-branch` is supposed to remove the remote branch, but it
deletes it after the merge lands and gives up on the first failure — a local
checkout error is enough. The merge succeeds, the branch survives, and nothing
reports it. That is where most stale remote branches come from.

## Ignored files survive a move, and git will not tell you

`git mv` moves what git tracks. Anything matched by `.gitignore` — `__pycache__/`, `node_modules/`, `dist/`, `.venv/` — stays where it was, holding its parent directories alive. `git status` stays clean, because every file left behind is ignored.

After moving a directory, check the source is actually gone:

```bash
test -e <old path> && find <old path> -type f | head
```

## Branch names

`{type}/{slug}`, kebab-case, three to five words in the slug.

`feat` · `fix` · `docs` when every changed file is prose · `chore` when every changed file is config, dependencies, or a lockfile · `refactor` · `test` · `ci`.

Where more than one fits, take the first that does: `docs`, then `chore`, then `fix` when the commit subject opens with fix, bug, or resolve, then `feat`.

Build the slug from the commit subject's content words — drop the leading verb, articles, and conjunctions. Where the subject will not carry it, use the longest common directory prefix of the changed files, and failing that `sync-<dominant directory>` under `chore`. Reading a large diff to invent a name is wasted work; the subject already says it.

## Worktrees

A worktree cannot remove itself while you are standing in it, and a shell whose working directory has been deleted breaks every command that follows. Run `git worktree remove` from the primary checkout, and change directory out of the worktree first.

`git worktree list` reports the primary checkout too. More than one line means a worktree exists; one line means there is nothing to clean.

### The home worktree

The worktree a session is running in is that session's **home worktree**, and no session removes its own. Changing directory does not make it safe: the session's tooling, its scratch state, and its open file handles stay behind, and nothing running inside can undo the deletion. A home worktree is recycled from outside, once the session has ended.

Identify it before moving anywhere. Once you are in the primary checkout the question can no longer be asked, because `git rev-parse --show-toplevel` then answers for the primary:

```bash
git rev-parse --show-toplevel   # record at the start of the run, compare later
```

Report a home worktree as kept, with that as the reason. It is a completed step, not a failure — running from a worktree is the common case.
