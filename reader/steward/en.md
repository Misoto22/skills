`sync`, `ship` and `cleanup` each work in the repository you are standing in. `steward` is the one that runs that loop across every repository you have actually been working in — it finds them, sweeps them, and hands back a single report of what is waiting on you: which branches are ready to merge, which pull requests are blocked and on what, which branches were written and never opened, and which worktrees a live session is still sitting in.

## It finds the repositories from your sessions, not from your disk

Which repositories are active is not a question git can answer. A repository is active because a session was open in it, so the list comes from where sessions leave traces: Claude Code's transcripts and the sessions running right now, Codex's thread catalogue, and any directories you name with `--roots`. Each trace resolves to the worktree it sits in, and each worktree to the primary checkout it belongs to, so a repository with a dozen worktrees is swept once rather than a dozen times.

Traces that lead nowhere are counted, not raised: a working directory that no longer exists, a scratch checkout under the system temp directory, a session that ran somewhere that is not a repository. On one machine a fourteen-day window found 15 repositories and 121 worktrees, and set aside 132 vanished directories and 29 sandboxes without stopping.

## An occupied worktree is never touched

This is the thing the delegated skills cannot see. A worktree is occupied when a session has a process attached to it right now, or when any session wrote to it within the last day. An occupied worktree is never removed and its branch is never deleted — merged, clean, and unoccupied are three separate conditions, and only all three together make a worktree removable.

The reason is that a session resumed into a directory that has been deleted breaks every command that follows, and git has no idea the session exists. The sweep passes that list to `cleanup` as keeps, and every one of them appears in the report with the session that holds it.

## It reports what is ready to merge, and merges nothing

Every open pull request is classified: ready, blocked by a failing check, conflicting with the base, waiting on review, or draft. A ready one is reported with the command that would land it.

It is not run. Whether a green pull request should land today is a decision the sweep cannot see — a review you were waiting for, a deploy window, a change you meant to fold in first — and a sweep that merged on green would be taking it for you.

## It runs unattended, so it asks nothing

Scheduled, nobody is at the keyboard, so no pass is allowed to block on a question. Every question a sub-skill would have stopped to ask is written into a *Needs you* section instead: a base branch that could not be fast-forwarded, a branch with commits and no pull request, a merged branch checked out in the primary, a worktree living outside its repository's own directory. `retitle` proposes its renames and writes none, because a scheduler is not a confirmation.

The run is forked: its intermediate output stays inside the fork, and the report is what comes back. It is also written to `~/.local/state/steward/last-sweep.md`, so it survives a missed notification and tells the next sweep when the last one ran.

## What it does not do

It does not merge, rebase, resolve a conflict, or discard a commit. It does not delete anything `cleanup` would have kept, and it schedules itself only when you ask it to. Syncing or cleaning the single repository you are standing in belongs to `sync` and `cleanup`; landing a branch belongs to `ship`.
