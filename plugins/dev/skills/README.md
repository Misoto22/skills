# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [ship](ship/SKILL.md) — lands the current changes as a merged pull request: preflight, branch, test, commit, PR, CI, merge, worktree cleanup.
- [sync](sync/SKILL.md) — fetches, prunes, and fast-forwards the base branch, then reports what diverged. It never rebases a feature branch or discards a local commit.
- [cleanup](cleanup/SKILL.md) — removes what shipping left behind — merged branches, their worktrees, and ignored residue a move stranded. Every deletion is verified against the forge first.
- [retitle](retitle/SKILL.md) — renames agent conversations onto a dated `MMDD｜TYPE｜subject` scheme, English by default and Chinese with `--lang=zh`, proposing every rename as a two-column table before writing one.
- [steward](steward/SKILL.md) — sweeps every repository a session has touched, runs sync, cleanup and retitle in each, and reports what is ready to merge and which worktrees a live session still occupies. Forked and unattended: the questions land in the report.
- [reunite](reunite/SKILL.md) — unions the desktop app's per-account conversation indexes so every signed-in account sees the whole sidebar history. It also pulls a shared conversation's diverged titles back onto one name. It only ever adds entries, records each entry and each title it replaced, and `--undo` takes exactly those back.

`shared/git.md` carries the rules ship, sync and cleanup need: base resolution, the
force-push rule, why `git branch --merged` lies after a rebase merge, and that `git mv`
leaves ignored files behind. `scripts/sync-shared.py` vendors it into each skill.

`hooks/hooks.json` registers two hooks the moment the plugin is enabled: the
session-naming hook retitle ships, on every prompt, and `hooks/guard-git.py`, which
refuses a bare force-push, `--no-verify`, and `gh pr merge --admin` before they run.
