# Gate — ship, iteration 2

Three edits of three budgeted. All kept.

## Scores

`deepseek-default` through the evaluation gateway, `EVALS_SPLIT=all`, two samples
before and two after. A sample the judge or the generator could not complete is
void, not failing — this run produced an unusual number of them, and sample 1
after the edits is largely unusable for that reason.

| | before, s1 | before, s2 | after, s1 | after, s2 |
| --- | --- | --- | --- | --- |
| tuning routing | 7 / 7 | 7 / 7 | 7 / 7 | 7 / 7 |
| holdout routing | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 |
| holdout behavior | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| tuning behaviors, valid cases | 8 | 8 | 4 | 7 |
| of those, clean | 4 | 5 | 1 | 4 |

**Holdout did not fall, in either sample. The edits are kept**, on the same
grounds as iteration 1: the stable half of this suite shows no regression, and
the tuning half does not resolve a change of this size. Reporting a tuning number
off four valid cases would be reporting the judge's mood.

## The cases named at risk

- `worktree-holding-this-session` — void in both post-edit samples, so edit 2 is
  **unmeasured**, not passed. Its expectation 3 (that step 7 still reaches 7c) is
  what shortening 7a was most likely to move, and this iteration cannot say which
  way. Recorded as unmeasured rather than presented as gated; see
  `evals/synastry-reading/iteration-1/benchmark-summary.md` for the precedent.
- `chinese-conversation-english-commit` — expectation 2 fails in every sample
  before and after, with the same reason: the answer explains that it cannot
  begin rather than producing a subject, a branch name and a body. Step 1 no
  longer carries the naming rule, and the failure did not change shape, so the
  citation is not what produces it.
- `unpushed-commits-on-the-base` — passes in every sample, before and after. Step
  1 was edited and still branches off rather than reporting an empty run.

## What this suite is actually measuring

Across five scored runs of `ship`, what flips between samples is the shape of the
answer, not the rule: an answer opening "there is no repository state, so I cannot
run the preflight" fails every expectation phrased as an outcome, and an answer
that gives the plan passes them. Sample 2 here failed `tests-declared-only-in-ci`
with *aborted due to a preflight Git repository check* — a refusal produced by
step 0a, in a runner that has no git.

That is a property of the suite, and it is worth fixing on its own: it is the
class `evals/README.md` already names. It is deliberately not fixed here, because
a case rewritten while an edit is open cannot tell a fix from an overfit.
