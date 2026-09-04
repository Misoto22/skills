`sync` brings a local repository in line with its remote and then states plainly what did not line up. It fetches, prunes the tracking refs whose upstream is gone, fast-forwards the base branch, and reports every branch that needs a decision — without making any of those decisions for you.

## It only ever fast-forwards

Where a branch has diverged, choosing between rebase, merge and reset is your call, and guessing it destroys work. So the skill fast-forwards what can be fast-forwarded and reports the rest.

A rebase run without being asked is indistinguishable from losing work, which is why there is no flag to turn one on.

Two smaller refusals follow from the same rule. Tags are fetched but never pruned: `--prune-tags` deletes every local tag the remote does not carry, including one you made by hand five minutes ago, and a tag is sometimes the only thing keeping a commit reachable. And a dirty working tree that blocks the fast-forward is reported with the files that blocked it — stashing on your behalf is how uncommitted work goes missing.

## It reports before it writes

Every line of the opening report comes from a command that writes nothing: the state of the working tree, the current branch's position against its upstream, how far the base is behind, which branches lost their upstream in the prune, and which worktrees exist.

```
Sync <repo> → <base>
  working tree   clean
  current branch feat/x  ahead 2, behind 0
  base main      behind 7
  gone upstream  none
  worktrees      3
```

A field no command could fill is reported as unknown, never estimated and never quietly dropped.

## Then it tells you what your branch is doing

The base branch gets fast-forwarded. Your feature branch gets a sentence:

| State | What you are told |
|---|---|
| No upstream | push with `-u` to create one |
| Ahead only | unpushed work |
| Behind only | rebase onto the base when ready |
| Diverged | N ahead, M behind — rebase or merge, your call |
| Upstream gone | the pull request was probably merged and the branch deleted; `/dev:cleanup` removes it |

With `--all` every local branch is classified the same way, and the ones that are strictly behind are fast-forwarded without being checked out. A branch held by another worktree is skipped with that as the reason, which is a fact rather than an error.

## What it will not do

It does not ship changes, delete branches, or resolve a merge conflict. It never rebases, never resets, and never discards a local commit. Everything it refused to decide is collected under `attention` in the final report, with the options stated and none of them picked.
