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

## Ignored files survive a move, and git will not tell you

`git mv` moves what git tracks. Anything matched by `.gitignore` — `__pycache__/`, `node_modules/`, `dist/`, `.venv/` — stays where it was, holding its parent directories alive. `git status` stays clean, because every file left behind is ignored.

After moving a directory, check the source is actually gone:

```bash
test -e <old path> && find <old path> -type f | head
```

## Branch names

`{type}/{slug}`, kebab-case, three to five words in the slug.

`feat` · `fix` · `docs` when every changed file is prose · `chore` when every changed file is config, dependencies, or a lockfile · `refactor` · `test` · `ci`.

Build the slug from the commit subject's content words — drop the leading verb, articles, and conjunctions. Reading a large diff to invent a name is wasted work; the subject already says it.

## Worktrees

A worktree cannot remove itself while you are standing in it, and a shell whose working directory has been deleted breaks every command that follows. Run `git worktree remove` from the primary checkout, and change directory out of the worktree first.

`git worktree list` reports the primary checkout too. More than one line means a worktree exists; one line means there is nothing to clean.
