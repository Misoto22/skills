# Published skills

Only release-ready, recursively discoverable skills belong in this directory.

- [ship](ship/SKILL.md) — lands the current changes as a merged pull request: preflight, branch, test, commit, PR, CI, merge, worktree cleanup.
- [sync](sync/SKILL.md) — fetches, prunes, and fast-forwards the base branch, then reports what diverged. It never rebases a feature branch or discards a local commit.
- [cleanup](cleanup/SKILL.md) — removes what shipping left behind — merged branches, their worktrees, and ignored residue a move stranded. Every deletion is verified against the forge first.
- [retitle](retitle/SKILL.md) — renames agent conversations onto a dated `MMDD｜TYPE｜subject` scheme, English by default and Chinese with `--lang=zh`, proposing every rename as a two-column table before writing one.

`shared/git.md` carries the rules all three need: base resolution, the force-push
rule, why `git branch --merged` lies after a rebase merge, and that `git mv`
leaves ignored files behind. `scripts/sync-shared.py` vendors it into each skill.
