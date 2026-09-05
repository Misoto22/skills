# Cleanup — iteration 2 rollout

## What this iteration is

An audit finding, not a failing case. `cleanup`'s description spent 120
characters restating how it verifies a deletion:

> Every deletion is verified against the forge first, and anything unmerged or
> unexplained is reported rather than removed.

`SKILL.md` says it in its third line — "Every deletion here is verified against
the forge, never against git alone" — and then spends four passes on what
"unexplained" means per kind of thing. The description's copy is a second source
for a rule the body owns, in the field loaded on every turn, and no prompt routes
to `cleanup` because of it.

`delete merged branches` and `remove stale branches` were also one branch listed
twice.

## Rollout

Routing, `EVALS_SPLIT=tuning`, all six `dev` skills scored together because they
compete for each other's prompts:

```
ship      tuning   7/7
cleanup   tuning   8/8
sync      tuning   6/6
retitle   tuning   6/6
steward   tuning   9/9
reunite   tuning   6/6
```

**The tuning split is at ceiling before the edit.** No edit can raise 42 of 42,
so the gate in `evals/ITERATION.md` cannot accept one on a rise; it is used as a
veto instead. See [benchmark-summary.md](benchmark-summary.md).

## What passed that this edit could break

| Case | Split | The surface the edit could take away |
| --- | --- | --- |
| `merged-branches` | tuning | "Clean up the branches that have already merged." — "delete merged or stale branches" carries both words the old list carried. |
| `stale-worktrees` | tuning | "Remove the worktrees I am no longer using." — "clear out old worktrees" is untouched. |
| `remote-branches` | tuning | "There are a dozen merged branches still sitting on GitHub. Prune them." — "prune the remote branches" is untouched. |
| `chinese-tidy`, `chinese-delete-merged` | tuning | `清理一下仓库，收拾下没用的分支` and `清掉已经合并过的分支`. Every Chinese phrase is kept verbatim; the audit's "one trigger per branch" is applied to the English list only, because the Chinese phrases are what four separate cases land on. |
| `chinese-remote-branches` | holdout | `远程还留着一堆合并过的分支，清一下` — held by `清理远程分支` and `清掉合并过的分支`, both kept. |
| `chinese-discard-work` | holdout | `把我没提交的改动都扔掉` — held by the `Not for` clause, which is untouched. Removing the "reported rather than removed" sentence takes away a second statement of restraint that this case could have been leaning on. It is the case most exposed by this edit. |
| `discard-work`, `reset-branch`, `unseen-untracked` | tuning | The three English non-triggers, held by the same untouched `Not for` clause. |
