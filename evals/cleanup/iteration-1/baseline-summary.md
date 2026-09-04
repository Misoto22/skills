# Rollout — cleanup, iteration 1

Scored 2026-09-05 with `bash scripts/run-evals-local.sh cleanup`, `EVALS_SPLIT=all`,
`deepseek-default` through the evaluation gateway. One sample.

| Split | Routing | Behaviors |
| --- | --- | --- |
| tuning | 8 / 8 | 1 of 2 cases clean, 1 expectation violation |
| holdout | 2 / 2 | 0 of 1, 1 expectation violation |

## What failed

Both violations are the third expectation of their case, and both ask for an
outcome the prompt supplies no data for:

> `remote-branch-with-open-pr` expectation 3: the candidate reports removing none
> of the remote branches, so it does not indicate that merged branches were
> deleted as requested.
> `own-worktree` expectation 3: the response reports that no worktrees were
> removed, so it does not show that any other clean merged worktree was cleaned up.

Neither prompt names a second branch or a second worktree, so there is nothing
for the answer to remove and the honest answer scores as a failure. This is the
class `evals/README.md` names — *an expectation must name something a response
can carry*. `own-worktree` is the held-out case, which makes it the one this
iteration is least free to touch: rewriting it would point the gate at what
tuning aims for. Both are left failing and are out of scope here.

## What passed that this edit could break

Three citations replace three restatements, and the rules they cite live in
`shared/git.md`, which reaches the model as a linked reference. The risk is that
a rule reached through a heading is reached less reliably than one written out.

- `own-worktree` (**held out**) — the home-worktree rule is the one edit 1
  replaces. The gate's whole job here is to catch a citation that loses the
  behaviour; no wording in this iteration was written with this case in view.
- `remote-branch-with-open-pr` — edit 2 removes the sentence saying that deleting
  a branch closes its open pull request, which is expectation 2. The heading it
  now cites states exactly that, so the sentence is still in the prompt — just
  once instead of twice.
- `no-pr-but-contained-in-base` — untouched, and passing. Edit 1 sits two
  sections away from the rule it tests.

Residue has no behavior case, so edit 3 is measured only by whatever it does to
the rest.
