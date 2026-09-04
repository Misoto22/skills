# Rollout — sync, iteration 1

Scored 2026-09-05 with `bash scripts/run-evals-local.sh sync`, `EVALS_SPLIT=all`,
`deepseek-default` through the evaluation gateway. One sample.

| Split | Routing | Behaviors |
| --- | --- | --- |
| tuning | 6 / 6 | 3 of 4 cases clean, 2 expectation violations |
| holdout | 2 / 2 | 1 / 1 |

## What failed

`ahead-behind-not-transposed`, both violations, and neither is a rule this
iteration touches:

> expectation 2 failed: the candidate does not actually report any ahead/behind
> counts, so it never puts ahead and behind the right way round.
> expectation 3 failed: the candidate does not actually perform a fast-forward
> or report any diverged branch; it only describes what it would do.

The case asks for counts the runner cannot produce — it has no git, so there is
no repository to count against. `evals/README.md` names this class: *an
expectation must name something a response can carry*. Rewriting the case to fit
would be the overfit `ITERATION.md` forbids, and rewriting it to fit **an edit
that is open** would be worse. It is left failing, and is out of this iteration's
scope.

## What passed that this edit could break

The edit renames `/dev:cleanup` to *the cleanup skill* in two table rows. Two
cases read those rows:

- `all-skips-what-it-cannot-fast-forward` — must still point the `[gone]` branch
  at cleanup rather than deleting it. The name survives the edit; the command
  prefix is what goes.
- `delete-merged` (`routes_to: cleanup`) — the boundary between the two
  descriptions. Untouched: this edit changes the body, not the description.

The holdout cases — `chinese-pull-latest`, `resolve-conflict`,
`diverged-branch-not-rebased` — reach none of the changed lines. Nothing here is
aimed at one.
