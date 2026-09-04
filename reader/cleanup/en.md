After a change ships, the leftovers stay: the local branch, its copy on the remote, the worktree it was built in, and sometimes a directory holding nothing but ignored files. `cleanup` removes those, and keeps and reports anything whose history it cannot account for.

## Whether a branch merged is a question for the forge

A rebase or squash merge rewrites commits, so after the merge git itself can no longer tell whether a branch landed — `git branch --merged` does not list it. Deleting on git's answer deletes the wrong branches; keeping on it leaves every squash-merged branch behind forever.

So before every deletion the run asks the forge what the branch's pull request actually reports, and acts only on `MERGED`. A branch with no pull request is not assumed abandoned either: it is deletable only once `git merge-base --is-ancestor` proves every one of its commits is already on the base, and the report names which of the two checks cleared it, because "no pull request" and "deleted" sitting together look alarming.

The remote is asked twice, once for merged and once for open. Those are not opposites: a branch can carry a merged pull request and a newer open one, and GitHub closes any pull request whose head branch is deleted.

## Everything is listed before anything is removed

The first pass writes nothing. It prints one table — every branch, remote branch, worktree and residue directory it found, what it found out about each, and what it intends to do. `--dry-run` stops there.

Four passes run by default. `--branches`, `--remote`, `--worktrees` and `--residue` narrow it to one, and `--no-remote` keeps the other three, for a fork you cannot push to.

The residue pass handles a case git does not warn about: `git mv` moves only what git tracks, so an ignored directory like `__pycache__` or `node_modules` stays where it was and keeps its parent alive, while `git status` still reports clean. The test is whether anything tracked still lives under the directory; if something does, it is not residue. An ignored directory sitting beside tracked files is working state and is kept — deleting a build cache costs a rebuild, and deleting a `.venv` costs an afternoon.

## The table of what stayed

The final report has two tables: what went, and what stayed. The second is the one to read. Every row in it is something that looked removable and was not, with its reason stated — an unmerged branch, a remote branch with an open pull request, a dirty worktree, an ignored directory with tracked siblings.

Anything held back only because a person has to decide is asked as a question rather than filed under "kept". The common case is a merged branch checked out in your primary repository: there the checkout itself is the leftover, but a branch name is often the only record of what you were in the middle of, so the run offers rather than switches it.

## What it does not do

It does not discard uncommitted work, reset a branch, or remove untracked files you have not been shown. A worktree with anything in it is kept, including one holding only untracked files. The worktree the run is standing in is never removed whatever its state, because the deletion cannot be carried out from inside it. And a branch whose remote copy was deleted without merging is kept and flagged: that is either abandoned work or somebody else's mistake, and once the local copy is gone it cannot be recovered.
