After a change ships, the leftovers stay: the local branch, its copy on the remote, the worktree it was built in, and sometimes a directory of ignored files that `git mv` could not see. `cleanup` removes exactly those, and nothing it cannot account for.

## "Merged" is a question for the forge, not for git

A rebase or squash merge rewrites commits, so `git branch --merged` does not list a branch that actually landed. Deleting on git's answer alone deletes the wrong branches; keeping on it leaves every squash-merged branch behind forever.

So every deletion here is verified against the forge — the branch's pull request has to report `MERGED`. A branch with no pull request is not assumed abandoned either: it is deletable only when `git merge-base --is-ancestor` proves every one of its commits is already on the base, and the report says which of the two tests cleared it, because "no PR" and "deleted" sitting together look alarming otherwise.

The remote is asked twice, for merged and for open, because those are not opposites. A branch can carry a merged pull request and a newer open one, and GitHub closes any pull request whose head branch is deleted.

## Everything is listed before anything is removed

The first pass writes nothing. It prints one table — every branch, remote branch, worktree and residue directory it found, what it found out about each, and what it intends to do. `--dry-run` stops there.

Four passes run by default; `--branches`, `--remote`, `--worktrees` and `--residue` narrow it to one, and `--no-remote` keeps everything except the remote pass, for a fork you cannot push to.

Residue is the pass worth explaining. It removes directories holding nothing but ignored files, left stranded because `git mv` moves only what git tracks — a `__pycache__` whose `.py` files moved away months ago. An ignored directory sitting *beside* tracked files is working state, not residue, and is kept: deleting a build cache costs a rebuild, and deleting a `.venv` costs an afternoon.

## The kept table is the important half

The final report has two tables: what went, and what stayed. The second is the one to read. Every row in it is something that looked removable and was not, with the reason stated — an unmerged branch, a remote branch with an open pull request, a dirty worktree, an ignored directory with tracked siblings.

Anything held back only because a person has to decide is asked as a question rather than filed under "kept" and forgotten. A merged branch checked out in your primary repository is the common one: the checkout itself is the leftover, but a branch name is often the only record of what you were in the middle of, so it offers rather than switches.

## What it will not do

It does not discard uncommitted work, reset a branch, or remove untracked files you have not been shown. A worktree with anything at all in it — including untracked files — is kept. The worktree the run is standing in is never removed, whatever its state: the deletion cannot be undone from inside it. And a branch whose remote was deleted without merging is kept and flagged, because that is either abandoned work or somebody else's mistake, and it is not recoverable once the local copy is gone.
