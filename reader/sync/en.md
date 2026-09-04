`sync` does one thing: it lays out the difference between your local repository and its remote, and performs only the part of that which is unambiguously safe. It fetches, prunes the tracking refs whose upstream is gone, fast-forwards the base branch, and lists every branch that needs a decision from you.

## It only fast-forwards

The base branch moves only when it can be fast-forwarded. When it cannot, the local branch carries commits the remote does not, and the run reports the divergence and stops.

The reason is that the three choices available at that point — rebase, merge, reset — can all lose work, and deciding whether to lose it is a person's call rather than a sync tool's. There is not even a flag to turn automatic rebasing on: a rebase run without being asked is indistinguishable in its result from losing work.

The same rule produces two smaller refusals. Tags are fetched but never pruned, because `--prune-tags` deletes every local tag the remote does not carry, including one made by hand five minutes ago, and a tag is sometimes the only thing keeping a commit reachable. And when a dirty working tree blocks the fast-forward, the run reports which files blocked it rather than stashing them for you.

## It reports before it writes

Every line of the opening report comes from a command that writes nothing: the state of the working tree, how far the current branch is ahead of or behind its upstream, how far the base is behind, which branches lost their upstream in the prune, and which worktrees exist.

```
Sync <repo> → <base>
  working tree   clean
  current branch feat/x  ahead 2, behind 0
  base main      behind 7
  gone upstream  none
  worktrees      3
```

A field no command could fill is reported as unknown. It is not estimated, and it is not quietly dropped.

## What your branch is doing

The base branch is fast-forwarded. The feature branch you are on is left alone and given a sentence:

| State | Reported as |
|---|---|
| No upstream | push with `-u` to create one |
| Ahead only | unpushed work |
| Behind only | rebase onto the base when ready |
| Diverged | N ahead, M behind — rebase or merge, your call |
| Upstream gone | the pull request was probably merged and the branch deleted; `/dev:cleanup` removes it |

With `--all`, every local branch is classified the same way, and the ones that are strictly behind are fast-forwarded without being checked out. A branch held by another worktree is skipped with that as the reason: the ref is pinned by a working tree, so the command would be refused anyway.

## What it does not do

It does not ship changes, delete branches, or resolve merge conflicts. It does not rebase, does not reset, and does not discard a local commit. Everything it refused to decide is collected under `attention` at the end of the report, with the options stated and none of them chosen.
