# Gate — cleanup, iteration 1

Three edits of three budgeted. All kept.

## The edits

Three restatements become citations. `cleanup` opened by pointing at
`shared/git.md` and then wrote out three of its rules again:

1. step 2 — the rule that a session never removes the worktree it runs in, now
   `shared/git.md` § The home worktree;
2. step 3 — what deleting a remote branch does to an open pull request;
3. step 4 — what `git mv` leaves behind.

## Scores

One sample each, `deepseek-default` through the evaluation gateway,
`EVALS_SPLIT=all`.

| | baseline | after |
| --- | --- | --- |
| tuning routing | 8 / 8 | 8 / 8 |
| holdout routing | 2 / 2 | 2 / 2 |
| `remote-branch-with-open-pr` | exp 3 fails | exp 3 fails |
| `no-pr-but-contained-in-base` | pass | pass |
| `own-worktree` (held out) | exp 3 fails; 1 and 2 pass | exp 3 fails; 1 and 2 pass |

**Holdout did not fall. Tuning did not move, and could not have** — no edit here
is aimed at a failing case. Reported as a veto that did not fire, not as an
improvement.

## What the gate was actually for

`own-worktree` is the held-out case, and its first two expectations are the
home-worktree rule itself: keep the worktree the run is standing in, give running
inside it as the reason, and do not change directory and remove it anyway. Edit 1
replaced that whole paragraph with a heading reference.

Both expectations pass, before and after. A rule reached through
`shared/git.md` § The home worktree is reached as reliably as one written out in
the skill — which is the claim the three edits rest on, and the one that could not
be settled by reading the page.

`remote-branch-with-open-pr` expectation 2 — that deleting the branch would close
the open pull request — also passes before and after, and it is the sentence edit 2
deleted. The heading it cites says it instead.

Its expectation 3 fails identically in both runs: the prompt names one branch and
that branch is the exception, so there is no second branch for the answer to
delete. That is a case defect, not a skill defect, and it is left alone while an
edit is open.
